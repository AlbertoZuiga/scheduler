"""Autorización de controles de escritura en la pantalla de subgrupos.

Cubre:
- view_own: GET /groups/<id>/subgroups no expone acciones de escritura.
- view_availability (implica view_own): idem.
- edit_own + pertenencia: sí expone las acciones (no-regresión).
- POST add_member, remove_member, rename con solo view_own -> 403.
"""

import flask

from app.models import (
    Group,
    GroupMember,
    GroupPermissionGrant,
    RoleEnum,
)
from app.models.subgroup import SubGroup, SubGroupMember
from app.models.user import User
from app.permissions import (
    PERM_EDIT_OWN,
    PERM_VIEW_AVAILABILITY,
    PERM_VIEW_OWN,
)


def _seed(db_session, token):
    """Owner + 2 miembros en un subgrupo compartido."""
    owner = User(email=f"{token}-owner@t.lo", name="Owner")
    member_a = User(email=f"{token}-a@t.lo", name="Miembro A")
    member_b = User(email=f"{token}-b@t.lo", name="Miembro B")
    db_session.add_all([owner, member_a, member_b])
    db_session.flush()

    group = Group(name=f"G-{token}", join_token=token, owner_id=owner.id)
    db_session.add(group)
    db_session.flush()

    gm_owner = GroupMember(group_id=group.id, user_id=owner.id, role=RoleEnum.ADMIN)
    gm_a = GroupMember(group_id=group.id, user_id=member_a.id, role=RoleEnum.MEMBER)
    gm_b = GroupMember(group_id=group.id, user_id=member_b.id, role=RoleEnum.MEMBER)
    db_session.add_all([gm_owner, gm_a, gm_b])
    db_session.flush()

    sg = SubGroup(parent_group_id=group.id, name=f"SG-{token}")
    db_session.add(sg)
    db_session.flush()

    db_session.add_all(
        [
            SubGroupMember(subgroup_id=sg.id, user_id=member_a.id),
            SubGroupMember(subgroup_id=sg.id, user_id=member_b.id),
        ]
    )
    db_session.commit()

    return group, owner, member_a, member_b, gm_a, gm_b, sg


def _client_for(app, user_id):
    flask.g.pop("_login_user", None)
    client = app.test_client()
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True
    return client


def _get_subgroups(app, user_id, group_id):
    client = _client_for(app, user_id)
    resp = client.get(f"/groups/{group_id}/subgroups")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


# ---------------------------------------------------------------------------
# view_own: GET no expone controles de escritura
# ---------------------------------------------------------------------------


def test_view_own_no_muestra_add_member(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-view-add")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_OWN,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, member_b.id, group.id)

    assert "Agregar integrante" not in body


def test_view_own_no_muestra_remove_member(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-view-rm")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_OWN,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, member_b.id, group.id)

    assert "/members/" not in body


# ---------------------------------------------------------------------------
# view_availability (implica view_own): idem
# ---------------------------------------------------------------------------


def test_view_availability_no_muestra_add_member(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-avail-add")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_AVAILABILITY,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, member_b.id, group.id)

    assert "Agregar integrante" not in body


def test_view_availability_no_muestra_remove_member(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-avail-rm")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_AVAILABILITY,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, member_b.id, group.id)

    assert "/members/" not in body


# ---------------------------------------------------------------------------
# edit_own + pertenencia: sí expone las acciones (no-regresión)
# ---------------------------------------------------------------------------


def test_edit_own_miembro_ve_add_member(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-edit-add")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_EDIT_OWN,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, member_b.id, group.id)

    assert "Agregar integrante" in body


def test_edit_own_miembro_ve_remove_member(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-edit-rm")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_EDIT_OWN,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, member_b.id, group.id)

    assert "/members/" in body


def test_edit_own_no_miembro_no_ve_controles(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-edit-nonmember")

    # Tercer miembro del grupo pero fuera del subgrupo
    outsider = User(email="sp-edit-nonmember-out@t.lo", name="Outsider")
    db_session.add(outsider)
    db_session.flush()
    gm_out = GroupMember(group_id=group.id, user_id=outsider.id, role=RoleEnum.MEMBER)
    db_session.add(gm_out)
    db_session.flush()

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_out.id,
            permission=PERM_EDIT_OWN,
        )
    )
    db_session.commit()

    body = _get_subgroups(app, outsider.id, group.id)

    assert "Agregar integrante" not in body
    assert "/members/" not in body


# ---------------------------------------------------------------------------
# POST con view_own -> 403
# ---------------------------------------------------------------------------


def test_post_add_member_con_view_own_retorna_403(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-post-add")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_OWN,
        )
    )
    db_session.commit()

    client = _client_for(app, member_b.id)
    resp = client.post(
        f"/groups/{group.id}/subgroups/{sg.id}/members/add",
        data={"user_id": str(member_a.id)},
    )
    assert resp.status_code == 403


def test_post_remove_member_con_view_own_retorna_403(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-post-rm")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_OWN,
        )
    )
    db_session.commit()

    client = _client_for(app, member_b.id)
    resp = client.post(
        f"/groups/{group.id}/subgroups/{sg.id}/members/{member_a.id}/remove",
    )
    assert resp.status_code == 403


def test_post_rename_con_view_own_retorna_403(app, db_session):
    group, _, member_a, member_b, gm_a, gm_b, sg = _seed(db_session, "sp-post-rename")

    db_session.add(
        GroupPermissionGrant(
            group_id=group.id,
            group_member_id=gm_b.id,
            permission=PERM_VIEW_OWN,
        )
    )
    db_session.commit()

    client = _client_for(app, member_b.id)
    resp = client.post(
        f"/groups/{group.id}/subgroups/{sg.id}/rename",
        data={"name": "Nuevo nombre"},
    )
    assert resp.status_code == 403
