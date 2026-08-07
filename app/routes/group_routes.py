import uuid
import csv
import io

from flask import Blueprint, flash, redirect, render_template, request, url_for, abort, make_response
from markupsafe import Markup, escape
from flask_login import current_user, login_required

from app.extensions import scheduler_db
from app.models import Availability, Category, Group, GroupMember, RoleEnum, UserAvailability
from app.models.subgroup import SubGroup
from app.authz import (
    require_group_member,
    require_group_admin_or_owner,
    require_group_owner,
    safe_remove_member,
)
from app.soft_delete import (
    INCLUDE_DELETED,
    active_or_404,
    find_soft_deleted,
    restore_batch,
)

group_bp = Blueprint("groups", __name__, url_prefix="/groups")

def _generate_time_blocks(group):
    return [
        (i, f"{hour:02}:30 - {(hour + 1):02}:20")
        for i, hour in enumerate(range(group.start_hour, group.end_hour))
    ]

def _clear_existing_availability(group_id, user_id):
    """Oculta la disponibilidad previa del usuario. No borra filas: al volver a
    marcar el mismo bloque se restaura la fila existente (ver _restore_or_create)."""
    user_avails = (
        scheduler_db.session.query(UserAvailability)
        .join(Availability)
        .filter(UserAvailability.user_id == user_id, Availability.group_id == group_id)
        .all()
    )
    for ua in user_avails:
        ua.soft_delete()
    scheduler_db.session.commit()

def _process_posted_availability(group_id, form_data, blocks, user_id, active_weekdays=None):
    block_count = len(blocks)
    count = 0
    for weekday in (active_weekdays if active_weekdays is not None else range(7)):
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
                existing = UserAvailability.query.join(Availability).filter(
                    UserAvailability.user_id == user_id,
                    Availability.group_id == group_id,
                    Availability.weekday == weekday,
                    Availability.hour == hour_as_float,
                ).first()

                if not existing:
                    # Reutiliza la fila oculta si existe: evita duplicar
                    # (user_id, availability_id) en cada guardado.
                    hidden = find_soft_deleted(
                        UserAvailability,
                        user_id=user_id,
                        availability_id=group_availability.id,
                    )
                    if hidden:
                        hidden.restore()
                    else:
                        scheduler_db.session.add(
                            UserAvailability(
                                user_id=user_id, availability_id=group_availability.id
                            )
                        )
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


def _active_member_user_ids(group_id):
    """Ids de usuarios que siguen siendo miembros del grupo.

    La disponibilidad de quien se fue no se borra, así que hay que excluirla
    explícitamente de los agregados para no inflar los conteos.
    """
    return {
        user_id
        for (user_id,) in scheduler_db.session.query(GroupMember.user_id)
        .filter(GroupMember.group_id == group_id)
        .all()
    }


