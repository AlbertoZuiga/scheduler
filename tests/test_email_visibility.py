"""El email ajeno solo lo ve owner/admin.

Los permisos de subgrupos (incluso los de edición) no abren emails, y el
fallback de nombre no puede filtrar el email de quien no tiene nombre.
"""

# pylint: disable=redefined-outer-name
from app.models import Category, Group, GroupMember, GroupPermissionGrant, RoleEnum
from app.models.subgroup import SubGroup, SubGroupMember
from app.models.user import User
from app.permissions import PERM_EDIT_ALL, PERM_EDIT_OWN


def _user(db_session, email, name="Con Nombre"):
    user = User(name=name, email=email)
    db_session.add(user)
    db_session.commit()
    return user


def _setup(db_session):
    owner = _user(db_session, "owner-sec011@example.com")
    admin = _user(db_session, "admin-sec011@example.com")
    editor = _user(db_session, "editor-sec011@example.com")
    plain = _user(db_session, "plain-sec011@example.com")
    # Sin nombre: el fallback no puede caer en el email.
    nameless = _user(db_session, "nameless-sec011@example.com", name="")

    group = Group(name="Grupo SEC011", owner_id=owner.id, join_token="tok-sec011")
    db_session.add(group)
    db_session.commit()

    memberships = {}
    for user, role in (
        (owner, RoleEnum.ADMIN),
        (admin, RoleEnum.ADMIN),
        (editor, RoleEnum.MEMBER),
        (plain, RoleEnum.MEMBER),
        (nameless, RoleEnum.MEMBER),
    ):
        membership = GroupMember(group_id=group.id, user_id=user.id, role=role)
        db_session.add(membership)
        memberships[user.id] = membership
    db_session.commit()

    return group, owner, admin, editor, plain, nameless, memberships


def _grant(db_session, group, membership, permission):
    db_session.add(
        GroupPermissionGrant(
            group_id=group.id, group_member_id=membership.id, permission=permission
        )
    )
    db_session.commit()


def _login(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


OTHER_EMAILS = [
    b"owner-sec011@example.com",
    b"admin-sec011@example.com",
    b"nameless-sec011@example.com",
]


def test_miembro_comun_no_ve_emails_ajenos_en_show(client, db_session):
    group, _, _, _, plain, _, _ = _setup(db_session)
    _login(client, plain)
    resp = client.get(f"/groups/{group.id}")
    assert resp.status_code == 200
    for email in OTHER_EMAILS:
        assert email not in resp.data
    # El propio sí (el menú de usuario lo muestra).
    assert b"plain-sec011@example.com" in resp.data


def test_miembro_comun_no_ve_emails_ajenos_en_members(client, db_session):
    group, _, _, _, plain, _, _ = _setup(db_session)
    _login(client, plain)
    resp = client.get(f"/groups/{group.id}/members")
    assert resp.status_code == 200
    for email in OTHER_EMAILS:
        assert email not in resp.data


def test_editar_subgrupos_no_abre_emails(client, db_session):
    """El eje de subgrupos no es el eje de emails: EDIT_ALL no los concede."""
    group, _, _, editor, _, _, memberships = _setup(db_session)
    _grant(db_session, group, memberships[editor.id], PERM_EDIT_ALL)

    _login(client, editor)
    for url in (
        f"/groups/{group.id}",
        f"/groups/{group.id}/members",
        f"/groups/{group.id}/subgroups",
        f"/groups/{group.id}/subgroups/new",
    ):
        resp = client.get(url)
        assert resp.status_code == 200, url
        for email in OTHER_EMAILS:
            assert email not in resp.data, f"{url} filtró {email!r}"


def test_edit_own_tampoco_abre_emails(client, db_session):
    group, _, _, editor, _, _, memberships = _setup(db_session)
    _grant(db_session, group, memberships[editor.id], PERM_EDIT_OWN)

    _login(client, editor)
    resp = client.get(f"/groups/{group.id}/subgroups")
    assert resp.status_code == 200
    for email in OTHER_EMAILS:
        assert email not in resp.data


def test_sin_nombre_el_fallback_no_es_el_email(client, db_session):
    """El usuario sin nombre se muestra como "Usuario #id", no como su email."""
    group, _, _, _, plain, nameless, _ = _setup(db_session)
    _login(client, plain)
    resp = client.get(f"/groups/{group.id}")
    assert resp.status_code == 200
    assert b"nameless-sec011@example.com" not in resp.data
    assert f"Usuario #{nameless.id}".encode() in resp.data


# Un solo login por test: el app context del fixture se comparte entre requests
# y Flask-Login cachea el usuario en `g`, así que un segundo login no toma efecto.
def test_owner_sigue_viendo_los_emails(client, db_session):
    group, owner, _, _, _, _, _ = _setup(db_session)
    _login(client, owner)
    resp = client.get(f"/groups/{group.id}/members")
    assert resp.status_code == 200
    assert b"nameless-sec011@example.com" in resp.data


def test_admin_sigue_viendo_los_emails(client, db_session):
    group, _, admin, _, _, _, _ = _setup(db_session)
    _login(client, admin)
    resp = client.get(f"/groups/{group.id}/members")
    assert resp.status_code == 200
    assert b"nameless-sec011@example.com" in resp.data


def _setup_con_subgrupo(db_session):
    group, owner, _, editor, _, nameless, memberships = _setup(db_session)
    _grant(db_session, group, memberships[editor.id], PERM_EDIT_ALL)
    subgroup = SubGroup(parent_group_id=group.id, name="Sub 1")
    db_session.add(subgroup)
    db_session.commit()
    db_session.add(SubGroupMember(subgroup_id=subgroup.id, user_id=nameless.id))
    db_session.commit()
    return group, owner, editor


def test_export_de_subgrupos_sin_columna_de_email_para_no_admin(client, db_session):
    group, _, editor = _setup_con_subgrupo(db_session)
    _login(client, editor)
    resp = client.get(f"/groups/{group.id}/subgroups/export")
    assert resp.status_code == 200
    assert b"Usuario Email" not in resp.data
    assert b"nameless-sec011@example.com" not in resp.data


def test_export_de_subgrupos_conserva_el_email_para_el_owner(client, db_session):
    group, owner, _ = _setup_con_subgrupo(db_session)
    _login(client, owner)
    resp = client.get(f"/groups/{group.id}/subgroups/export")
    assert resp.status_code == 200
    assert b"Usuario Email" in resp.data
    assert b"nameless-sec011@example.com" in resp.data


def test_categorias_de_otro_miembro_no_muestran_su_email(client, db_session):
    group, owner, _, _, plain, _, memberships = _setup(db_session)
    db_session.add(Category(group_id=group.id, name="Cat SEC011"))
    db_session.commit()

    _login(client, plain)
    resp = client.get(
        f"/categories/group_member/{memberships[owner.id].id}",
        headers={"Accept": "text/html"},
    )
    assert resp.status_code == 200
    assert b"owner-sec011@example.com" not in resp.data
