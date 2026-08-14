"""El borrado real de un padre arrastra a sus hijos por FK.

No se prueba el ORM sino la BD: cada caso emite el DELETE por SQL (`query.
delete()`, sin cascada de sesión) y comprueba que las filas dependientes se
fueron igual. Es lo que permitió sacar el andamiaje manual de `app/db/seed.py`.

Los tests corren sobre SQLite, así que dependen de `PRAGMA foreign_keys=ON`
(app/extensions.py): sin eso pasarían por vacuidad, con las FKs sin aplicar.
"""

# pylint: disable=redefined-outer-name
import pytest

from app.models import (
    Availability,
    Category,
    Group,
    GroupMember,
    GroupMemberCategory,
    GroupPermissionGrant,
    User,
    UserAvailability,
)
from app.models.subgroup import DivisionJob, SubGroup, SubGroupMember


@pytest.fixture()
def arbol(db_session):
    """Un usuario dueño de un grupo con una fila de cada tabla dependiente."""
    duenio = User(email="duenio-cascada@example.com", name="Dueño")
    db_session.add(duenio)
    db_session.flush()

    group = Group(name="Cascada", join_token="tok-cascada", owner_id=duenio.id)
    db_session.add(group)
    db_session.flush()

    member = GroupMember(group_id=group.id, user_id=duenio.id)
    category = Category(group_id=group.id, name="Cat")
    slot = Availability(group_id=group.id, weekday=0, start_minutes=510)
    subgroup = SubGroup(parent_group_id=group.id, name="Sub")
    db_session.add_all([member, category, slot, subgroup])
    db_session.flush()

    db_session.add_all(
        [
            GroupMemberCategory(group_member_id=member.id, category_id=category.id),
            GroupPermissionGrant(
                group_id=group.id,
                permission="subgroups.view_all",
                category_id=category.id,
            ),
            UserAvailability(user_id=duenio.id, availability_id=slot.id),
            SubGroupMember(subgroup_id=subgroup.id, user_id=duenio.id),
            DivisionJob(parent_group_id=group.id, created_by=duenio.id, config_json={}),
        ]
    )
    db_session.flush()

    return {"user": duenio, "group": group}


DEPENDIENTES = [
    GroupMember,
    Category,
    GroupMemberCategory,
    GroupPermissionGrant,
    Availability,
    UserAvailability,
    SubGroup,
    SubGroupMember,
    DivisionJob,
]


def _cuantas(session, model):
    return session.query(model).count()


def test_borrar_el_grupo_arrastra_todo_lo_suyo(db_session, arbol):
    for model in DEPENDIENTES:
        assert _cuantas(db_session, model) == 1

    db_session.query(Group).filter(Group.id == arbol["group"].id).delete(synchronize_session=False)
    db_session.flush()

    for model in DEPENDIENTES:
        assert _cuantas(db_session, model) == 0, model.__name__


def test_borrar_al_duenio_arrastra_su_grupo(db_session, arbol):
    """`group.owner_id` es NOT NULL: el grupo no puede quedar huérfano."""
    db_session.query(User).filter(User.id == arbol["user"].id).delete(synchronize_session=False)
    db_session.flush()

    assert _cuantas(db_session, Group) == 0
    for model in DEPENDIENTES:
        assert _cuantas(db_session, model) == 0, model.__name__


def test_el_job_sobrevive_a_su_creador(db_session, arbol):
    """`division_jobs.created_by` es SET NULL: el historial no se pierde."""
    otro = User(email="otro-cascada@example.com", name="Otro")
    db_session.add(otro)
    db_session.flush()
    job = DivisionJob(parent_group_id=arbol["group"].id, created_by=otro.id, config_json={})
    db_session.add(job)
    db_session.flush()

    db_session.query(User).filter(User.id == otro.id).delete(synchronize_session=False)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(DivisionJob, job.id).created_by is None
