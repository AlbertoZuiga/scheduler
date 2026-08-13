"""Helpers centralizados de autorización y control de acceso.

Proveen funciones reutilizables para validar pertenencia/roles
antes de acceder o modificar recursos sensibles.
"""
from __future__ import annotations

from typing import Tuple

from flask import abort, flash
from flask_login import current_user

from app.extensions import scheduler_db
from app.models import Group, GroupMember, RoleEnum
from app.models.subgroup import SubGroup, SubGroupMember
from app.permissions import (
    PERM_EDIT_ALL,
    PERM_EDIT_OWN,
    PERM_VIEW_ALL,
    PERM_VIEW_OWN,
    effective_permissions,
)
from app.soft_delete import active_or_404


def get_group_or_404(group_id: int) -> Group:
    # `query.get` resuelve por identity map y esquiva el filtro de borrado lógico.
    return active_or_404(scheduler_db.session.get(Group, group_id))


def get_membership(group_id: int, user_id: int):
    return GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()


def require_group_member(group_id: int) -> Tuple[Group, GroupMember]:
    """Asegura que el usuario autenticado pertenece al grupo.

    Devuelve (group, membership). Aborta con 403 si no es miembro.
    """
    group = get_group_or_404(group_id)
    membership = get_membership(group_id, current_user.id)
    if not membership:
        flash("No perteneces a este grupo.", "danger")
        abort(403)
    return group, membership


def require_group_admin_or_owner(group_id: int) -> Tuple[Group, GroupMember]:
    """Verifica que el usuario sea owner o admin del grupo."""
    group, membership = require_group_member(group_id)
    if not (group.owner_id == current_user.id or membership.role == RoleEnum.ADMIN):
        flash("No tienes permisos suficientes para esta acción.", "danger")
        abort(403)
    return group, membership


def require_group_permission(group_id: int, permission: str) -> Tuple[Group, GroupMember, set]:
    """Verifica que el usuario tenga `permission` (directo, por categoría, o
    por ser owner/admin) sobre los subgrupos del grupo.

    Devuelve (group, membership, perms) para que la vista reutilice el set de
    permisos efectivos sin recalcularlo.
    """
    group, membership = require_group_member(group_id)
    perms = effective_permissions(group, membership)
    if permission not in perms:
        flash("No tienes permisos suficientes para esta acción.", "danger")
        abort(403)
    return group, membership, perms


def require_subgroup_access(group_id: int, subgroup_id: int, *, edit: bool):
    """Verifica acceso a un subgrupo puntual, propio o de todo el grupo.

    Con el permiso "_all" alcanza cualquier subgrupo; con el "_own" el
    usuario debe pertenecer activamente a `subgroup_id`.
    """
    perm_own = PERM_EDIT_OWN if edit else PERM_VIEW_OWN
    perm_all = PERM_EDIT_ALL if edit else PERM_VIEW_ALL

    group, membership = require_group_member(group_id)
    perms = effective_permissions(group, membership)
    subgroup = SubGroup.query.filter_by(id=subgroup_id, parent_group_id=group_id).first_or_404()

    if perm_all in perms:
        return group, membership, subgroup, perms

    if perm_own in perms:
        belongs = SubGroupMember.query.filter_by(
            subgroup_id=subgroup_id, user_id=current_user.id
        ).first()
        if belongs:
            return group, membership, subgroup, perms

    flash("No tienes permisos suficientes para esta acción.", "danger")
    abort(403)


def require_group_owner(group_id: int) -> Tuple[Group, GroupMember]:
    group, membership = require_group_member(group_id)
    if group.owner_id != current_user.id:
        flash("Solo el propietario del grupo puede realizar esta acción.", "danger")
        abort(403)
    return group, membership


def can_see_member_emails(group: Group, membership) -> bool:
    """El email de los demás es dato de administración: solo owner/admin.

    Mismo criterio que `groups.export_members_csv` y la vista de subgrupos: los
    permisos de subgrupos, incluso los de edición, no abren los emails. El email
    propio no pasa por acá (cada quien ve el suyo).
    """
    if membership is None:
        return False
    return group.owner_id == membership.user_id or membership.role == RoleEnum.ADMIN


def display_name(user, *, with_email: bool) -> str:
    """Nombre a mostrar de un usuario sin nombre propio.

    Sin permiso para ver emails, el fallback no puede ser el email: filtraría
    justo lo que se está ocultando.
    """
    if user is None:
        return "Usuario desconocido"
    name = (user.name or "").strip()
    if name:
        return name
    return user.email if with_email else f"Usuario #{user.id}"


def safe_remove_member(group_id: int, user_id: int):
    """Elimina un miembro del grupo respetando reglas:
    - Solo owner o admin (admin no puede eliminar owner)
    - Un admin no puede eliminar a otro admin si no es owner
    """
    group, acting_membership = require_group_member(group_id)

    target_membership = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if not target_membership:
        flash("Miembro no encontrado en el grupo.", "warning")
        return

    # Owner siempre puede eliminar excepto a sí mismo (usar leave para eso)
    if group.owner_id == current_user.id:
        target_membership.soft_delete()
        return

    # Admin intentando eliminar
    if acting_membership.role != RoleEnum.ADMIN:
        flash("No tienes permisos para eliminar miembros.", "danger")
        abort(403)

    if group.owner_id == user_id:
        flash("No puedes eliminar al propietario del grupo.", "danger")
        abort(403)

    # Admin no puede eliminar otros admins (política)
    if target_membership.role == RoleEnum.ADMIN and acting_membership.user_id != group.owner_id:
        flash("No puedes eliminar a otro administrador.", "danger")
        abort(403)

    target_membership.soft_delete()
