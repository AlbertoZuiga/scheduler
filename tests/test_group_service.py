"""Operaciones de dominio de grupo, ejercitadas sin pasar por las rutas."""

# pylint: disable=redefined-outer-name
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
from app.permissions import LEVEL_NONE, PERM_VIEW_AVAILABILITY, PERM_VIEW_OWN
from app.services import group_service as svc
from app.services.availability_service import active_member_user_ids

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def owner(db_session):
    user = User(name="Dueño", email="owner-gs@example.com")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def group(db_session, owner):
    grupo = Group(
        name="Grupo GS",
        owner_id=owner.id,
        join_token="tok-gs",
        start_minutes=480,
        end_minutes=600,
        block_minutes=60,
        active_weekdays="0,1",
    )
    db_session.add(grupo)
    db_session.commit()
    db_session.add(GroupMember(group_id=grupo.id, user_id=owner.id, role=RoleEnum.ADMIN))
    db_session.commit()
    return grupo


def _add_user(db_session, email):
    user = User(name=email, email=email)
    db_session.add(user)
    db_session.commit()
    return user


def _add_member(db_session, group, email, role=RoleEnum.MEMBER):
    user = _add_user(db_session, email)
    db_session.add(GroupMember(group_id=group.id, user_id=user.id, role=role))
    db_session.commit()
    return user


def _mark(db_session, group, user, weekday, minutes):
    row = Availability(group_id=group.id, weekday=weekday, start_minutes=minutes)
    db_session.add(row)
    db_session.flush()
    db_session.add(UserAvailability(user_id=user.id, availability_id=row.id))
    db_session.commit()
    return row


# ---------------------------------------------------------------------------
# create_group
# ---------------------------------------------------------------------------


def test_create_group_crea_grupo_y_membresia_admin(db_session, owner):
    grupo = svc.create_group("Nuevo Grupo", owner.id)
    db_session.commit()

    assert grupo.id is not None
    assert grupo.name == "Nuevo Grupo"
    assert grupo.owner_id == owner.id
    assert grupo.join_token

    membership = GroupMember.query.filter_by(group_id=grupo.id, user_id=owner.id).first()
    assert membership is not None
    assert membership.role == RoleEnum.ADMIN


def test_create_group_no_commitea_solo(db_session, owner):
    svc.create_group("Rollback Grupo", owner.id)
    scheduler_db.session.rollback()

    assert Group.query.filter_by(name="Rollback Grupo").first() is None


# ---------------------------------------------------------------------------
# rotate_join_token
# ---------------------------------------------------------------------------


def test_rotate_join_token_cambia_el_token(db_session, group):
    old_token = group.join_token
    svc.rotate_join_token(group)
    db_session.commit()

    assert group.join_token != old_token
    assert group.join_token


# ---------------------------------------------------------------------------
# join_group
# ---------------------------------------------------------------------------


def test_join_group_crea_membresia_nueva(db_session, group):
    user = _add_user(db_session, "nuevo@example.com")
    membership = svc.join_group(group, user.id)
    db_session.commit()

    assert membership.group_id == group.id
    assert membership.user_id == user.id
    assert membership.role == RoleEnum.MEMBER


def test_join_group_restaura_membresia_removida(db_session, group):
    user = _add_user(db_session, "exmember@example.com")
    db_session.add(GroupMember(group_id=group.id, user_id=user.id, role=RoleEnum.MEMBER))
    db_session.commit()
    GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first().soft_delete()
    db_session.commit()

    membership = svc.join_group(group, user.id)
    db_session.commit()

    assert membership.deleted_at is None
    assert membership.role == RoleEnum.MEMBER
    # No se crea una fila nueva: la membresía es la misma fila restaurada.
    count = GroupMember.query.filter_by(group_id=group.id, user_id=user.id).count()
    assert count == 1


