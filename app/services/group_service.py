"""Operaciones de dominio de grupo.

Extraído de `group_routes.py` (BE-007). Ninguna función commitea:
la transacción la maneja la ruta que llama.
"""

from sqlalchemy import func

from app.extensions import scheduler_db
from app.models import (
    Availability,
    Category,
    Group,
    GroupMember,
    GroupPermissionGrant,
    RoleEnum,
    UserAvailability,
)
from app.models.group import generate_join_token
from app.models.audit_log import (
    ACTION_PERMISSION_GRANTED,
    ACTION_PERMISSION_REVOKED,
    ACTION_ROLE_CHANGED,
    record_action,
)
from app.permissions import (
    LEVEL_PERMISSIONS,
    PERM_VIEW_AVAILABILITY,
)
from app.soft_delete import find_soft_deleted, restore_batch


# ---------------------------------------------------------------------------
# group lifecycle
# ---------------------------------------------------------------------------


def create_group(name, owner_id):
    """Crea el grupo y agrega al dueño como miembro ADMIN. No commitea."""
    new_group = Group(name=name, join_token=generate_join_token(), owner_id=owner_id)
    scheduler_db.session.add(new_group)
    scheduler_db.session.flush()
    scheduler_db.session.add(
        GroupMember(group_id=new_group.id, user_id=owner_id, role=RoleEnum.ADMIN)
    )
    return new_group


def rotate_join_token(group):
    """Regenera el join_token del grupo. No commitea."""
    group.join_token = generate_join_token()


def join_group(group, user_id):
    """Une al usuario al grupo.

    Si fue removido previamente, restaura la membresía y la degrada a MEMBER.
    Si es la primera vez, crea una nueva. No commitea.
    """
    removed = find_soft_deleted(GroupMember, group_id=group.id, user_id=user_id)
    if removed:
        restore_batch(removed)
        removed.role = RoleEnum.MEMBER
        return removed
    membership = GroupMember(group_id=group.id, user_id=user_id, role=RoleEnum.MEMBER)
    scheduler_db.session.add(membership)
    return membership


def leave_group(group, user_id):
    """El usuario abandona el grupo.

    Si era el dueño, transfiere el ownership al primer miembro restante.
    Si era el último miembro, oculta el grupo (soft-delete).
    Devuelve la membresía, o None si el usuario no era miembro. No commitea.
    """
    membership = GroupMember.query.filter_by(user_id=user_id, group_id=group.id).first()
    if not membership:
        return None
    membership.soft_delete()
    if group.owner_id == user_id:
        remaining = GroupMember.query.filter_by(group_id=group.id).all()
        if remaining:
            group.owner_id = remaining[0].user_id
        else:
            group.soft_delete()
    return membership


# ---------------------------------------------------------------------------
# roles & permissions
# ---------------------------------------------------------------------------


def update_member_role(group, user_id, role_str, actor):
    """Actualiza el rol de un miembro y registra la acción en la bitácora.

    No commitea. Delega en first_or_404 si el miembro no existe.
    """
    member = GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first_or_404()
    prev_role = member.role.name if member.role is not None else None
    member.role = RoleEnum[role_str]
    record_action(
        group_id=group.id,
        actor=actor,
        action=ACTION_ROLE_CHANGED,
        subject_type="member",
        subject_id=member.id,
        detail={"from": prev_role, "to": role_str},
    )
    return member


def apply_permission_level(group, subject_type, subject_id, level, availability_checked, actor):
    """Otorga o actualiza permisos de subgrupo y disponibilidad.

    Oculta los permisos que ya no aplican, restaura o crea los que faltan,
    y registra la acción en la bitácora. No commitea.
    """
    wanted_subgroup = LEVEL_PERMISSIONS[level]
    wanted_availability = {PERM_VIEW_AVAILABILITY} if availability_checked else set()
    wanted = wanted_subgroup | wanted_availability

    if subject_type == "member":
        subject_filters = {"group_member_id": subject_id}
    else:
        subject_filters = {"category_id": subject_id}

    existing = GroupPermissionGrant.query.filter_by(group_id=group.id, **subject_filters).all()
    existing_permissions = {grant.permission for grant in existing}

    for grant in existing:
        if grant.permission not in wanted:
            grant.soft_delete()

    for permission in wanted - existing_permissions:
        filters = {"group_id": group.id, "permission": permission, **subject_filters}
        hidden = find_soft_deleted(GroupPermissionGrant, **filters)
        if hidden:
            hidden.restore()
        else:
            scheduler_db.session.add(GroupPermissionGrant(**filters))

    action = ACTION_PERMISSION_GRANTED if wanted else ACTION_PERMISSION_REVOKED
    record_action(
        group_id=group.id,
        actor=actor,
        action=action,
        subject_type=subject_type,
        subject_id=subject_id,
        detail={"level": level, "permissions": sorted(wanted)},
    )
    return wanted


def revoke_all_permissions(group, subject_type, subject_id, actor):
    """Quita todos los permisos directos de una persona o categoría.

    Registra la acción en la bitácora solo si había permisos que revocar.
    Devuelve la lista de grants revocados. No commitea.
    """
    if subject_type == "member":
        subject_filters = {"group_member_id": subject_id}
    else:
        subject_filters = {"category_id": subject_id}

    grants = GroupPermissionGrant.query.filter_by(group_id=group.id, **subject_filters).all()
    for grant in grants:
        grant.soft_delete()

    if grants:
        record_action(
            group_id=group.id,
            actor=actor,
            action=ACTION_PERMISSION_REVOKED,
            subject_type=subject_type,
            subject_id=subject_id,
            detail={"permissions": sorted(grant.permission for grant in grants)},
        )
    return grants


# ---------------------------------------------------------------------------
# reusable queries
# ---------------------------------------------------------------------------


def counts_by_model(model, group_ids):
    """{group_id: filas activas de `model`} en una sola consulta agregada."""
    if not group_ids:
        return {}
    return dict(
        scheduler_db.session.query(model.group_id, func.count(model.id))
        .filter(model.group_id.in_(group_ids))
        .group_by(model.group_id)
        .all()
    )


def get_responded_user_ids(group_id, visible_user_ids):
    """IDs de usuarios con al menos una marca de disponibilidad activa en el grupo."""
    return {
        user_id
        for (user_id,) in (
            scheduler_db.session.query(UserAvailability.user_id)
            .join(Availability, UserAvailability.availability_id == Availability.id)
            .filter(Availability.group_id == group_id)
            .filter(UserAvailability.user_id.in_(visible_user_ids))
            .distinct()
            .all()
        )
    }


def get_member_availability_counts(group_id, user_ids):
    """Conteo de bloques disponibles por usuario. Usado en el CSV export."""
    return dict(
        scheduler_db.session.query(
            UserAvailability.user_id, func.count(UserAvailability.id)
        )
        .join(Availability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
        .filter(UserAvailability.user_id.in_(user_ids))
        .group_by(UserAvailability.user_id)
        .all()
    )