def _count_out_of_range_marks(group_id, start_hour, end_hour, weekdays):
    """Cuenta marcas de disponibilidad que el nuevo rango dejaría fuera de la grilla.

    No se borra ninguna: solo dejan de mostrarse mientras el rango las excluya.
    """
    rows = (
        scheduler_db.session.query(Availability.weekday, Availability.hour)
        .join(UserAvailability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
        .filter(UserAvailability.user_id.in_(_active_member_user_ids(group_id)))
        .all()
    )
    return sum(
        1
        for weekday, hour in rows
        if weekday not in weekdays or not start_hour <= hour < end_hour
    )


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
        .filter(UserAvailability.user_id.in_(_active_member_user_ids(group_id)))
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
    memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    admin_group_ids = {
        m.group_id for m in memberships if m.role == RoleEnum.ADMIN
    }

    trash_count = (
        Group.query.execution_options(**{INCLUDE_DELETED: True})
        .filter(Group.deleted_at.isnot(None), Group.owner_id == current_user.id)
        .count()
    )

    return render_template(
        "groups/index.html",
        groups=groups,
        admin_group_ids=admin_group_ids,
        trash_count=trash_count,
    )


@group_bp.route("/<int:group_id>", methods=["GET"])
@login_required
def show(group_id):
    group, membership = require_group_member(group_id)
    blocks = [f"{hour:02}:30 - {(hour + 1):02}:20" for hour in range(group.start_hour, group.end_hour)]
    active_weekdays = group.get_active_weekdays()

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
            .filter(UserAvailability.user_id.in_(_active_member_user_ids(group.id)))
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
    # Se resuelve acá y no en la plantilla: indexar por hora dentro del Jinja
    # daba índices negativos (y celdas pintadas en la fila equivocada) cuando la
    # marca caía fuera del rango visible.
    selected = set()
    cell_users = {}
    for user_id, weekday, hour in user_availability_data:
        block_index = int(hour - group.start_hour)
        if not 0 <= block_index < len(blocks):
            continue
        selected.add((weekday, blocks[block_index]))
        cell_users.setdefault((weekday, block_index), []).append(user_id)

    availability_data = get_availability_data(group_id)

    responded_user_ids = {
        user_id
        for (user_id,) in (
            scheduler_db.session.query(UserAvailability.user_id)
            .join(Availability, UserAvailability.availability_id == Availability.id)
            .filter(Availability.group_id == group.id)
            .filter(UserAvailability.user_id.in_(_active_member_user_ids(group.id)))
            .distinct()
            .all()
        )
    }
    users_without_availability = [
        member.user
        for member in group_members
        if member.user.id not in responded_user_ids
    ]
    members_with_availability_count = len(responded_user_ids)

    can_manage = (group.owner_id == current_user.id) or is_admin

    group_categories = Category.query.filter_by(group_id=group.id).all()
    member_category_map = {
        gm.id: [assoc.category_id for assoc in gm.categories]
        for gm in group_members
    }
    user_gm_map = {gm.user_id: gm.id for gm in group_members}
    subgroups = (
        SubGroup.query.filter_by(parent_group_id=group.id, auto_generated=True)
        .order_by(SubGroup.created_at.desc(), SubGroup.id.asc())
        .all()
    )
    group_subgroups = []
    user_subgroup_map = {}

    for subgroup in subgroups:
        group_subgroups.append(
            {
                "id": subgroup.id,
                "name": subgroup.name,
                "member_count": len(subgroup.members),
            }
        )
        for subgroup_member in subgroup.members:
            user_subgroup_map.setdefault(subgroup_member.user_id, []).append(subgroup.id)

    return render_template(
        "groups/show.html",
        group=group,
        availability=user_availability_data,
        selected=selected,
        cell_users=cell_users,
        blocks=blocks,
        convert_float_to_time_string=convert_float_to_time_string,
        availability_data=availability_data,
        color_map=color_map,
        user_info_map=user_info_map,
        is_admin=is_admin,
        can_manage=can_manage,
        group_categories=group_categories,
        group_subgroups=group_subgroups,
        member_category_map=member_category_map,
        user_subgroup_map=user_subgroup_map,
        user_gm_map=user_gm_map,
        users_without_availability=users_without_availability,
        members_with_availability_count=members_with_availability_count,
        responded_user_ids=sorted(responded_user_ids),
        active_weekdays=active_weekdays,
    )


@group_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        group_name = request.form["group_name"]

        join_token = uuid.uuid4().hex[:10]
        user_id = current_user.id

        new_group = Group(
            name=group_name,
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

    if GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first():
        flash(f"ℹ️ Ya eres miembro del grupo '{group.name}'.", "info")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))

    # Si ya estuvo en el grupo y lo removieron, se reutiliza esa membresía (con
    # sus categorías) en vez de insertar una fila duplicada que dejaría al mismo
    # usuario contado dos veces y listado a la vez como activo y como removido.
    removed = find_soft_deleted(GroupMember, group_id=group.id, user_id=user_id)
    if removed:
        restore_batch(removed)
        # Reingresar por el enlace público no devuelve privilegios: quien fue
        # removido siendo admin vuelve como miembro.
        removed.role = RoleEnum.MEMBER
    else:
        scheduler_db.session.add(
            GroupMember(group_id=group.id, user_id=user_id, role=RoleEnum.MEMBER)
        )
    scheduler_db.session.commit()

    flash(f"✅ ¡Bienvenido! Te has unido al grupo '{group.name}' exitosamente.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))


@group_bp.route("/<int:group_id>/members", methods=["GET"])
@login_required
def members(group_id):
    group, membership = require_group_member(group_id)
    group_members = GroupMember.query.filter_by(group_id=group.id).all()
    can_manage = (group.owner_id == current_user.id) or (membership.role == RoleEnum.ADMIN)
    categories = Category.query.filter_by(group_id=group.id).all()
    responded_user_ids = {
        user_id
        for (user_id,) in (
            scheduler_db.session.query(UserAvailability.user_id)
            .join(Availability, UserAvailability.availability_id == Availability.id)
            .filter(Availability.group_id == group.id)
            .filter(UserAvailability.user_id.in_(_active_member_user_ids(group.id)))
            .distinct()
            .all()
        )
    }
    # Quienes no han respondido primero: son los que necesitan seguimiento.
    group_members.sort(key=lambda gm: gm.user_id in responded_user_ids)

    # Miembros removidos: no se borran, quedan disponibles para reincorporar.
    removed_members = []
    if can_manage:
        removed_members = (
            GroupMember.query.execution_options(**{INCLUDE_DELETED: True})
            .filter(GroupMember.group_id == group.id, GroupMember.deleted_at.isnot(None))
            .order_by(GroupMember.deleted_at.desc())
            .all()
        )

    return render_template(
        "groups/members.html",
        group=group,
        members=group_members,
        membership=membership,
        categories=categories,
        can_manage=can_manage,
        responded_user_ids=responded_user_ids,
        removed_members=removed_members,
    )


@group_bp.route("/<int:group_id>/members/export.csv", methods=["GET"])
@login_required
def export_members_csv(group_id):
    group, _ = require_group_member(group_id)
    group_members = GroupMember.query.filter_by(group_id=group.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nombre", "Correo", "Categorias", "Cantidad de horarios disponibles"])

    for member in group_members:
        category_names = sorted(
            assoc.category.name
            for assoc in member.categories
            if assoc.category and assoc.category.name
        )
        availability_count = (
            scheduler_db.session.query(UserAvailability)
            .join(Availability)
            .filter(
                UserAvailability.user_id == member.user.id,
                Availability.group_id == group.id
            )
            .count()
        )
        writer.writerow([
            member.user.name if member.user else "",
            member.user.email if member.user else "",
            ", ".join(category_names),
            availability_count,
        ])

    output.seek(0)
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f"attachment; filename=group_{group_id}_members.csv"
    return response


@group_bp.route("/<int:group_id>/availability", methods=["GET", "POST"])
@login_required
def availability(group_id):
    group, _ = require_group_member(group_id)
    blocks = _generate_time_blocks(group)
    active_weekdays = group.get_active_weekdays()

    if request.method == "POST":
        _clear_existing_availability(group_id, current_user.id)
        saved_count = _process_posted_availability(
            group_id, request.form, blocks, current_user.id, active_weekdays
        )

        if saved_count == 0:
            # Dejar la grilla vacía es una respuesta válida ("no puedo ningún
            # bloque"), no un error: se guarda igual y se avisa sin alarmar.
            flash(
                "ℹ️ Guardado sin bloques marcados: quedaste sin disponibilidad en este grupo.",
                "info",
            )
            return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

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
        block_index = int(hour - group.start_hour)
        if 0 <= block_index < len(blocks):
            selected.add((weekday, block_index))
    return render_template(
        "groups/availability.html",
        group=group,
        group_id=group_id,
        selected=selected,
        blocks=blocks,
        active_weekdays=active_weekdays,
    )


@group_bp.route("/<int:group_id>/availability/autosave", methods=["POST"])
@login_required
def availability_autosave(group_id):
    """Guarda la disponibilidad completa del usuario vía fetch, sin recargar la página."""
    group, _ = require_group_member(group_id)
    blocks = _generate_time_blocks(group)
    active_weekdays = group.get_active_weekdays()

    payload = request.get_json(silent=True) or {}
    slots = payload.get("slots")
    if not isinstance(slots, list):
        return {"ok": False, "message": "Formato inválido."}, 400

    # Reconstruye el form_data esperado por _process_posted_availability a partir
    # de la lista de slots [{weekday, block_index}, ...] enviada por el cliente.
    form_data = {
        f"day_{slot.get('weekday')}_hour_{slot.get('block_index')}": "on"
        for slot in slots
        if isinstance(slot, dict)
    }

    _clear_existing_availability(group_id, current_user.id)
    saved_count = _process_posted_availability(
        group_id, form_data, blocks, current_user.id, active_weekdays
    )

    return {"ok": True, "saved_count": saved_count}


@group_bp.route("/<int:group_id>/availability/settings", methods=["POST"])
@login_required
def availability_settings(group_id):
    """Permite a owner/admin ajustar el rango horario y los días visibles del grupo."""
    group, _ = require_group_admin_or_owner(group_id)

    try:
        start_hour = int(request.form.get("start_hour", group.start_hour))
        end_hour = int(request.form.get("end_hour", group.end_hour))
    except (TypeError, ValueError):
        flash("❌ Rango horario inválido.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    if not (0 <= start_hour < end_hour <= 24):
        flash("❌ El rango horario no es válido (debe ir de 0 a 24 y el inicio ser menor al fin).", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    weekdays = request.form.getlist("weekdays")
    try:
        weekday_ints = sorted({int(d) for d in weekdays if 0 <= int(d) <= 6})
    except ValueError:
        weekday_ints = []
    if not weekday_ints:
        flash("❌ Selecciona al menos un día.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    hidden_blocks = _count_out_of_range_marks(group_id, start_hour, end_hour, weekday_ints)

    group.start_hour = start_hour
    group.end_hour = end_hour
    group.active_weekdays = ",".join(str(d) for d in weekday_ints)
    scheduler_db.session.commit()

    flash("✅ Configuración de disponibilidad actualizada.", "success")
    if hidden_blocks:
        flash(
            f"ℹ️ {hidden_blocks} bloques ya marcados quedan fuera del nuevo rango. "
            "No se borraron: vuelven a aparecer si amplías el horario o los días.",
            "info",
        )
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/delete", methods=["POST"])
@login_required
def delete(group_id):
    group, _ = require_group_owner(group_id)
    group_name = group.name

    # Nada se borra de la base: el grupo y sus miembros, categorías y subgrupos
    # quedan ocultos y recuperables desde la papelera.
    group.soft_delete()
    scheduler_db.session.commit()

    restore_url = url_for("groups.restore", group_id=group.id)
    flash(
        Markup(
            f"🗑️ Grupo '{escape(group_name)}' movido a la papelera. "
            f'<a class="underline font-medium" href="{restore_url}">Deshacer</a>'
        ),
        "success",
    )
    return redirect(url_for(GROUP_INDEX_URL))


@group_bp.route("/trash", methods=["GET"])
@login_required
def trash():
    """Papelera: grupos que el usuario eliminó y puede restaurar."""
    groups = (
        Group.query.execution_options(**{INCLUDE_DELETED: True})
        .filter(Group.deleted_at.isnot(None), Group.owner_id == current_user.id)
        .order_by(Group.deleted_at.desc())
        .all()
    )
    return render_template("groups/trash.html", groups=groups)


@group_bp.route("/<int:group_id>/restore", methods=["GET", "POST"])
@login_required
def restore(group_id):
    group = (
        Group.query.execution_options(**{INCLUDE_DELETED: True})
        .filter(Group.id == group_id)
        .first()
    )
    if group is None or group.owner_id != current_user.id:
        abort(404)

    if not group.is_deleted:
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    restore_batch(group)
    scheduler_db.session.commit()

    flash(f"✅ Grupo '{group.name}' restaurado.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/leave", methods=["POST"])
@login_required
def leave(group_id):
    group = active_or_404(Group.query.get(group_id))
    membership = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()
    if not membership:
        flash("⚠️ No perteneces a este grupo.", "warning")
        return redirect(url_for(GROUP_INDEX_URL))

    # La disponibilidad del usuario no se toca: queda fuera de los agregados
    # por dejar de ser miembro, y vuelve tal cual si reingresa.
    membership.soft_delete()

    if group.owner_id == current_user.id:
        remaining_members = GroupMember.query.filter_by(group_id=group_id).all()
        if remaining_members:
            group.owner_id = remaining_members[0].user_id
        else:
            # Grupo sin nadie: se oculta, no se borra.
            group.soft_delete()

    scheduler_db.session.commit()

    flash(f"✅ Has abandonado el grupo '{group.name}' exitosamente.", "success")
    return redirect(url_for(GROUP_INDEX_URL))


@group_bp.route("/<int:group_id>/remove/<int:user_id>", methods=["POST"])
@login_required
def remove(group_id, user_id):
    if current_user.id == user_id:
        flash("ℹ️ Para salir del grupo, usa la opción 'Abandonar grupo'.", "info")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    # Ejecuta comprobaciones y oculta la membresía (la disponibilidad se conserva)
    safe_remove_member(group_id, user_id)
    scheduler_db.session.commit()

    restore_url = url_for("groups.restore_member", group_id=group_id, user_id=user_id)
    flash(
        Markup(
            "🗑️ Miembro removido del grupo. "
            f'<a class="underline font-medium" href="{restore_url}">Deshacer</a>'
        ),
        "success",
    )
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/restore_member/<int:user_id>", methods=["GET", "POST"])
@login_required
def restore_member(group_id, user_id):
    """Reincorpora a un miembro removido, con su disponibilidad y categorías."""
    require_group_admin_or_owner(group_id)

    membership = find_soft_deleted(GroupMember, group_id=group_id, user_id=user_id)
    if membership is None:
        flash("⚠️ Ese miembro no está en la papelera del grupo.", "warning")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    restore_batch(membership)
    scheduler_db.session.commit()

    flash("✅ Miembro reincorporado al grupo.", "success")
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
    
    member.role = RoleEnum[role_str]
    scheduler_db.session.commit()

    flash("Rol actualizado con éxito.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))
