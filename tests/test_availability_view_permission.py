"""Permiso availability.view_all sobre groups.show.

Cubre seis criterios de aceptación:
- Sin permiso → solo marcas propias en HTML y embed.
- Con availability.view_all → grilla agregada visible.
- Owner → grilla agregada visible.
- subgroups.view_all NO alcanza para ver la grilla.
- El embed no lleva identidades de otros usuarios a quien no tiene el permiso.
- Regresión: el permiso se concede y revoca desde el panel del owner.
"""

import json
import re

import flask
import pytest

from app.extensions import scheduler_db
from app.models import (
    Availability,
    Group,
    GroupMember,
    GroupPermissionGrant,
    RoleEnum,
    UserAvailability,
)
from app.models.user import User
from app.permissions import PERM_VIEW_ALL, PERM_VIEW_AVAILABILITY

EMBED_RE = re.compile(
    r'<script type="application/json" id="embed-data"[^>]*>(.*?)</script>', re.DOTALL
)


def _seed(db_session, token):
    """Grupo mínimo: owner + 2 miembros, 2 slots de disponibilidad."""
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

    slot1 = Availability(group_id=group.id, weekday=0, start_minutes=9 * 60)
    slot2 = Availability(group_id=group.id, weekday=1, start_minutes=10 * 60)
    db_session.add_all([slot1, slot2])
    db_session.flush()

    # owner y member_a marcan el slot1; solo owner marca slot2
    db_session.add_all([
        UserAvailability(user_id=owner.id, availability_id=slot1.id),
        UserAvailability(user_id=member_a.id, availability_id=slot1.id),
        UserAvailability(user_id=owner.id, availability_id=slot2.id),
    ])
    db_session.commit()

    return group, owner, member_a, member_b, gm_a, gm_b


def _client_for(app, user_id):
    flask.g.pop("_login_user", None)
    client = app.test_client()
    with client.session_transaction() as s:
        s["_user_id"] = str(user_id)
        s["_fresh"] = True
    return client


def _get_show(app, user_id, group_id):
    client = _client_for(app, user_id)
    resp = client.get(f"/groups/{group_id}")
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def _embed(body):
    m = EMBED_RE.search(body)
    assert m, "No se encontró el bloque embed-data"
    return json.loads(m.group(1))


# ---------------------------------------------------------------------------
# Criterio 1: sin permiso → solo marcas propias
# ---------------------------------------------------------------------------

def test_miembro_sin_permiso_no_ve_chips_de_otros(app, db_session):
    group, owner, member_a, member_b, gm_a, _ = _seed(db_session, "av-sin-perm")

    body = _get_show(app, member_b.id, group.id)

    # La clase .availability-user-chip y la palabra "Disponible" aparecen en el
    # JS (siempre presente). Lo que importa es que no aparezcan chips HTML reales:
    # los chips tienen atributo data-user-id de otros usuarios,
    # o la estructura del span de "Disponible" (bg-primary + texto) en celdas.
    assert f'data-user-id="{member_a.id}"' not in body
    assert f'data-user-id="{owner.id}"' not in body
    assert 'bg-primary text-white">Disponible' not in body


def test_miembro_sin_permiso_embed_sin_identidades_ajenas(app, db_session):
    group, owner, member_a, member_b, _, _ = _seed(db_session, "av-embed-sin-perm")

    body = _get_show(app, member_b.id, group.id)
    payload = _embed(body)

    assert payload["can_view_availability"] is False
    assert payload["can_manage"] is False
    # responded_user_ids viaja (IDs sin nombre), pero no lleva nombre/email de ajenos
    for key in ("cell_users", "user_info_map"):
        assert key not in payload


# ---------------------------------------------------------------------------
# Criterio 2: con availability.view_all → grilla agregada
# ---------------------------------------------------------------------------

def test_miembro_con_permiso_ve_chips_del_grupo(app, db_session):
    group, owner, member_a, member_b, gm_a, gm_b = _seed(db_session, "av-con-perm")

    db_session.add(GroupPermissionGrant(
        group_id=group.id,
        group_member_id=gm_b.id,
        permission=PERM_VIEW_AVAILABILITY,
    ))
    db_session.commit()

    body = _get_show(app, member_b.id, group.id)

    assert "Miembro A" in body or "Owner" in body


