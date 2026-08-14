from flask import (
    Blueprint, current_app, request, jsonify, render_template, redirect, url_for, flash
)
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import scheduler_db
from app.models import Category, GroupMember, GroupMemberCategory, GroupPermissionGrant
from app.authz import (
    can_see_member_emails,
    display_name,
    require_group_member,
    require_group_admin_or_owner,
)
from app.soft_delete import active_or_404, find_soft_deleted, restore_batch


category_bp = Blueprint("categories", __name__, url_prefix="/categories")


DUPLICATE_MSG = "Ya existe una categoría con ese nombre."
NAME_REQUIRED_MSG = "El nombre de la categoría es requerido."
# Largo de la columna `Category.name` (String(150)): pasado ese punto el INSERT
# falla en la BD con DataError, así que se rechaza antes de llegar ahí.
NAME_MAX_LENGTH = 150
NAME_TOO_LONG_MSG = f"El nombre de la categoría no puede superar los {NAME_MAX_LENGTH} caracteres."
GROUP_CATEGORIES_ENDPOINT = "categories.group_categories"


def _json_or_flash(ok: bool, message: str, status: int = 200, redirect_to: str | None = None):
    """Helper para devolver JSON o hacer flash+redirect según Accept/Content-Type."""
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": ok, "message": message}), status
    if ok:
        flash(message, "success")
    elif 400 <= status < 500:
        flash(message, "warning")
    else:
        flash(message, "danger")
    if redirect_to:
        return redirect(redirect_to)
    return ("", status)


def _commit_or_duplicate(message, redirect_to, log_message, *log_args):
    """Commitea; devuelve una respuesta 409 si un unique de BD rechaza la fila.

    El chequeo previo en Python no cubre dos requests simultáneos: ahí el que
    pierde la carrera choca contra el unique parcial de categorías activas y sin esto vería
    un 500 crudo en vez del mismo mensaje de duplicado.
    """
    try:
        scheduler_db.session.commit()
        return None
    except IntegrityError:
        scheduler_db.session.rollback()
        current_app.logger.warning(log_message, *log_args)
        return _json_or_flash(False, message, 409, redirect_to)


def _category_exists(group_id: int, name: str) -> bool:
    return (
        Category.query.filter(Category.group_id == group_id)
        .filter(scheduler_db.func.lower(Category.name) == name.strip().lower())
        .first()
        is not None
    )


def _handle_create_category(group_id: int):
    require_group_admin_or_owner(group_id)
    name = request.form.get("name") or (request.is_json and request.json.get("name"))
    if not name:
        return _json_or_flash(False, NAME_REQUIRED_MSG, 400, url_for("groups.show", group_id=group_id))
    # Se mide el valor tal cual se inserta (sin strip): es lo que ve la columna.
    if len(name) > NAME_MAX_LENGTH:
        return _json_or_flash(
            False, NAME_TOO_LONG_MSG, 400, url_for(GROUP_CATEGORIES_ENDPOINT, group_id=group_id)
        )
    if _category_exists(group_id, name):
        return _json_or_flash(False, DUPLICATE_MSG, 409, url_for(GROUP_CATEGORIES_ENDPOINT, group_id=group_id))

    # Si existe una categoría eliminada con ese nombre, se restaura en vez de
    # crear una nueva: recupera de paso sus asignaciones a miembros.
    category = (
        Category.query.execution_options(include_deleted=True)
        .filter(Category.group_id == group_id, Category.deleted_at.isnot(None))
        .filter(scheduler_db.func.lower(Category.name) == name.strip().lower())
        .order_by(Category.deleted_at.desc())
        .first()
    )
    if category is not None:
        restore_batch(category)
    else:
        category = Category(group_id=group_id, name=name)
        scheduler_db.session.add(category)
    conflict = _commit_or_duplicate(
        DUPLICATE_MSG,
        url_for(GROUP_CATEGORIES_ENDPOINT, group_id=group_id),
        "categoría duplicada en carrera (group_id=%s)", group_id,
    )
    if conflict:
        return conflict
    if request.is_json:
        return jsonify({"ok": True, "id": category.id, "name": category.name}), 201
    flash("Categoría creada.", "success")
    return redirect(url_for(GROUP_CATEGORIES_ENDPOINT, group_id=group_id))


@category_bp.route("/group/<int:group_id>", methods=["GET", "POST"])
@login_required
def group_categories(group_id):
    # Only members can list; only admin/owner can create
    group, _ = require_group_member(group_id)

    if request.method == "POST":
        return _handle_create_category(group_id)

    categories = Category.query.filter_by(group_id=group_id).all()
    # If accessed from browser, render a small template or return JSON
    if request.accept_mimetypes.best == "text/html":
        return render_template("groups/categories.html", group=group, categories=categories)
    # Build counts and member ids per category
    cat_info = []
    for c in categories:
        member_ids = [assoc.group_member_id for assoc in GroupMemberCategory.query.filter_by(category_id=c.id).all()]
        cat_info.append({"id": c.id, "name": c.name, "member_ids": member_ids, "count": len(member_ids)})
    return jsonify(cat_info)


