"""Las vistas calientes no hacen más consultas por tener más miembros.

No se afirma un número exacto de queries (cambiaría con cualquier refactor
legítimo): se compara la misma vista con dos tamaños de grupo. Si el conteo
crece con N, volvió a colarse un N+1.

Para medir a escala real, ver `tests/bench_queries.py`.
"""

# pylint: disable=redefined-outer-name
import flask
import pytest
from sqlalchemy import event

from app.extensions import scheduler_db
from app.models import (
    Availability,
    Category,
    Group,
    GroupMember,
    SubGroup,
    SubGroupMember,
    GroupMemberCategory,
    GroupPermissionGrant,
    RoleEnum,
    UserAvailability,
)
from app.models.user import User
from app.permissions import PERM_VIEW_ALL


class QueryCounter:
    """Cuenta las sentencias SQL ejecutadas dentro del bloque."""

    def __init__(self):
        self.count = 0

    def __enter__(self):
        event.listen(scheduler_db.engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *_exc):
        event.remove(scheduler_db.engine, "before_cursor_execute", self._on_execute)
        return False

    def _on_execute(self, *_args):
        self.count += 1


def _seed_group(db_session, n_members, token):
    users = [
        User(email=f"{token}-{i}@test.local", name=f"Usuario {i}") for i in range(n_members)
    ]
    db_session.add_all(users)
    db_session.flush()

    group = Group(name=f"Grupo {token}", join_token=token, owner_id=users[0].id)
    db_session.add(group)
    db_session.flush()

    members = [
        GroupMember(
            group_id=group.id,
            user_id=user.id,
            role=RoleEnum.ADMIN if i == 0 else RoleEnum.MEMBER,
        )
        for i, user in enumerate(users)
    ]
    db_session.add_all(members)

    categories = [Category(group_id=group.id, name=f"Cat {i}") for i in range(3)]
    db_session.add_all(categories)
    db_session.flush()
    for i, member in enumerate(members):
        db_session.add(
            GroupMemberCategory(
                group_member_id=member.id, category_id=categories[i % 3].id
            )
        )
    for category in categories:
        db_session.add(
            GroupPermissionGrant(
                group_id=group.id, category_id=category.id, permission=PERM_VIEW_ALL
            )
        )
    for member in members[1:]:
        db_session.add(
            GroupPermissionGrant(
                group_id=group.id, group_member_id=member.id, permission=PERM_VIEW_ALL
            )
        )

    availabilities = [
        Availability(group_id=group.id, weekday=weekday, start_minutes=(9 + block) * 60)
        for weekday in range(3)
        for block in range(4)
    ]
    db_session.add_all(availabilities)
    db_session.flush()
    for i, user in enumerate(users):
        for slot in range(4):
            db_session.add(
                UserAvailability(
                    user_id=user.id,
                    availability_id=availabilities[(i + slot) % len(availabilities)].id,
                )
            )

    db_session.commit()
    # Se devuelven ids y no instancias: la medición vacía la sesión, y una
    # instancia detached ya no puede refrescar sus columnas.
    return group.id, users[0].id


def _count_queries(client, owner_id, path):
    # El fixture `db_session` deja un app context empujado, así que las
    # requests del test client lo reutilizan en vez de crear uno nuevo: sin
    # limpiar el usuario que flask_login cachea en `g`, la segunda medición
    # correría autenticada como el usuario de la primera.
    flask.g.pop("_login_user", None)

    with client.session_transaction() as flask_session:
        flask_session["_user_id"] = str(owner_id)
        flask_session["_fresh"] = True
    client.get(path)  # calentamiento: descarta el trabajo puntual del arranque
    # Identity map en frío: con los objetos del seed (o del calentamiento)
    # cargados en la sesión, un lazy load no llega a la base y el N+1 se
    # esconde. Una request real siempre arranca con la sesión vacía.
    scheduler_db.session.expunge_all()
    with QueryCounter() as counter:
        response = client.get(path)
    assert response.status_code == 200, f"{path} devolvió {response.status_code}"
    return counter.count


@pytest.mark.parametrize(
    "path_template",
    [
        "/groups/",
        "/groups/{group_id}",
        "/groups/{group_id}/permissions",
        "/groups/{group_id}/members",
        "/groups/{group_id}/members/export.csv",
        "/groups/{group_id}/subgroups",
        "/groups/{group_id}/subgroups/new",
    ],
)
def test_vista_no_escala_en_queries_con_los_miembros(app, db_session, path_template):
    grupo_chico, owner_chico = _seed_group(db_session, 3, "perf-chico")
    grupo_grande, owner_grande = _seed_group(db_session, 30, "perf-grande")

    chico = _count_queries(
        app.test_client(), owner_chico, path_template.format(group_id=grupo_chico)
    )
    grande = _count_queries(
        app.test_client(), owner_grande, path_template.format(group_id=grupo_grande)
    )

    assert grande == chico, (
        f"{path_template}: {chico} queries con 3 miembros y {grande} con 30 "
        "→ hay un N+1"
    )


def _seed_group_con_subgrupos(db_session, n_members, token):
    group_id, owner_id = _seed_group(db_session, n_members, token)
    memberships = GroupMember.query.filter_by(group_id=group_id).all()
    subgroup = SubGroup(parent_group_id=group_id, name=f"Sub {token}")
    db_session.add(subgroup)
    db_session.flush()
    for m in memberships:
        db_session.add(SubGroupMember(subgroup_id=subgroup.id, user_id=m.user_id))
    db_session.commit()
    return group_id, owner_id


def test_export_csv_subgrupos_no_escala_en_queries(app, db_session):
    """get_confirmed_subgroups usa eager loading — sin N+1 al escalar miembros."""
    grupo_chico, owner_chico = _seed_group_con_subgrupos(db_session, 3, "perf-export-chico")
    grupo_grande, owner_grande = _seed_group_con_subgrupos(db_session, 30, "perf-export-grande")

    chico = _count_queries(
        app.test_client(), owner_chico, f"/groups/{grupo_chico}/subgroups/export"
    )
    grande = _count_queries(
        app.test_client(), owner_grande, f"/groups/{grupo_grande}/subgroups/export"
    )

    assert grande == chico, (
        f"/subgroups/export: {chico} queries con 3 miembros y {grande} con 30 "
        "→ N+1 en get_confirmed_subgroups"
    )
