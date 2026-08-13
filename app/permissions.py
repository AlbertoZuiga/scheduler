"""Permisos extra sobre subgrupos, otorgables a una persona o a una categoría.

Estos permisos son un tercer nivel de autoridad, por debajo de owner/admin de
grupo: abren la pantalla de subgrupos (verla, editarla) sin dar acceso nunca a
`/groups/<id>/members` ni a la administración de categorías, que siguen siendo
exclusivas de `require_group_admin_or_owner` (ver app/authz.py).
"""
from __future__ import annotations

from app.extensions import scheduler_db
from app.models import GroupPermissionGrant, RoleEnum

PERM_VIEW_OWN = "subgroups.view_own"
PERM_VIEW_ALL = "subgroups.view_all"
PERM_EDIT_OWN = "subgroups.edit_own"
PERM_EDIT_ALL = "subgroups.edit_all"
PERM_VIEW_AVAILABILITY = "availability.view_all"

ALL_PERMISSIONS = {PERM_VIEW_OWN, PERM_VIEW_ALL, PERM_EDIT_OWN, PERM_EDIT_ALL, PERM_VIEW_AVAILABILITY}

# Qué otros permisos trae implícitos cada uno, para que la UI y el resolver
# no tengan que evaluar combinaciones sueltas.
# PERM_VIEW_AVAILABILITY es independiente del retículo de subgrupos: tener
# subgroups.view_all / subgroups.edit_all NO lo implica.
IMPLIES = {
    PERM_VIEW_OWN: {PERM_VIEW_OWN},
    PERM_VIEW_ALL: {PERM_VIEW_ALL, PERM_VIEW_OWN},
    PERM_EDIT_OWN: {PERM_EDIT_OWN, PERM_VIEW_OWN},
    PERM_EDIT_ALL: {PERM_EDIT_ALL, PERM_VIEW_ALL, PERM_EDIT_OWN, PERM_VIEW_OWN},
    PERM_VIEW_AVAILABILITY: {PERM_VIEW_AVAILABILITY},
}

# Un nivel es un conjunto canónico de permisos otorgables. Son los únicos 6
# conjuntos distintos que produce el retículo IMPLIES; el resto son
# combinaciones redundantes que la UI no necesita ofrecer.
LEVELS = [
    ("view_own", "Ver su subgrupo", {PERM_VIEW_OWN}),
    ("edit_own", "Ver y modificar su subgrupo", {PERM_EDIT_OWN}),
    ("view_all", "Ver todos los subgrupos", {PERM_VIEW_ALL}),
    ("view_all_edit_own", "Ver todos, modificar el suyo", {PERM_VIEW_ALL, PERM_EDIT_OWN}),
    ("edit_all", "Ver y modificar todos", {PERM_EDIT_ALL}),
    ("view_availability", "Ver los horarios del grupo", {PERM_VIEW_AVAILABILITY}),
]

LEVEL_PERMISSIONS = {key: perms for key, _, perms in LEVELS}
LEVEL_LABELS = {key: label for key, label, _ in LEVELS}
LEVEL_ORDER = [key for key, _, _ in LEVELS]


def level_of(raw_permissions) -> str | None:
    """Nivel al que corresponde un conjunto de permisos directos, o None.

    Compara por permisos efectivos. Si el conjunto no calza exacto con ningún
    nivel (combinación escrita a mano o heredada), devuelve el nivel de mayor
    cobertura contenido en él.
    """
    raw = set(raw_permissions)
    if not raw:
        return None
    effective = expand(raw)
    for key, _, perms in LEVELS:
        if expand(perms) == effective:
            return key
    best_key, best_size = None, -1
    for key, _, perms in LEVELS:
        if expand(perms) <= effective and len(perms) > best_size:
            best_key, best_size = key, len(perms)
    return best_key


def expand(raw_permissions) -> set[str]:
    """Un conjunto de permisos concedidos directamente, con sus implícitos."""
    expanded = set()
    for perm in raw_permissions:
        expanded |= IMPLIES.get(perm, {perm})
    return expanded


def effective_permissions(group, membership) -> set[str]:
    """Permisos efectivos de `membership` sobre los subgrupos de `group`.

    Owner y admin de grupo tienen los 4 implícitamente. El resto solo tiene lo
    que le fue concedido directamente o a través de sus categorías actuales
    (evaluación dinámica: entrar/salir de la categoría cambia el resultado en
    el siguiente request, sin snapshot).
    """
    if membership is None:
        return set()
    if group.owner_id == membership.user_id or membership.role == RoleEnum.ADMIN:
        return set(ALL_PERMISSIONS)

    category_ids = [assoc.category_id for assoc in membership.categories]
    subject_filter = [GroupPermissionGrant.group_member_id == membership.id]
    if category_ids:
        subject_filter.append(GroupPermissionGrant.category_id.in_(category_ids))

    grants = GroupPermissionGrant.query.filter(
        GroupPermissionGrant.group_id == group.id,
        scheduler_db.or_(*subject_filter),
    ).all()
    return expand(grant.permission for grant in grants)


def grant_sources(group) -> dict:
    """Concesiones directas y vía categoría del grupo, agrupadas por sujeto.

    Devuelve {'members': {group_member_id: {permission, ...}}, 'categories':
    {category_id: {permission, ...}}}, para que la UI de administración pinte
    la matriz sin una query por fila.
    """
    grants = GroupPermissionGrant.query.filter_by(group_id=group.id).all()
    result = {"members": {}, "categories": {}}
    for grant in grants:
        if grant.group_member_id is not None:
            result["members"].setdefault(grant.group_member_id, set()).add(grant.permission)
        elif grant.category_id is not None:
            result["categories"].setdefault(grant.category_id, set()).add(grant.permission)
    return result
