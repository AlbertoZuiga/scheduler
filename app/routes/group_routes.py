import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort
from flask_login import current_user, login_required

from app.extensions import scheduler_db
from app.models import Availability, Group, GroupMember, RoleEnum, UserAvailability
from app.authz import (
    require_group_member,
    require_group_admin_or_owner,
    require_group_owner,
    safe_remove_member,
)

group_bp = Blueprint("groups", __name__, url_prefix="/groups")

def _generate_time_blocks():
    return [
        (i, f"{hour:02}:30 - {(hour + 1):02}:20")
        for i, hour in enumerate(range(STARTING_HOUR, ENDING_HOUR))
    ]

def _clear_existing_availability(group_id, user_id):
    user_avails = (
        scheduler_db.session.query(UserAvailability)
        .join(Availability)
        .filter(UserAvailability.user_id == user_id, Availability.group_id == group_id)
        .all()
    )
    for ua in user_avails:
        scheduler_db.session.delete(ua)
    scheduler_db.session.commit()

def _process_posted_availability(group_id, form_data, blocks, user_id):
    block_count = len(blocks)
    count = 0
    for weekday in range(7):
        for block_index in range(block_count):
            key = f"day_{weekday}_hour_{block_index}"
            if key in form_data:
                hour_str = blocks[block_index][1].split(" - ")[0]
                hour_as_float = convert_hour_to_integer(hour_str)
                group_availability = Availability.query.filter_by(
                    group_id=group_id, weekday=weekday, hour=hour_as_float
                ).first()
                if not group_availability:
                    group_availability = Availability(
                        group_id=group_id, weekday=weekday, hour=hour_as_float
                    )
                    scheduler_db.session.add(group_availability)
                    scheduler_db.session.commit()
                user_availability = UserAvailability(
                    user_id=user_id, availability_id=group_availability.id
                )
                scheduler_db.session.add(user_availability)
                count += 1
    scheduler_db.session.commit()
    return count

GROUP_SHOW_URL = "groups.show"
GROUP_INDEX_URL = "groups.index"
COLORS = [
    "bg-primary",
    "bg-success",
    "bg-warning",
    "bg-danger",
    "bg-info",
    "bg-dark",
    "bg-secondary",
    "bg-pink",
    "bg-teal",
]
STARTING_HOUR = 8
ENDING_HOUR = 19

def assign_colors_to_members(group_members):
    return {member.user.id: COLORS[i % len(COLORS)] for i, member in enumerate(group_members)}


def convert_hour_to_integer(hour):
    """Convert a time string in 'HH:MM' format to a float representing hours."""
    try:
        hours, minutes = map(int, hour.split("-")[0].split(":"))
        return hours + minutes / 60
    except ValueError as exc:
        raise ValueError("Invalid time format. Expected 'HH:MM'.") from exc


def convert_float_to_time_string(hour):
    """Convert a float representing hours to a time string in 'HH:MM' format."""
    try:
        hour_on_clock = int(hour)
        minutes = int(round((hour - hour_on_clock) * 60))
        return f"{hour_on_clock:02}:{minutes:02}"
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid hour value. Expected a float.") from exc


