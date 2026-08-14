"""Operaciones de dominio de grupo.

Extraído de `group_routes.py` (BE-007). Ninguna función commitea:
la transacción la maneja la ruta que llama.
"""

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import scheduler_db
from app.models import (
    Availability,
    Category,
    Group,
    GroupMember,
    GroupMemberCategory,
    GroupPermissionGrant,
    RoleEnum,
    UserAvailability,
)
from app.models.group import generate_join_token
from app.models.subgroup import SubGroup
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
from app.soft_delete import INCLUDE_DELETED, find_soft_deleted, restore_batch


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
    """{group_id: filas activas de `model`} en una sola consulta agregada.

    Un GROUP BY en vez de |length sobre las relaciones lazy: |length cargaba
    miembros y categorías completos de cada grupo (dos SELECT por fila) solo
    para contarlos.
    """
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
    """Conteo de bloques disponibles por usuario. Usado en el CSV export.

    Un GROUP BY para todo el grupo en vez de un COUNT por miembro: antes el
    export era O(miembros) consultas.
    """
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


def get_groups_for_user(user_id):
    """Grupos de los que el usuario es miembro, ordenados por nombre."""
    return (
        Group.query.join(GroupMember)
        .filter(GroupMember.user_id == user_id)
        .order_by(Group.name.asc(), Group.id.asc())
        .all()
    )


def get_admin_group_ids(user_id):
    """IDs de grupos donde el usuario tiene rol ADMIN."""
    memberships = GroupMember.query.filter_by(user_id=user_id, role=RoleEnum.ADMIN).all()
    return {m.group_id for m in memberships}


def get_trash_count(user_id):
    """Cantidad de grupos en papelera del usuario (soft-deleted)."""
    return (
        Group.query.execution_options(**{INCLUDE_DELETED: True})
        .filter(Group.deleted_at.isnot(None), Group.owner_id == user_id)
        .count()
    )


def get_group_members(group_id, limit=500):
    """Miembros activos con user y categories cargados, ordenados por id.

    El selectinload previene dos SELECT por miembro: la vista recorre
    `member.user` y `member.categories` de todos los miembros.
    """
    return (
        GroupMember.query.filter_by(group_id=group_id)
        .options(selectinload(GroupMember.user), selectinload(GroupMember.categories))
        .order_by(GroupMember.id.asc())
        .limit(limit)
        .all()
    )


def get_removed_members(group_id, limit=500):
    """Miembros soft-deleted del grupo, ordenados por fecha de borrado desc."""
    return (
        GroupMember.query.execution_options(**{INCLUDE_DELETED: True})
        .options(selectinload(GroupMember.user))
        .filter(GroupMember.group_id == group_id, GroupMember.deleted_at.isnot(None))
        .order_by(GroupMember.deleted_at.desc(), GroupMember.id.desc())
        .limit(limit)
        .all()
    )


def get_user_availability_data(group_id, user_ids):
    """(user_id, weekday, start_minutes) para los usuarios dados.

    user_ids puede ser un int (un solo usuario) o un iterable de ints.
    """
    q = (
        scheduler_db.session.query(
            UserAvailability.user_id, Availability.weekday, Availability.start_minutes
        )
        .join(Availability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
    )
    if isinstance(user_ids, int):
        return q.filter(UserAvailability.user_id == user_ids).all()
    return q.filter(UserAvailability.user_id.in_(user_ids)).all()


def get_group_categories(group_id):
    """Categorías activas del grupo."""
    return Category.query.filter_by(group_id=group_id).all()


def get_category_member_counts(category_ids):
    """Conteo de miembros por categoría. Devuelve {category_id: count}.

    category_ids debe ser ya filtrado por grupo: la query no verifica pertenencia.
    """
    if not category_ids:
        return {}
    return dict(
        scheduler_db.session.query(
            GroupMemberCategory.category_id, func.count(GroupMemberCategory.id)
        )
        .filter(GroupMemberCategory.category_id.in_(list(category_ids)))
        .group_by(GroupMemberCategory.category_id)
        .all()
    )


def get_group_members_for_export(group_id):
    """Miembros con user y categoría/category para el CSV export."""
    return (
        GroupMember.query.filter_by(group_id=group_id)
        .options(
            selectinload(GroupMember.user),
            selectinload(GroupMember.categories).selectinload(GroupMemberCategory.category),
        )
        .order_by(GroupMember.id.asc())
        .all()
    )


def get_deleted_groups_for_user(user_id, limit=200):
    """Grupos en papelera del usuario, ordenados por fecha de borrado desc."""
    return (
        Group.query.execution_options(**{INCLUDE_DELETED: True})
        .filter(Group.deleted_at.isnot(None), Group.owner_id == user_id)
        .order_by(Group.deleted_at.desc(), Group.id.desc())
        .limit(limit)
        .all()
    )


def get_group_including_deleted(group_id):
    """Busca un grupo incluyendo los soft-deleted."""
    return (
        Group.query.execution_options(**{INCLUDE_DELETED: True})
        .filter(Group.id == group_id)
        .first()
    )


def get_group_by_token(token):
    """Busca un grupo activo por su join_token."""
    return Group.query.filter_by(join_token=token).first()


def get_group_member(group_id, user_id):
    """Busca la membresía activa de un usuario en un grupo."""
    return GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()


def get_group_member_by_id(member_id, group_id):
    """Busca un GroupMember activo por id y group_id."""
    return GroupMember.query.filter_by(id=member_id, group_id=group_id).first()


def get_category(category_id, group_id):
    """Busca una categoría activa por id y group_id."""
    return Category.query.filter_by(id=category_id, group_id=group_id).first()


def get_group_members_with_users(group_id):
    """Todos los miembros activos del grupo con su user cargado (sin límite)."""
    return (
        GroupMember.query.filter_by(group_id=group_id)
        .options(selectinload(GroupMember.user))
        .all()
    )


def get_subgroups_for_show(group_id, scope_user_ids, current_user_id):
    """Subgrupos y mapas para la vista show del grupo.

    Devuelve (group_subgroups, user_subgroup_map).
    Con scope_user_ids no None, filtra a los subgrupos que contienen al usuario.
    """
    subgroups = (
        SubGroup.query.filter_by(parent_group_id=group_id)
        .options(selectinload(SubGroup.members))
        .order_by(SubGroup.created_at.desc(), SubGroup.id.asc())
        .all()
    )
    group_subgroups = []
    user_subgroup_map = {}
    for subgroup in subgroups:
        member_ids = [
            m.user_id for m in subgroup.members
            if scope_user_ids is None or m.user_id in scope_user_ids
        ]
        if scope_user_ids is not None and current_user_id not in member_ids:
            continue
        group_subgroups.append({
            "id": subgroup.id,
            "name": subgroup.name,
            "member_count": len(member_ids),
        })
        for user_id in member_ids:
            user_subgroup_map.setdefault(user_id, []).append(subgroup.id)
    return group_subgroups, user_subgroup_map
