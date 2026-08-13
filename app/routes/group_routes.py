import csv
import io

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for, abort, make_response,
    current_app,
)
from markupsafe import Markup, escape
from flask_login import current_user, login_required
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import scheduler_db
from app.models import (
    Availability,
    Category,
    Group,
    GroupMember,
    GroupMemberCategory,
    RoleEnum,
    UserAvailability,
)
from app.models.subgroup import SubGroup
from app.ratelimit import rate_limit
from app.authz import (
    can_see_member_emails,
    display_name,
    require_group_member,
    require_group_admin_or_owner,
    require_group_owner,
    safe_remove_member,
)
from app.permissions import (
    LEVEL_LABELS,
    LEVEL_NONE,
    LEVEL_ORDER,
    LEVEL_PERMISSIONS,
    PERM_VIEW_ALL,
    PERM_VIEW_AVAILABILITY,
    effective_permissions,
    grant_sources,
    has_availability_of,
    level_of,
)
from app.services.availability_service import (
    active_member_user_ids,
    block_index_for,
    clear_existing_availability,
    count_out_of_range_marks,
    format_minutes,
    generate_time_blocks,
    get_availability_data,
    parse_time_to_minutes,
    process_posted_availability,
    remap_availability_marks,
    subgroup_peer_user_ids,
)
from app.services.group_service import (
    apply_permission_level,
    counts_by_model,
    create_group,
    get_admin_group_ids,
    get_category_member_counts,
    get_group_categories,
    get_group_members,
    get_groups_for_user,
    get_member_availability_counts,
    get_removed_members,
    get_responded_user_ids,
    get_subgroups_for_show,
    get_trash_count,
    get_user_availability_data,
    join_group,
    leave_group,
    revoke_all_permissions,
    rotate_join_token as svc_rotate_join_token,
    update_member_role,
)
from app.soft_delete import (
    INCLUDE_DELETED,
    active_or_404,
    find_soft_deleted,
    restore_batch,
)

group_bp = Blueprint("groups", __name__, url_prefix="/groups")

GROUP_SHOW_URL = "groups.show"
GROUP_INDEX_URL = "groups.index"

# Largo de la columna `Group.name` (String(150)): pasado ese punto el INSERT
# falla en la BD, así que la request se rechaza antes de llegar ahí.
GROUP_NAME_MAX_LENGTH = 150

# Cotas de los listados que crecen sin techo. No es paginación: es el techo que
# evita que una vista se vuelva ilegible (y cara) cuando el grupo se dispara.
# Todos los listados acotados llevan además un orden total, para que el corte
# sea el mismo entre requests con los mismos datos.
MEMBERS_LIST_LIMIT = 500
TRASH_LIST_LIMIT = 200


def _commit_or_flash_conflict(message, log_message, *log_args):
    """Commitea; si un unique de BD rechaza el duplicado, avisa en limpio.

    Los unique parciales de DATA-001 son lo que atrapa la carrera entre dos
    requests que pasan a la vez el chequeo previo en Python. Sin este manejo el
    segundo vería un 500 crudo en vez de un mensaje.
    """
    try:
        scheduler_db.session.commit()
        return True
    except IntegrityError:
        scheduler_db.session.rollback()
        current_app.logger.warning(log_message, *log_args)
        flash(message, "warning")
        return False


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



@group_bp.route("/", methods=["GET"])
@login_required
def index():
    groups = get_groups_for_user(current_user.id)
    admin_group_ids = get_admin_group_ids(current_user.id)
    group_ids = [group.id for group in groups]
    member_counts = counts_by_model(GroupMember, group_ids)
    category_counts = counts_by_model(Category, group_ids)
    trash_count = get_trash_count(current_user.id)
    return render_template(
        "groups/index.html",
        groups=groups,
        admin_group_ids=admin_group_ids,
        trash_count=trash_count,
        member_counts=member_counts,
        category_counts=category_counts,
    )


