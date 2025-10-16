from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import scheduler_db
from app.models import Category, GroupMember, GroupMemberCategory
from app.authz import require_group_member, require_group_admin_or_owner


category_bp = Blueprint("categories", __name__, url_prefix="/categories")


@category_bp.route("/group/<int:group_id>", methods=["GET", "POST"])
@login_required
def group_categories(group_id):
    # Only members can list; only admin/owner can create
    group, _ = require_group_member(group_id)

    if request.method == "POST":
        # creation requires admin or owner
        require_group_admin_or_owner(group_id)
        name = request.form.get("name") or (request.json and request.json.get("name"))
        if not name:
            flash("El nombre de la categoría es requerido.", "warning")
            return redirect(url_for("groups.show", group_id=group_id))
        category = Category(group_id=group_id, name=name)
        scheduler_db.session.add(category)
        scheduler_db.session.commit()
        flash("Categoría creada.", "success")
        return redirect(url_for("categories.group_categories", group_id=group_id))

    categories = Category.query.filter_by(group_id=group_id).all()
    # If accessed from browser, render a small template or return JSON
    if request.accept_mimetypes.best == "text/html":
        return render_template("groups/categories.html", group=group, categories=categories)
    return jsonify([{"id": c.id, "name": c.name} for c in categories])


@category_bp.route("/group_member/<int:group_member_id>", methods=["GET", "POST", "DELETE"])
@login_required
def member_categories(group_member_id):
    gm = GroupMember.query.get_or_404(group_member_id)
    group_id = gm.group_id

    # Must be member to view/modify associations
    group, membership = require_group_member(group_id)

    # POST -> associate category to member (admin or owner or the member themselves)
    if request.method == "POST":
        category_id = request.form.get("category_id") or (request.json and request.json.get("category_id"))
        if not category_id:
            return ("category_id required", 400)

        # allow if acting user is owner/admin or the member itself
        if not (group.owner_id == current_user.id or membership.role.name == "ADMIN" or gm.user_id == current_user.id):
            flash("No tienes permisos para asociar categorías.", "danger")
            return ("Forbidden", 403)

        existing = GroupMemberCategory.query.filter_by(group_member_id=group_member_id, category_id=category_id).first()
        if existing:
            return ("Already exists", 409)
        assoc = GroupMemberCategory(group_member_id=group_member_id, category_id=category_id)
        scheduler_db.session.add(assoc)
        scheduler_db.session.commit()
        flash("Categoría asociada.", "success")
        return redirect(url_for("categories.member_categories", group_member_id=group_member_id))

    if request.method == "DELETE":
        # Expect category_id in json
        category_id = request.json and request.json.get("category_id")
        if not category_id:
            return ("category_id required", 400)
        # permission same as POST
        if not (group.owner_id == current_user.id or membership.role.name == "ADMIN" or gm.user_id == current_user.id):
            return ("Forbidden", 403)
        assoc = GroupMemberCategory.query.filter_by(group_member_id=group_member_id, category_id=category_id).first()
        if not assoc:
            return ("Not found", 404)
        scheduler_db.session.delete(assoc)
        scheduler_db.session.commit()
        return ("", 204)

    # GET -> list categories and associations
    all_categories = Category.query.filter_by(group_id=group_id).all()
    assoc_ids = [a.category_id for a in gm.categories]

    # render small template fragment if html
    if request.accept_mimetypes.best == "text/html":
        return render_template("groups/member_categories.html", group=group, member=gm, categories=all_categories, assoc_ids=assoc_ids)

    return jsonify({
        "all": [{"id": c.id, "name": c.name} for c in all_categories],
        "selected": assoc_ids,
    })