def get_availability_data(group_id):
    if not group_id:
        return {}

    results = (
        scheduler_db.session.query(
            Availability.id,
            Availability.weekday,
            Availability.hour,
            Availability.group_id,
            UserAvailability.user_id,
        )
        .join(UserAvailability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
        .all()
    )

    data = {}
    for availability_id, weekday, hour, _, user_id in results:
        if availability_id not in data:
            data[availability_id] = {
                "availability": Availability(
                    id=availability_id, weekday=weekday, hour=hour, group_id=group_id
                ),
                "users": [],
                "count_users": 0,
            }
        data[availability_id]["users"].append(user_id)
        data[availability_id]["count_users"] += 1

    sorted_data = dict(sorted(data.items(), key=lambda item: item[1]["count_users"], reverse=True))

    return sorted_data


@group_bp.route("/", methods=["GET"])
@login_required
def index():
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()

    return render_template("groups/index.html", groups=groups)


@group_bp.route("/<int:group_id>", methods=["GET"])
@login_required
def show(group_id):
    blocks = [f"{hour:02}:30 - {(hour + 1):02}:20" for hour in range(STARTING_HOUR, ENDING_HOUR)]

    group, membership = require_group_member(group_id)
    group_members = GroupMember.query.filter_by(group_id=group.id).all()
    color_map = assign_colors_to_members(group_members)
    user_info_map = {
        member.user.id: {
            "name": member.user.name,
            "email": member.user.email
        } for member in group_members
    }
    is_admin = membership and membership.role == RoleEnum.ADMIN

    if group.owner_id == current_user.id or is_admin:
        user_availability_data = (
            scheduler_db.session.query(
                UserAvailability.user_id, Availability.weekday, Availability.hour
            )
            .join(Availability, UserAvailability.availability_id == Availability.id)
            .filter(Availability.group_id == group.id)
            .all()
        )
    else:
        user_availability_data = (
            scheduler_db.session.query(
                UserAvailability.user_id, Availability.weekday, Availability.hour
            )
            .join(Availability, Availability.id == UserAvailability.availability_id)
            .filter(Availability.group_id == group.id)
            .filter(UserAvailability.user_id == current_user.id)
            .all()
        )
    selected = set()
    for _, weekday, hour in user_availability_data:
        block_index = int(hour - STARTING_HOUR)
        if 0 <= block_index < len(blocks):
            selected.add((weekday, blocks[block_index]))

    availability_data = get_availability_data(group_id)
    
    # Determinar si el usuario puede gestionar el grupo
    can_manage = (group.owner_id == current_user.id) or is_admin

    return render_template(
        "groups/show.html",
        group=group,
        availability=user_availability_data,
        selected=selected,
        blocks=blocks,
        convert_float_to_time_string=convert_float_to_time_string,
        availability_data=availability_data,
        color_map=color_map,
        user_info_map=user_info_map,
        is_admin=is_admin,
        can_manage=can_manage,
    )


@group_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        group_name = request.form["group_name"]
        group_description = request.form.get("group_description", "")

        join_token = uuid.uuid4().hex[:10]
        user_id = current_user.id

        new_group = Group(
            name=group_name, 
            description=group_description,
            join_token=join_token, 
            owner_id=user_id
        )
        scheduler_db.session.add(new_group)
        scheduler_db.session.commit()

        group_member = GroupMember(group_id=new_group.id, user_id=user_id, role=RoleEnum.ADMIN)
        scheduler_db.session.add(group_member)
        scheduler_db.session.commit()

        flash(
            f"✅ ¡Grupo '{group_name}' creado con éxito! Ya puedes invitar miembros.",
            "success",
        )
        return redirect(url_for(GROUP_SHOW_URL, group_id=new_group.id))
    return render_template("groups/create.html")


@group_bp.route("/join/<token>", methods=["GET"])
@login_required
def join(token):
    group = Group.query.filter_by(join_token=token).first()

    if not group:
        flash("❌ Grupo no encontrado. Verifica que el enlace de invitación sea correcto.", "danger")
        return redirect(url_for(GROUP_INDEX_URL))

    user_id = current_user.id

    print(group, user_id)

    if GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first():
        flash(f"ℹ️ Ya eres miembro del grupo '{group.name}'.", "info")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))

    new_member = GroupMember(group_id=group.id, user_id=user_id, role=RoleEnum.MEMBER)
    scheduler_db.session.add(new_member)
    scheduler_db.session.commit()

    flash(f"✅ ¡Bienvenido! Te has unido al grupo '{group.name}' exitosamente.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))


@group_bp.route("/<int:group_id>/members", methods=["GET"])
@login_required
def members(group_id):
    group, membership = require_group_member(group_id)
    group_members = GroupMember.query.filter_by(group_id=group.id).all()
    return render_template("groups/members.html", group=group, members=group_members, membership=membership)


@group_bp.route("/<int:group_id>/availability", methods=["GET", "POST"])
@login_required
def availability(group_id):
    blocks = _generate_time_blocks()

    # Debe ser miembro para ver o editar disponibilidad
    group, _ = require_group_member(group_id)

    if request.method == "POST":
        _clear_existing_availability(group_id, current_user.id)
        saved_count = _process_posted_availability(group_id, request.form, blocks, current_user.id)

        if saved_count == 0:
            flash("⚠️ No se guardó ninguna disponibilidad. Por favor, selecciona al menos un bloque horario.", "warning")
            return render_template(
                "groups/availability.html",
                group_id=group_id,
                selected={},
                blocks=blocks
            )

        flash(f"✅ Disponibilidad actualizada exitosamente ({saved_count} bloques horarios guardados).", "success")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    user_availability = (
        scheduler_db.session.query(
            UserAvailability.user_id, Availability.weekday, Availability.hour
        )
        .join(Availability)
        .filter(UserAvailability.user_id == current_user.id, Availability.group_id == group_id)
        .all()
    )
    selected = set()
    for _, weekday, hour in user_availability:
        block_index = int(hour - STARTING_HOUR)
        if 0 <= block_index < len(blocks):
            selected.add((weekday, block_index))
        print(f"Selected availability: {selected}")
    return render_template(
        "groups/availability.html", group_id=group_id, selected=selected, blocks=blocks
    )


@group_bp.route("/<int:group_id>/delete", methods=["POST"])
@login_required
def delete(group_id):
    group, _ = require_group_owner(group_id)
    group_name = group.name

    availability_ids = [a.id for a in Availability.query.filter_by(group_id=group_id).all()]
    if availability_ids:
        UserAvailability.query.filter(
            UserAvailability.availability_id.in_(availability_ids)
        ).delete(synchronize_session=False)

    Availability.query.filter_by(group_id=group_id).delete()
    GroupMember.query.filter_by(group_id=group_id).delete()

    scheduler_db.session.delete(group)
    scheduler_db.session.commit()

    flash(f"✅ Grupo '{group_name}' eliminado exitosamente.", "success")
    return redirect(url_for(GROUP_INDEX_URL))


@group_bp.route("/<int:group_id>/leave", methods=["POST"])
@login_required
def leave(group_id):
    group = Group.query.get_or_404(group_id)
    membership = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()
    if not membership:
        flash("⚠️ No perteneces a este grupo.", "warning")
        return redirect(url_for(GROUP_INDEX_URL))
    ua_ids = (
        scheduler_db.session.query(UserAvailability.id)
        .join(Availability)
        .filter(UserAvailability.user_id == current_user.id, Availability.group_id == group_id)
        .all()
    )
    ua_ids = [id for (id,) in ua_ids]
    if ua_ids:
        scheduler_db.session.query(UserAvailability).filter(UserAvailability.id.in_(ua_ids)).delete(
            synchronize_session=False
        )

    # Borramos la membresía del usuario actual
    scheduler_db.session.delete(membership)

    group = Group.query.get_or_404(group_id)

    if group.owner_id == current_user.id:
        remaining_members = GroupMember.query.filter_by(group_id=group_id).all()
        if remaining_members:
            group.owner_id = remaining_members[0].user_id
        else:
            # Delete all related availability and the group
            availability_ids = [a.id for a in Availability.query.filter_by(group_id=group_id).all()]
            if availability_ids:
                UserAvailability.query.filter(
                    UserAvailability.availability_id.in_(availability_ids)
                ).delete(synchronize_session=False)
            Availability.query.filter_by(group_id=group_id).delete()
            scheduler_db.session.delete(group)

    scheduler_db.session.commit()

    flash(f"✅ Has abandonado el grupo '{group.name}' exitosamente.", "success")
    return redirect(url_for(GROUP_INDEX_URL))


@group_bp.route("/<int:group_id>/remove/<int:user_id>", methods=["POST"])
@login_required
def remove(group_id, user_id):
    if current_user.id == user_id:
        flash("ℹ️ Para salir del grupo, usa la opción 'Abandonar grupo'.", "info")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    # Ejecuta comprobaciones y elimina
    safe_remove_member(group_id, user_id)

    # Limpiamos disponibilidad asociada sólo si el miembro existía
    ua_ids = (
        scheduler_db.session.query(UserAvailability.id)
        .join(Availability)
        .filter(UserAvailability.user_id == user_id, Availability.group_id == group_id)
        .all()
    )
    ua_ids = [id for (id,) in ua_ids]
    if ua_ids:
        scheduler_db.session.query(UserAvailability).filter(UserAvailability.id.in_(ua_ids)).delete(
            synchronize_session=False
        )

    scheduler_db.session.commit()
    flash("✅ Miembro removido del grupo exitosamente.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/update_role/<int:user_id>", methods=["POST"])
@login_required
def update_role(group_id, user_id):
    group, _ = require_group_owner(group_id)

    role_str = request.form.get("role")
    if role_str not in RoleEnum.__members__:
        flash("❌ Rol inválido. Selecciona un rol válido.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first_or_404()
    if group.owner_id == user_id:
        flash("⚠️ No puedes cambiar el rol del propietario del grupo.", "warning")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))
    
    old_role = member.role.value
    member.role = RoleEnum[role_str]
    scheduler_db.session.commit()

    flash("Rol actualizado con éxito.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))