def test_join_group_degrada_admin_removido_a_member(db_session, group):
    user = _add_user(db_session, "exadmin@example.com")
    db_session.add(GroupMember(group_id=group.id, user_id=user.id, role=RoleEnum.ADMIN))
    db_session.commit()
    GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first().soft_delete()
    db_session.commit()

    membership = svc.join_group(group, user.id)
    db_session.commit()

    assert membership.role == RoleEnum.MEMBER


# ---------------------------------------------------------------------------
# leave_group
# ---------------------------------------------------------------------------


def test_leave_group_oculta_membresia(db_session, group, owner):
    user = _add_member(db_session, group, "saliente@example.com")

    svc.leave_group(group, user.id)
    db_session.commit()

    membership = GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first()
    assert membership is None


def test_leave_group_sin_membresia_devuelve_none(db_session, group):
    stranger = _add_user(db_session, "stranger@example.com")
    result = svc.leave_group(group, stranger.id)
    assert result is None


def test_leave_group_transfiere_ownership_al_irse_el_duenio(db_session, group, owner):
    otro = _add_member(db_session, group, "otro@example.com")

    svc.leave_group(group, owner.id)
    db_session.commit()

    assert group.owner_id == otro.id


def test_leave_group_borra_grupo_si_era_el_ultimo(db_session, group, owner):
    svc.leave_group(group, owner.id)
    db_session.commit()

    assert group.is_deleted


# ---------------------------------------------------------------------------
# update_member_role
# ---------------------------------------------------------------------------


def test_update_member_role_cambia_el_rol(db_session, group, owner):
    user = _add_member(db_session, group, "target-rol@example.com")

    svc.update_member_role(group, user.id, "ADMIN", owner)
    db_session.commit()

    membership = GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first()
    assert membership.role == RoleEnum.ADMIN


# ---------------------------------------------------------------------------
# get_responded_user_ids
# ---------------------------------------------------------------------------


def test_get_responded_user_ids_retorna_quienes_respondieron(db_session, group, owner):
    user = _add_member(db_session, group, "resp@example.com")
    _mark(db_session, group, user, 0, 480)
    visible = active_member_user_ids(group.id)

    result = svc.get_responded_user_ids(group.id, visible)

    assert user.id in result
    assert owner.id not in result


def test_get_responded_user_ids_excluye_usuario_fuera_del_scope(db_session, group):
    user = _add_member(db_session, group, "scope-out@example.com")
    _mark(db_session, group, user, 0, 480)

    result = svc.get_responded_user_ids(group.id, set())
    assert result == set()


# ---------------------------------------------------------------------------
# get_member_availability_counts
# ---------------------------------------------------------------------------


def test_get_member_availability_counts_cuenta_por_usuario(db_session, group):
    a = _add_member(db_session, group, "a@example.com")
    b = _add_member(db_session, group, "b@example.com")
    _mark(db_session, group, a, 0, 480)
    _mark(db_session, group, a, 1, 480)
    _mark(db_session, group, b, 0, 540)  # slot distinto al de a

    counts = svc.get_member_availability_counts(group.id, [a.id, b.id])

    assert counts[a.id] == 2
    assert counts[b.id] == 1


def test_get_member_availability_counts_devuelve_vacio_sin_user_ids(db_session, group):
    result = svc.get_member_availability_counts(group.id, [])
    assert result == {}


# ---------------------------------------------------------------------------
# counts_by_model
# ---------------------------------------------------------------------------


def test_counts_by_model_retorna_conteo_por_grupo(db_session, owner):
    g1 = Group(name="g1", owner_id=owner.id, join_token="t1")
    g2 = Group(name="g2", owner_id=owner.id, join_token="t2")
    db_session.add_all([g1, g2])
    db_session.commit()
    db_session.add_all(
        [
            GroupMember(group_id=g1.id, user_id=owner.id, role=RoleEnum.ADMIN),
            GroupMember(group_id=g2.id, user_id=owner.id, role=RoleEnum.ADMIN),
        ]
    )
    db_session.commit()

    counts = svc.counts_by_model(GroupMember, [g1.id, g2.id])

    assert counts[g1.id] == 1
    assert counts[g2.id] == 1