@group_bp.route("/<int:group_id>", methods=["GET"])
@login_required
def show(group_id):
    group, membership = require_group_member(group_id)
    blocks = [label for _, label in generate_time_blocks(group)]
    active_weekdays = group.get_active_weekdays()

    group_members = get_group_members(group.id, MEMBERS_LIST_LIMIT)
    color_map = assign_colors_to_members(group_members)
    is_admin = membership and membership.role == RoleEnum.ADMIN
    perms = effective_permissions(group, membership)
    can_manage = (group.owner_id == current_user.id) or is_admin
    can_see_emails = can_see_member_emails(group, membership)
    user_info_map = {
        member.user.id: {
            "name": display_name(member.user, with_email=can_see_emails),
            "email": (
                member.user.email
                if can_see_emails or member.user.id == current_user.id
                else ""
            ),
        } for member in group_members
    }
    can_view_group_availability = PERM_VIEW_AVAILABILITY in perms
    scope_user_ids = None
    if can_view_group_availability and PERM_VIEW_ALL not in perms:
        peers = subgroup_peer_user_ids(group.id, current_user.id)
        if peers:
            scope_user_ids = peers
        else:
            can_view_group_availability = False

    visible_user_ids = (
        active_member_user_ids(group.id) if scope_user_ids is None else scope_user_ids
    )

    if can_view_group_availability:
        user_availability_data = get_user_availability_data(group.id, visible_user_ids)
    else:
        user_availability_data = get_user_availability_data(group.id, current_user.id)

    selected = set()
    cell_users = {}
    for user_id, weekday, hour in user_availability_data:
        block_index = block_index_for(group, hour)
        if block_index is None:
            continue
        selected.add((weekday, blocks[block_index]))
        cell_users.setdefault((weekday, block_index), []).append(user_id)

    availability_data = get_availability_data(group_id, user_ids=scope_user_ids)

    responded_user_ids = get_responded_user_ids(group.id, visible_user_ids)
    users_without_availability = [
        member.user
        for member in group_members
        if member.user.id not in responded_user_ids and member.user.id in visible_user_ids
    ]
    members_with_availability_count = len(responded_user_ids)

    group_categories = get_group_categories(group.id)
    scoped_members = [
        gm for gm in group_members
        if scope_user_ids is None or gm.user_id in scope_user_ids
    ]
    member_category_map = {
        gm.id: [assoc.category_id for assoc in gm.categories]
        for gm in scoped_members
    }
    user_gm_map = {gm.user_id: gm.id for gm in scoped_members}
    category_member_names = {category.id: [] for category in group_categories}
    for gm in group_members:
        shown_name = display_name(gm.user, with_email=can_see_emails)
        for assoc in gm.categories:
            if assoc.category_id in category_member_names:
                category_member_names[assoc.category_id].append(shown_name)

    group_subgroups, user_subgroup_map = get_subgroups_for_show(
        group.id, scope_user_ids, current_user.id
    )

    return render_template(
        "groups/show.html",
        group=group,
        availability=user_availability_data,
        selected=selected,
        cell_users=cell_users,
        blocks=blocks,
        format_minutes=format_minutes,
        availability_data=availability_data,
        color_map=color_map,
        user_info_map=user_info_map,
        is_admin=is_admin,
        can_manage=can_manage,
        can_see_emails=can_see_emails,
        can_view_group_availability=can_view_group_availability,
        availability_scope_user_ids=scope_user_ids,
        perms=perms,
        group_categories=group_categories,
        category_member_names=category_member_names,
        group_subgroups=group_subgroups,
        member_category_map=member_category_map,
        scoped_members=scoped_members,
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
        group_name = request.form["group_name"].strip()
        # `Group.name` es String(150): sin este chequeo Postgres tira DataError y
        # el usuario ve un 500 crudo. El maxlength del template no basta (UX-004).
        if not group_name:
            flash("❌ El nombre del grupo es obligatorio.", "warning")
            return render_template("groups/create.html"), 400
        if len(group_name) > GROUP_NAME_MAX_LENGTH:
            flash(
                f"❌ El nombre del grupo no puede superar los {GROUP_NAME_MAX_LENGTH} caracteres.",
                "warning",
            )
            return render_template("groups/create.html"), 400

        user_id = current_user.id

        # El grupo y la membresía del owner van en la misma transacción: un fallo
        # entre medio dejaría un grupo cuyo dueño no es miembro (huérfano).
        try:
            new_group = create_group(group_name, user_id)
            scheduler_db.session.commit()
        except Exception:  # pylint: disable=broad-except
            scheduler_db.session.rollback()
            current_app.logger.exception("create group failed (user_id=%s)", user_id)
            flash("❌ No se pudo crear el grupo. Inténtalo de nuevo.", "danger")
            return redirect(url_for(GROUP_INDEX_URL))

        flash(
            f"✅ ¡Grupo '{group_name}' creado con éxito! Ya puedes invitar miembros.",
            "success",
        )
        return redirect(url_for(GROUP_SHOW_URL, group_id=new_group.id))
    return render_template("groups/create.html")


@group_bp.route("/<int:group_id>/rotate_token", methods=["POST"])
@login_required
def rotate_join_token(group_id):
    """Regenera el link de invitación del grupo (SEC-009).

    Es la única forma de invalidar un link que se filtró, y el camino por el
    que un grupo viejo deja atrás su token de 40 bits. Solo el dueño: un admin
    puede invitar, pero cortarle el acceso a la invitación en circulación es
    decisión de quien es dueño del grupo.
    """
    group, _ = require_group_owner(group_id)

    svc_rotate_join_token(group)
    try:
        scheduler_db.session.commit()
    except Exception:  # pylint: disable=broad-except
        scheduler_db.session.rollback()
        current_app.logger.exception("rotate join token failed (group_id=%s)", group_id)
        flash("❌ No se pudo regenerar el link de invitación. Inténtalo de nuevo.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    current_app.logger.info(
        "join_token rotado (group_id=%s user_id=%s)", group_id, current_user.id
    )
    flash("🔄 Link de invitación regenerado. El anterior dejó de funcionar.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


# Adivinar un token deja de ser gratis: 20 intentos cada 5 minutos por IP. Un
# invitado real hace 2 o 3 (abrir el link, rebotar por Google, volver).
@group_bp.route("/join/<token>", methods=["GET", "POST"])
@rate_limit(limit=20, window_seconds=300, scope="groups.join")
def join(token):
    group = Group.query.filter_by(join_token=token).first()

    if not group:
        flash("❌ Grupo no encontrado. Verifica que el enlace de invitación sea correcto.", "danger")
        # Un anónimo con un link roto no puede ir a "Mis Grupos": rebotaría al login.
        target = GROUP_INDEX_URL if current_user.is_authenticated else "main.index"
        return redirect(url_for(target))

    if current_user.is_authenticated and GroupMember.query.filter_by(
        group_id=group.id, user_id=current_user.id
    ).first():
        flash(f"ℹ️ Ya eres miembro del grupo '{group.name}'.", "info")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))

    # El GET sólo muestra la confirmación: así el link de invitación compartido
    # sigue siendo un link normal (y sobrevive al rebote por OAuth), pero unirse
    # exige un POST con token, que un <img> o un prefetch ajeno no puede emitir.
    # No pide login para que el invitado vea a qué grupo lo invitaron antes de
    # decidir si crea una cuenta.
    if request.method == "GET":
        return render_template("groups/join.html", group=group, token=token)

    if not current_user.is_authenticated:
        destino = url_for("groups.join", token=token)
        session["next_page"] = destino
        return redirect(url_for("auth.login", next=destino))

    user_id = current_user.id

    # Si ya estuvo en el grupo y lo removieron, se reutiliza esa membresía (con
    # sus categorías) en vez de insertar una fila duplicada que dejaría al mismo
    # usuario contado dos veces y listado a la vez como activo y como removido.
    # Reingresar por el enlace público no devuelve privilegios: quien fue
    # removido siendo admin vuelve como miembro.
    join_group(group, user_id)
    if not _commit_or_flash_conflict(
        f"ℹ️ Ya eres miembro del grupo '{group.name}'.",
        "join duplicado (group_id=%s user_id=%s)", group.id, user_id,
    ):
        return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))

    flash(f"✅ ¡Bienvenido! Te has unido al grupo '{group.name}' exitosamente.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group.id))


@group_bp.route("/<int:group_id>/members", methods=["GET"])
@login_required
def members(group_id):
    group, membership = require_group_member(group_id)
    group_members = (
        GroupMember.query.filter_by(group_id=group.id)
        .options(selectinload(GroupMember.user), selectinload(GroupMember.categories))
        .order_by(GroupMember.id.asc())
        .limit(MEMBERS_LIST_LIMIT)
        .all()
    )
    can_manage = (group.owner_id == current_user.id) or (membership.role == RoleEnum.ADMIN)
    can_see_emails = can_see_member_emails(group, membership)
    categories = Category.query.filter_by(group_id=group.id).all()
    responded_user_ids = get_responded_user_ids(group.id, active_member_user_ids(group.id))
    # Quienes no han respondido primero: son los que necesitan seguimiento.
    group_members.sort(key=lambda gm: gm.user_id in responded_user_ids)

    # Miembros removidos: no se borran, quedan disponibles para reincorporar.
    removed_members = []
    if can_manage:
        removed_members = (
            GroupMember.query.execution_options(**{INCLUDE_DELETED: True})
            .options(selectinload(GroupMember.user))
            .filter(GroupMember.group_id == group.id, GroupMember.deleted_at.isnot(None))
            .order_by(GroupMember.deleted_at.desc(), GroupMember.id.desc())
            .limit(MEMBERS_LIST_LIMIT)
            .all()
        )

    return render_template(
        "groups/members.html",
        group=group,
        members=group_members,
        membership=membership,
        categories=categories,
        can_manage=can_manage,
        can_see_emails=can_see_emails,
        member_names={
            member.user.id: display_name(member.user, with_email=can_see_emails)
            for member in group_members
        },
        responded_user_ids=responded_user_ids,
        removed_members=removed_members,
    )


@group_bp.route("/<int:group_id>/members/export.csv", methods=["GET"])
@login_required
def export_members_csv(group_id):
    # Exporta emails de todo el grupo: exclusivo de owner/admin, igual que el
    # resto de la administración de usuarios (antes cualquier miembro podía).
    group, _ = require_group_admin_or_owner(group_id)
    group_members = (
        GroupMember.query.filter_by(group_id=group.id)
        .options(
            selectinload(GroupMember.user),
            selectinload(GroupMember.categories).selectinload(GroupMemberCategory.category),
        )
        .order_by(GroupMember.id.asc())
        .all()
    )

    # Un GROUP BY para todo el grupo en vez de un COUNT por miembro dentro del
    # bucle: el export era O(miembros) consultas.
    availability_counts = get_member_availability_counts(
        group.id, [member.user_id for member in group_members]
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Nombre", "Correo", "Categorias", "Cantidad de horarios disponibles"])

    for member in group_members:
        category_names = sorted(
            assoc.category.name
            for assoc in member.categories
            if assoc.category and assoc.category.name
        )
        availability_count = availability_counts.get(member.user_id, 0)
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
    blocks = generate_time_blocks(group)
    active_weekdays = group.get_active_weekdays()

    if request.method == "POST":
        # Borrado y reinserción son una sola operación lógica: commitear el
        # borrado por separado perdería las respuestas si falla la reinserción.
        try:
            clear_existing_availability(group, current_user.id, active_weekdays)
            saved_count = process_posted_availability(
                group_id, request.form, group, current_user.id, active_weekdays
            )
            scheduler_db.session.commit()
        except Exception:  # pylint: disable=broad-except
            scheduler_db.session.rollback()
            current_app.logger.exception(
                "availability save failed (group_id=%s user_id=%s)", group_id, current_user.id
            )
            flash("❌ No se pudo guardar la disponibilidad. Inténtalo de nuevo.", "danger")
            return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

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
            UserAvailability.user_id, Availability.weekday, Availability.start_minutes
        )
        .join(Availability)
        .filter(UserAvailability.user_id == current_user.id, Availability.group_id == group_id)
        .all()
    )
    selected = set()
    for _, weekday, hour in user_availability:
        block_index = block_index_for(group, hour)
        if block_index is not None:
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
    active_weekdays = group.get_active_weekdays()

    payload = request.get_json(silent=True) or {}
    slots = payload.get("slots")
    if not isinstance(slots, list):
        return {"ok": False, "message": "Formato inválido."}, 400

    # Reconstruye el form_data esperado por process_posted_availability a partir
    # de la lista de slots [{weekday, block_index}, ...] enviada por el cliente.
    form_data = {
        f"day_{slot.get('weekday')}_hour_{slot.get('block_index')}": "on"
        for slot in slots
        if isinstance(slot, dict)
    }

    try:
        clear_existing_availability(group, current_user.id, active_weekdays)
        saved_count = process_posted_availability(
            group_id, form_data, group, current_user.id, active_weekdays
        )
        scheduler_db.session.commit()
    except Exception:  # pylint: disable=broad-except
        scheduler_db.session.rollback()
        current_app.logger.exception(
            "availability autosave failed (group_id=%s user_id=%s)", group_id, current_user.id
        )
        return {"ok": False, "message": "No se pudo guardar la disponibilidad."}, 500

    return {"ok": True, "saved_count": saved_count}