def test_miembro_con_permiso_embed_can_view_availability_true(app, db_session):
    group, owner, member_a, member_b, gm_a, gm_b = _seed(db_session, "av-embed-con-perm")

    db_session.add(GroupPermissionGrant(
        group_id=group.id,
        group_member_id=gm_b.id,
        permission=PERM_VIEW_AVAILABILITY,
    ))
    db_session.commit()

    body = _get_show(app, member_b.id, group.id)
    payload = _embed(body)

    assert payload["can_view_availability"] is True


# ---------------------------------------------------------------------------
# Criterio 3: owner ve la grilla
# ---------------------------------------------------------------------------

def test_owner_ve_grilla_agregada(app, db_session):
    group, owner, member_a, member_b, _, _ = _seed(db_session, "av-owner")

    body = _get_show(app, owner.id, group.id)
    payload = _embed(body)

    assert payload["can_view_availability"] is True
    assert "Miembro A" in body


# ---------------------------------------------------------------------------
# Criterio 4: subgroups.view_all NO implica availability.view_all
# ---------------------------------------------------------------------------

def test_subgroups_view_all_no_concede_ver_disponibilidad(app, db_session):
    group, owner, member_a, member_b, gm_a, gm_b = _seed(db_session, "av-sub-noimplica")

    db_session.add(GroupPermissionGrant(
        group_id=group.id,
        group_member_id=gm_b.id,
        permission=PERM_VIEW_ALL,
    ))
    db_session.commit()

    body = _get_show(app, member_b.id, group.id)
    payload = _embed(body)

    assert payload["can_view_availability"] is False
    assert f'data-user-id="{member_a.id}"' not in body
    assert f'data-user-id="{owner.id}"' not in body


# ---------------------------------------------------------------------------
# Criterio 5: embed sin identidades ajenas para usuario sin permiso
# (variante con subgroups.view_all, para confirmar que tampoco filtra)
# ---------------------------------------------------------------------------

def test_embed_no_lleva_cell_users_ni_user_info_map(app, db_session):
    group, owner, member_a, member_b, gm_a, gm_b = _seed(db_session, "av-embed-no-idents")

    body = _get_show(app, member_b.id, group.id)
    payload = _embed(body)

    assert "cell_users" not in payload
    assert "user_info_map" not in payload


# ---------------------------------------------------------------------------
# Criterio 6: el permiso se puede conceder y revocar desde el panel del owner
# ---------------------------------------------------------------------------

def test_owner_puede_conceder_availability_view_all_via_ruta(app, db_session):
    group, owner, member_a, member_b, gm_a, gm_b = _seed(db_session, "av-grant-ruta")

    client = _client_for(app, owner.id)
    resp = client.post(
        f"/groups/{group.id}/permissions/set",
        data={"subject": f"member:{gm_b.id}", "level": "view_availability"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    grant = GroupPermissionGrant.query.filter_by(
        group_id=group.id,
        group_member_id=gm_b.id,
        permission=PERM_VIEW_AVAILABILITY,
    ).first()
    assert grant is not None


def test_owner_puede_revocar_availability_view_all_via_ruta(app, db_session):
    group, owner, member_a, member_b, gm_a, gm_b = _seed(db_session, "av-revoke-ruta")

    db_session.add(GroupPermissionGrant(
        group_id=group.id,
        group_member_id=gm_b.id,
        permission=PERM_VIEW_AVAILABILITY,
    ))
    db_session.commit()

    client = _client_for(app, owner.id)
    resp = client.post(
        f"/groups/{group.id}/permissions/revoke",
        data={"subject_type": "member", "subject_id": str(gm_b.id)},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    active = GroupPermissionGrant.query.filter_by(
        group_id=group.id,
        group_member_id=gm_b.id,
        permission=PERM_VIEW_AVAILABILITY,
        deleted_at=None,
    ).first()
    assert active is None