def test_counts_by_model_devuelve_vacio_para_lista_vacia(db_session):
    assert svc.counts_by_model(GroupMember, []) == {}


# ---------------------------------------------------------------------------
# apply_permission_level
# ---------------------------------------------------------------------------


def _grant(db_session, group, member, permission):
    g = GroupPermissionGrant(group_id=group.id, group_member_id=member.id, permission=permission)
    db_session.add(g)
    db_session.commit()
    return g


def _member_obj(db_session, group, email, role=RoleEnum.MEMBER):
    user = _add_user(db_session, email)
    m = GroupMember(group_id=group.id, user_id=user.id, role=role)
    db_session.add(m)
    db_session.commit()
    return m


def test_apply_permission_level_crea_permisos_nuevos(db_session, group, owner):
    member = _member_obj(db_session, group, "perm-new@example.com")

    svc.apply_permission_level(group, "member", member.id, "view_own", False, owner)
    db_session.commit()

    grants = GroupPermissionGrant.query.filter_by(
        group_id=group.id, group_member_id=member.id
    ).all()
    permissions = {g.permission for g in grants}
    assert PERM_VIEW_OWN in permissions


def test_apply_permission_level_incluye_availability_si_checked(db_session, group, owner):
    member = _member_obj(db_session, group, "perm-avail@example.com")

    svc.apply_permission_level(group, "member", member.id, "view_own", True, owner)
    db_session.commit()

    grants = GroupPermissionGrant.query.filter_by(
        group_id=group.id, group_member_id=member.id
    ).all()
    permissions = {g.permission for g in grants}
    assert PERM_VIEW_AVAILABILITY in permissions


def test_apply_permission_level_revoca_permisos_no_deseados(db_session, group, owner):
    member = _member_obj(db_session, group, "perm-revoke@example.com")
    _grant(db_session, group, member, PERM_VIEW_OWN)

    svc.apply_permission_level(group, "member", member.id, LEVEL_NONE, False, owner)
    db_session.commit()

    active = GroupPermissionGrant.query.filter_by(
        group_id=group.id, group_member_id=member.id
    ).all()
    assert active == []


def test_apply_permission_level_restaura_grant_soft_deleted(db_session, group, owner):
    member = _member_obj(db_session, group, "perm-restore@example.com")
    grant = _grant(db_session, group, member, PERM_VIEW_OWN)
    grant.soft_delete()
    db_session.commit()

    svc.apply_permission_level(group, "member", member.id, "view_own", False, owner)
    db_session.commit()

    active = GroupPermissionGrant.query.filter_by(
        group_id=group.id, group_member_id=member.id
    ).all()
    assert any(g.permission == PERM_VIEW_OWN for g in active)
    total = (
        GroupPermissionGrant.query.execution_options(include_deleted=True)
        .filter_by(group_id=group.id, group_member_id=member.id, permission=PERM_VIEW_OWN)
        .count()
    )
    assert total == 1


# ---------------------------------------------------------------------------
# revoke_all_permissions
# ---------------------------------------------------------------------------


def test_revoke_all_permissions_oculta_todos_los_grants(db_session, group, owner):
    member = _member_obj(db_session, group, "perm-rall@example.com")
    _grant(db_session, group, member, PERM_VIEW_OWN)

    revoked = svc.revoke_all_permissions(group, "member", member.id, owner)
    db_session.commit()

    assert len(revoked) == 1
    active = GroupPermissionGrant.query.filter_by(
        group_id=group.id, group_member_id=member.id
    ).all()
    assert active == []


def test_revoke_all_permissions_sin_grants_no_falla(db_session, group, owner):
    member = _member_obj(db_session, group, "perm-empty@example.com")

    revoked = svc.revoke_all_permissions(group, "member", member.id, owner)
    db_session.commit()

    assert revoked == []