@group_bp.route("/<int:group_id>/availability/settings", methods=["POST"])
@login_required
def availability_settings(group_id):
    """Permite a owner/admin ajustar horario, extensión del bloque y días visibles."""
    group, _ = require_group_admin_or_owner(group_id)

    try:
        start_minutes = parse_time_to_minutes(
            request.form.get("start_time") or format_minutes(group.start_minutes)
        )
        end_minutes = parse_time_to_minutes(
            request.form.get("end_time") or format_minutes(group.end_minutes)
        )
        block_minutes = int(request.form.get("block_minutes", group.block_minutes))
    except (TypeError, ValueError):
        flash("❌ Rango horario inválido.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    if not 0 <= start_minutes < end_minutes <= 24 * 60:
        flash("❌ El rango horario no es válido: el inicio debe ser anterior al fin.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    if not 5 <= block_minutes <= end_minutes - start_minutes:
        flash(
            "❌ La extensión del bloque debe ser de al menos 5 minutos y caber dentro del rango.",
            "danger",
        )
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    weekdays = request.form.getlist("weekdays")
    try:
        weekday_ints = sorted({int(d) for d in weekdays if 0 <= int(d) <= 6})
    except ValueError:
        weekday_ints = []
    if not weekday_ints:
        flash("❌ Selecciona al menos un día.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    old_starts = group.block_starts()
    old_block_minutes = group.block_minutes
    grid_changed = (
        start_minutes != group.start_minutes
        or end_minutes != group.end_minutes
        or block_minutes != group.block_minutes
    )

    hidden_blocks = count_out_of_range_marks(
        group_id, start_minutes, end_minutes, weekday_ints
    )

    # La grilla nueva y el remapeo de las marcas viajan juntos: commitear la
    # grilla sola dejaría las marcas viejas colgando de bloques inexistentes.
    try:
        group.start_minutes = start_minutes
        group.end_minutes = end_minutes
        group.block_minutes = block_minutes
        group.active_weekdays = ",".join(str(d) for d in weekday_ints)

        remapped = 0
        if grid_changed:
            remapped = remap_availability_marks(
                group, old_starts, old_block_minutes, set(weekday_ints)
            )
        scheduler_db.session.commit()
    except Exception:  # pylint: disable=broad-except
        scheduler_db.session.rollback()
        current_app.logger.exception("availability settings failed (group_id=%s)", group_id)
        flash("❌ No se pudo actualizar la configuración. Inténtalo de nuevo.", "danger")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    flash("✅ Configuración de disponibilidad actualizada.", "success")
    if remapped:
        flash(
            f"🔄 {remapped} marcas de disponibilidad se reubicaron en los bloques "
            "nuevos que cubren su horario original.",
            "info",
        )
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

    # "Deshacer" restaura, así que es un POST con token, no un link.
    restore_url = url_for("groups.restore", group_id=group.id)
    flash(
        Markup(
            f"🗑️ Grupo '{escape(group_name)}' movido a la papelera. "
            f'<form method="POST" action="{restore_url}" style="display:inline">'
            f'<input type="hidden" name="csrf_token" value="{escape(generate_csrf())}">'
            '<button type="submit" class="underline font-medium">Deshacer</button>'
            "</form>"
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
        .order_by(Group.deleted_at.desc(), Group.id.desc())
        .limit(TRASH_LIST_LIMIT)
        .all()
    )
    return render_template("groups/trash.html", groups=groups)


@group_bp.route("/<int:group_id>/restore", methods=["POST"])
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
    if not _commit_or_flash_conflict(
        "⚠️ No se pudo restaurar el grupo: hay datos activos que chocan con los "
        "de la papelera.",
        "restore de grupo con conflicto de unique (group_id=%s)", group_id,
    ):
        return redirect(url_for("groups.trash"))

    flash(f"✅ Grupo '{group.name}' restaurado.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/leave", methods=["POST"])
@login_required
def leave(group_id):
    group = active_or_404(scheduler_db.session.get(Group, group_id))

    # La disponibilidad del usuario no se toca: queda fuera de los agregados
    # por dejar de ser miembro, y vuelve tal cual si reingresa.
    if leave_group(group, current_user.id) is None:
        flash("⚠️ No perteneces a este grupo.", "warning")
        return redirect(url_for(GROUP_INDEX_URL))

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
            f'<form method="POST" action="{restore_url}" style="display:inline">'
            f'<input type="hidden" name="csrf_token" value="{escape(generate_csrf())}">'
            '<button type="submit" class="underline font-medium">Deshacer</button>'
            "</form>"
        ),
        "success",
    )
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/restore_member/<int:user_id>", methods=["POST"])
@login_required
def restore_member(group_id, user_id):
    """Reincorpora a un miembro removido, con su disponibilidad y categorías."""
    require_group_admin_or_owner(group_id)

    membership = find_soft_deleted(GroupMember, group_id=group_id, user_id=user_id)
    if membership is None:
        flash("⚠️ Ese miembro no está en la papelera del grupo.", "warning")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    restore_batch(membership)
    if not _commit_or_flash_conflict(
        "ℹ️ Esa persona ya volvió a ser miembro del grupo.",
        "restore_member con conflicto de unique (group_id=%s user_id=%s)",
        group_id, user_id,
    ):
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

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

    if group.owner_id == user_id:
        flash("⚠️ No puedes cambiar el rol del propietario del grupo.", "warning")
        return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))

    update_member_role(group, user_id, role_str, current_user)
    scheduler_db.session.commit()

    flash("Rol actualizado con éxito.", "success")
    return redirect(url_for(GROUP_SHOW_URL, group_id=group_id))


