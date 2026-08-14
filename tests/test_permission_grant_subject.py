"""Una concesión de permiso tiene exactamente un sujeto.

La regla vivía solo en la ruta que concede; ahora la impone el CHECK
`ck_perm_grant_subject_xor`, así que se prueba contra la BD.
"""

# pylint: disable=redefined-outer-name
import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Category, Group, GroupMember, GroupPermissionGrant, User


@pytest.fixture()
def contexto(db_session):
    user = User(email="perm-xor@example.com", name="P")
    db_session.add(user)
    db_session.flush()

    group = Group(name="XOR", join_token="tok-xor", owner_id=user.id)
    db_session.add(group)
    db_session.flush()

    member = GroupMember(group_id=group.id, user_id=user.id)
    category = Category(group_id=group.id, name="Cat")
    db_session.add_all([member, category])
    db_session.flush()

    return {"group": group, "member": member, "category": category}


def _rechaza(session, row):
    savepoint = session.begin_nested()
    session.add(row)
    with pytest.raises(IntegrityError):
        session.flush()
    savepoint.rollback()


def test_sin_sujeto_es_rechazada(db_session, contexto):
    """El caso real: se guardaba con subject_key 'cNone' y ocupaba la unicidad."""
    _rechaza(
        db_session,
        GroupPermissionGrant(group_id=contexto["group"].id, permission="subgroups.view_all"),
    )


def test_con_los_dos_sujetos_es_rechazada(db_session, contexto):
    _rechaza(
        db_session,
        GroupPermissionGrant(
            group_id=contexto["group"].id,
            permission="subgroups.view_all",
            group_member_id=contexto["member"].id,
            category_id=contexto["category"].id,
        ),
    )


@pytest.mark.parametrize("campo", ["group_member_id", "category_id"])
def test_con_un_solo_sujeto_se_acepta(db_session, contexto, campo):
    sujeto = contexto["member" if campo == "group_member_id" else "category"]
    db_session.add(
        GroupPermissionGrant(
            group_id=contexto["group"].id,
            permission="subgroups.view_all",
            **{campo: sujeto.id},
        )
    )
    db_session.flush()


def test_la_ruta_ya_no_puede_dejar_el_fantasma(db_session, contexto, client):
    """La ruta corta antes por su cuenta: sin sujeto válido no inserta nada."""
    duenio = db_session.get(User, contexto["group"].owner_id)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(duenio.id)
        sess["_fresh"] = True

    response = client.post(
        f"/groups/{contexto['group'].id}/permissions/set",
        data={"subject": "category:999999", "level": "view_all"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert GroupPermissionGrant.query.count() == 0
