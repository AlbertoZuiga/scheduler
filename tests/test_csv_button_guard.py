"""Botón "Descargar CSV" visible solo para admin/owner en members.html."""

# pylint: disable=redefined-outer-name
from app.models import Group, GroupMember, RoleEnum
from app.models.user import User


def _user(db_session, email):
    u = User(name=email, email=email)
    db_session.add(u)
    db_session.commit()
    return u


def _setup(db_session):
    owner = _user(db_session, "owner-csv@example.com")
    admin = _user(db_session, "admin-csv@example.com")
    member = _user(db_session, "member-csv@example.com")

    group = Group(name="Grupo CSV", owner_id=owner.id, join_token="tok-csv")
    db_session.add(group)
    db_session.commit()

    db_session.add(GroupMember(group_id=group.id, user_id=owner.id, role=RoleEnum.ADMIN))
    db_session.add(GroupMember(group_id=group.id, user_id=admin.id, role=RoleEnum.ADMIN))
    db_session.add(GroupMember(group_id=group.id, user_id=member.id, role=RoleEnum.MEMBER))
    db_session.commit()

    return group, owner, admin, member


def _get_members_html(client, user, group):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return client.get(f"/groups/{group.id}/members")


CSV_LABEL = b"Descargar CSV"


def test_miembro_comun_no_ve_el_boton_csv(client, db_session):
    group, _, _, member = _setup(db_session)
    resp = _get_members_html(client, member, group)
    assert resp.status_code == 200
    assert CSV_LABEL not in resp.data


def test_admin_ve_el_boton_csv(client, db_session):
    group, _, admin, _ = _setup(db_session)
    resp = _get_members_html(client, admin, group)
    assert resp.status_code == 200
    assert CSV_LABEL in resp.data


def test_owner_ve_el_boton_csv(client, db_session):
    group, owner, _, _ = _setup(db_session)
    resp = _get_members_html(client, owner, group)
    assert resp.status_code == 200
    assert CSV_LABEL in resp.data