@group_bp.route("/<int:group_id>/permissions", methods=["GET"])
@login_required
def permissions(group_id):
    """Panel del owner para otorgar permisos extra de subgrupos, por persona o categoría.

    Lista solo lo concedido (O(concesiones), no O(miembros)): una fila por
    categoría o persona con una concesión directa. El acceso que una persona
    recibe por pertenecer a una categoría NO se repite fila por fila aquí: se
    administra en la fila de la categoría, no en la de cada miembro.
    """
    group, _ = require_group_owner(group_id)

    categories = Category.query.filter_by(group_id=group.id).all()
    categories_by_id = {cat.id: cat for cat in categories}
    group_members = (
        GroupMember.query.filter_by(group_id=group.id)
        .options(selectinload(GroupMember.user))
        .all()
    )
    members_by_id = {member.id: member for member in group_members}
    sources = grant_sources(group)

    # Miembros por categoría en un solo GROUP BY: antes era un COUNT por fila
    # de la tabla de permisos.
    category_member_counts = dict(
        scheduler_db.session.query(
            GroupMemberCategory.category_id, func.count(GroupMemberCategory.id)
        )
        .filter(GroupMemberCategory.category_id.in_(list(categories_by_id)))
        .group_by(GroupMemberCategory.category_id)
        .all()
    ) if categories_by_id else {}

    category_rows = []
    for cat_id, direct in sources["categories"].items():
        cat = categories_by_id.get(cat_id)
        if cat is None:
            continue
        category_rows.append({
            "category": cat,
            "level": level_of(direct),
            "has_availability": has_availability_of(direct),
            "member_count": category_member_counts.get(cat_id, 0),
        })
    category_rows.sort(key=lambda row: row["category"].name)

    member_rows = []
    for member_id, direct in sources["members"].items():
        member = members_by_id.get(member_id)
        if member is None or member.user_id == group.owner_id:
            continue
        member_rows.append({
            "member": member,
            "level": level_of(direct),
            "has_availability": has_availability_of(direct),
        })
    member_rows.sort(key=lambda row: row["member"].user.name or row["member"].user.email)

    granted_category_ids = set(sources["categories"].keys())
    granted_member_ids = set(sources["members"].keys())
    available_categories = [cat for cat in categories if cat.id not in granted_category_ids]
    available_members = [
        member for member in group_members
        if member.id not in granted_member_ids
        and member.user_id != group.owner_id
        and member.role != RoleEnum.ADMIN
    ]

    return render_template(
        "groups/permissions.html",
        group=group,
        category_rows=category_rows,
        member_rows=member_rows,
        available_categories=available_categories,
        available_members=available_members,
        level_order=LEVEL_ORDER,
        level_labels=LEVEL_LABELS,
    )