@category_bp.route("/group/<int:group_id>/<int:category_id>", methods=["DELETE"])
@login_required
def delete_category(group_id, category_id):
    """Elimina una categoría y todas sus asociaciones con miembros."""
    require_group_admin_or_owner(group_id)
    
    category = Category.query.filter_by(id=category_id, group_id=group_id).first_or_404()

    # Oculta la categoría y sus asignaciones; volver a crearla con el mismo
    # nombre las recupera.
    category.soft_delete()
    scheduler_db.session.commit()

    return jsonify({"ok": True, "message": "Categoría eliminada"}), 200


@category_bp.route("/group/<int:group_id>/check", methods=["GET"])
@login_required
def check_category_name(group_id):
    """Valida en tiempo real si el nombre está disponible dentro del grupo."""
    require_group_member(group_id)
    name = (request.args.get("name") or "").strip()
    if not name:
        return jsonify({"available": False, "message": "Nombre requerido"}), 400
    exists = (
        Category.query.filter(Category.group_id == group_id)
        .filter(scheduler_db.func.lower(Category.name) == name.lower())
        .first()
    )
    if exists:
        return jsonify({"available": False, "message": "Ya existe una categoría con ese nombre."}), 200
    return jsonify({"available": True, "message": "Disponible"}), 200


def _can_modify_member(group_owner_id, acting_role_name, gm_user_id):
    return (group_owner_id == current_user.id) or (acting_role_name == "ADMIN") or (gm_user_id == current_user.id)


def _is_group_admin_or_owner(group, membership):
    return group.owner_id == current_user.id or membership.role.name == "ADMIN"


def _category_carries_permission(group_id, category_id):
    """True si la categoría porta alguna concesión de permiso sobre subgrupos."""
    return (
        GroupPermissionGrant.query.filter_by(group_id=group_id, category_id=category_id).first()
        is not None
    )


def _check_category_target(group, membership, gm, category_id, *, block_permission_grants=True):
    """Valida que la categoría sea del grupo y que el actor pueda tocarla.

    Un miembro que no es owner/admin no puede asignarse una categoría que
    porte permisos: sería una escalada de privilegios. Quitársela no lo es
    (solo pierde permisos), así que el borrado pasa `block_permission_grants=False`.
    Devuelve (category, None) si está permitido, o (None, error) si no.
    """
    category = Category.query.filter_by(id=category_id, group_id=gm.group_id).first()
    if category is None:
        return None, ("Not found", 404)
    if (
        block_permission_grants
        and not _is_group_admin_or_owner(group, membership)
        and _category_carries_permission(gm.group_id, category.id)
    ):
        return None, ("Forbidden", 403)
    return category, None


def _handle_member_post(group, membership, gm, group_member_id):
    category_id = request.form.get("category_id") or (request.is_json and request.json.get("category_id"))
    if not category_id:
        return ("category_id required", 400)

    # permission
    if not _can_modify_member(group.owner_id, membership.role.name, gm.user_id):
        return _json_or_flash(False, "No tienes permisos para asociar categorías.", 403)

    category, error = _check_category_target(group, membership, gm, category_id)
    if error:
        status = error[1]
        return _json_or_flash(
            False,
            "Categoría inválida." if status == 404 else "No tienes permisos para asociar esta categoría.",
            status,
        )
    category_id = category.id

    existing = GroupMemberCategory.query.filter_by(group_member_id=group_member_id, category_id=category_id).first()
    if existing:
        return ("Already exists", 409)
    assoc = find_soft_deleted(
        GroupMemberCategory, group_member_id=group_member_id, category_id=category_id
    )
    if assoc:
        assoc.restore()
    else:
        assoc = GroupMemberCategory(group_member_id=group_member_id, category_id=category_id)
        scheduler_db.session.add(assoc)
    conflict = _commit_or_duplicate(
        "Esa categoría ya está asociada al miembro.",
        url_for("categories.member_categories", group_member_id=group_member_id),
        "asignación de categoría duplicada (group_member_id=%s category_id=%s)",
        group_member_id, category_id,
    )
    if conflict:
        return conflict
    if request.is_json:
        return jsonify({"ok": True}), 201
    flash("Categoría asociada.", "success")
    return redirect(url_for("categories.member_categories", group_member_id=group_member_id))


def _handle_member_delete(group, membership, gm, group_member_id):
    category_id = request.is_json and request.json.get("category_id")
    if not category_id:
        return ("category_id required", 400)
    if not _can_modify_member(group.owner_id, membership.role.name, gm.user_id):
        return ("Forbidden", 403)
    category, error = _check_category_target(
        group, membership, gm, category_id, block_permission_grants=False
    )
    if error:
        return error
    category_id = category.id
    assoc = GroupMemberCategory.query.filter_by(group_member_id=group_member_id, category_id=category_id).first()
    if not assoc:
        return ("Not found", 404)
    assoc.soft_delete()
    scheduler_db.session.commit()
    if request.is_json:
        return ("", 204)
    flash("Asociación eliminada.", "success")
    return redirect(url_for("categories.member_categories", group_member_id=group_member_id))


