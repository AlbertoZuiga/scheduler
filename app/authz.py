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


def get_group_or_404(group_id: int) -> Group:
    return Group.query.get_or_404(group_id)


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
        scheduler_db.session.delete(target_membership)
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

    scheduler_db.session.delete(target_membership)