@group_bp.route("/<int:group_id>/permissions/set", methods=["POST"])
@login_required
def set_permission_level(group_id):
    """Otorga (o cambia) el nivel de permisos de una persona o categoría."""
    group, _ = require_group_owner(group_id)

    subject_type = request.form.get("subject_type")
    subject_id = request.form.get("subject_id", type=int)
    if subject_type is None:
        # Formulario "Agregar permiso": llega combinado como "member:12".
        subject = request.form.get("subject", "")
        subject_type, _, raw_id = subject.partition(":")
        subject_id = int(raw_id) if raw_id.isdigit() else None
    level = request.form.get("level")

    if level not in LEVEL_PERMISSIONS or subject_type not in ("member", "category"):
        flash("Parámetros inválidos.", "danger")
        return redirect(url_for("groups.permissions", group_id=group_id))

    if subject_type == "member":
        subject = GroupMember.query.filter_by(id=subject_id, group_id=group.id).first()
        if not subject or subject.user_id == group.owner_id:
            flash("Miembro inválido.", "danger")
            return redirect(url_for("groups.permissions", group_id=group_id))
    else:
        subject = Category.query.filter_by(id=subject_id, group_id=group.id).first()
        if not subject:
            flash("Categoría inválida.", "danger")
            return redirect(url_for("groups.permissions", group_id=group_id))

    availability_checked = request.form.get("availability") == "on"
    apply_permission_level(group, subject_type, subject_id, level, availability_checked, current_user)
    scheduler_db.session.commit()
    flash("Permisos actualizados.", "success")
    return redirect(url_for("groups.permissions", group_id=group_id))


@group_bp.route("/<int:group_id>/permissions/revoke", methods=["POST"])
@login_required
def revoke_permission(group_id):
    """Quita todos los permisos extra concedidos directamente a una persona o categoría."""
    group, _ = require_group_owner(group_id)

    subject_type = request.form.get("subject_type")
    subject_id = request.form.get("subject_id", type=int)

    # Sin subject_id el filter_by compila a `IS NULL` y barre TODOS los grants
    # por categoría (o por miembro) del grupo: hay que cortar antes de borrar.
    if subject_id is None:
        flash("Parámetros inválidos.", "danger")
        return redirect(url_for("groups.permissions", group_id=group_id))

    if subject_type not in ("member", "category"):
        flash("Parámetros inválidos.", "danger")
        return redirect(url_for("groups.permissions", group_id=group_id))

    revoke_all_permissions(group, subject_type, subject_id, current_user)
    scheduler_db.session.commit()
    flash("Permisos revocados.", "success")
    return redirect(url_for("groups.permissions", group_id=group_id))