def _parse_bulk_request():
    if not request.is_json:
        return None, ("JSON required", 400)
    data = request.get_json(silent=True) or {}
    gid = data.get("group_id")
    mids = data.get("member_ids") or []
    cids = data.get("category_ids") or []
    act = data.get("action") or "assign"
    if not gid or not isinstance(mids, list) or not isinstance(cids, list):
        return None, (jsonify({"ok": False, "message": "Parámetros inválidos."}), 400)
    return (gid, mids, cids, act), None


def _validate_bulk_ids(gid, mids, cids):
    valid_member_ids = [m.id for m in GroupMember.query.filter_by(group_id=gid).all()]
    invalid_members = [mid for mid in mids if mid not in valid_member_ids]
    if invalid_members:
        return jsonify({"ok": False, "message": "Miembro(s) inválido(s)", "invalid_members": invalid_members}), 400

    valid_category_ids = [c.id for c in Category.query.filter_by(group_id=gid).all()]
    invalid_categories = [cid for cid in cids if cid not in valid_category_ids]
    if invalid_categories:
        return jsonify({"ok": False, "message": "Categoría(s) inválida(s)", "invalid_categories": invalid_categories}), 400
    return None


def _bulk_do_assign(gid, mids, cids):
    created = 0
    existing = {
        (gmc.group_member_id, gmc.category_id)
        for gmc in GroupMemberCategory.query.join(
            GroupMember, GroupMember.id == GroupMemberCategory.group_member_id
        ).filter(GroupMember.group_id == gid)
        .all()
    }
    for mid in mids:
        for cid in cids:
            key = (mid, cid)
            if key not in existing:
                hidden = find_soft_deleted(
                    GroupMemberCategory, group_member_id=mid, category_id=cid
                )
                if hidden:
                    hidden.restore()
                else:
                    scheduler_db.session.add(
                        GroupMemberCategory(group_member_id=mid, category_id=cid)
                    )
                created += 1
    conflict = _commit_or_duplicate(
        "Alguna de las asignaciones ya existía. Recarga y vuelve a intentar.",
        None,
        "bulk_assign con conflicto de unique (group_id=%s)", gid,
    )
    if conflict:
        return conflict
    return jsonify({"ok": True, "created": created})


def _bulk_do_unassign(mids, cids):
    assocs = GroupMemberCategory.query.filter(
        GroupMemberCategory.group_member_id.in_(mids),
        GroupMemberCategory.category_id.in_(cids),
    ).all()
    for assoc in assocs:
        assoc.soft_delete()
    scheduler_db.session.commit()
    return jsonify({"ok": True, "deleted": len(assocs)})


@category_bp.route("/group_member/<int:group_member_id>", methods=["GET", "POST", "DELETE"])
@login_required
def member_categories(group_member_id):
    gm = active_or_404(scheduler_db.session.get(GroupMember, group_member_id))
    group_id = gm.group_id

    # Must be member to view/modify associations
    group, membership = require_group_member(group_id)

    # POST -> associate category to member (admin or owner or the member themselves)
    if request.method == "POST":
        return _handle_member_post(group, membership, gm, group_member_id)

    if request.method == "DELETE":
        return _handle_member_delete(group, membership, gm, group_member_id)

    # GET -> list categories and associations
    all_categories = Category.query.filter_by(group_id=group_id).all()
    assoc_ids = [a.category_id for a in gm.categories]
    can_edit = _can_modify_member(group.owner_id, membership.role.name, gm.user_id)

    # render small template fragment if html
    if request.accept_mimetypes.best == "text/html":
        return render_template(
            "groups/member_categories.html",
            group=group,
            member=gm,
            # El email del miembro solo si el que mira es owner/admin;
            # el propio siempre.
            member_label=display_name(
                gm.user,
                with_email=can_see_member_emails(group, membership)
                or gm.user_id == current_user.id,
            ),
            categories=all_categories,
            assoc_ids=assoc_ids,
            can_edit=can_edit,
        )

    return jsonify({
        "all": [{"id": c.id, "name": c.name} for c in all_categories],
        "selected": assoc_ids,
    })


@category_bp.route("/bulk_assign", methods=["POST"])
@login_required
def bulk_assign():
    """Asigna o desasigna categorías a múltiples miembros del grupo.

    Espera JSON: { group_id, member_ids: [int], category_ids: [int], action: 'assign'|'unassign' }
    Requiere permisos de admin/owner del grupo.
    """
    parsed, error = _parse_bulk_request()
    if error:
        return error
    group_id, member_ids, category_ids, action = parsed

    # Authz
    require_group_admin_or_owner(group_id)

    validation_error = _validate_bulk_ids(group_id, member_ids, category_ids)
    if validation_error:
        return validation_error

    if action == "assign":
        return _bulk_do_assign(group_id, member_ids, category_ids)
    if action == "unassign":
        return _bulk_do_unassign(member_ids, category_ids)
    return jsonify({"ok": False, "message": "Acción inválida"}), 400
