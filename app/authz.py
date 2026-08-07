"""Helpers centralizados de autorización y control de acceso.

Proveen funciones reutilizables para validar pertenencia/roles
antes de acceder o modificar recursos sensibles.
"""
from __future__ import annotations

from typing import Tuple

from flask import abort, flash
from flask_login import current_user

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
    return active_or_404(Group.query.get(group_id))


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
