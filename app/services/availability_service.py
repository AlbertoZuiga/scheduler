"""Motor de disponibilidad: la grilla horaria del grupo y las marcas sobre ella.

Extraído de `group_routes.py` (BE-005). Acá vive todo lo que traduce entre las
dos representaciones que conviven en el dominio:

- **minutos desde medianoche**: la unidad canónica (`Group.start_minutes`,
  `Group.block_minutes`, `Availability.start_minutes`).
- **índice de bloque**: la posición dentro de `Group.block_starts()`, que es lo
  que la plantilla y el formulario usan como coordenada (`day_N_hour_M`).

Ninguna función acá commitea: la transacción la maneja la ruta que llama.
"""

from types import SimpleNamespace

from sqlalchemy import func

from app.extensions import scheduler_db
from app.models import Availability, GroupMember, SubGroup, SubGroupMember, UserAvailability
from app.soft_delete import find_soft_deleted

# Cota del resumen "horarios en que pueden todos". No es paginación: es el techo
# que evita que la vista se vuelva ilegible (y cara) cuando el grupo se dispara.
AVAILABILITY_SUMMARY_LIMIT = 200


def format_minutes(total_minutes):
    """Minutos desde medianoche a 'HH:MM'."""
    if not isinstance(total_minutes, (int, float)):
        raise ValueError(f"Se esperaba un número, no {type(total_minutes).__name__!r}.")
    return f"{int(total_minutes) // 60:02}:{int(total_minutes) % 60:02}"


def generate_time_blocks(group):
    return [
        (i, f"{format_minutes(start)} - {format_minutes(start + group.block_minutes)}")
        for i, start in enumerate(group.block_starts())
    ]


def block_index_for(group, start_minutes):
    """Índice del bloque que arranca en `start_minutes`, o None si no calza."""
    return _block_index_for(group, start_minutes)


def _block_index_for(group, start_minutes):
    """Índice del bloque que arranca en `start_minutes` (entero), o None."""
    try:
        return group.block_starts().index(start_minutes)
    except ValueError:
        return None


def parse_time_to_minutes(value):
    """'HH:MM' (o 'HH:MM:SS') a minutos desde medianoche."""
    try:
        parts = str(value).strip().split(":")
        hours, minutes = int(parts[0]), int(parts[1])
    except (AttributeError, IndexError, ValueError) as exc:
        raise ValueError("Formato de hora inválido. Se espera 'HH:MM'.") from exc
    if not (0 <= hours <= 24 and 0 <= minutes <= 59):
        raise ValueError("Hora fuera de rango.")
    return hours * 60 + minutes


def _availability_by_minutes(group_id):
    """Filas de Availability del grupo indexadas por (weekday, start_minutes)."""
    return {
        (row.weekday, row.start_minutes): row
        for row in Availability.query.filter_by(group_id=group_id).all()
    }


def _get_or_create_availability(group_id, weekday, minutes, known):
    """Devuelve la fila del bloque, creándola si aún no existe. Actualiza `known`."""
    existing = known.get((weekday, minutes))
    if existing:
        return existing
    row = Availability(group_id=group_id, weekday=weekday, start_minutes=minutes)
    scheduler_db.session.add(row)
    scheduler_db.session.flush()
    known[(weekday, minutes)] = row
    return row


def clear_existing_availability(group, user_id, active_weekdays):
    """Oculta la disponibilidad previa del usuario dentro de la grilla visible.

    Solo se limpian los bloques que el formulario pudo mostrar: lo que quedó
    fuera del rango o en un día apagado no lo está desmarcando el usuario, así
    que se conserva y reaparece si el admin vuelve a ampliar la grilla.

    No borra filas: al volver a marcar el mismo bloque se restaura la fila
    existente (ver mark_user_available).
    """
    visible_starts = set(group.block_starts())
    visible_weekdays = set(active_weekdays)
    rows = (
        scheduler_db.session.query(UserAvailability, Availability.weekday, Availability.start_minutes)
        .join(Availability, UserAvailability.availability_id == Availability.id)
        .filter(UserAvailability.user_id == user_id, Availability.group_id == group.id)
        .all()
    )
    for ua, weekday, start_minutes in rows:
        if weekday in visible_weekdays and start_minutes in visible_starts:
            ua.soft_delete()


def mark_user_available(user_id, availability_id):
    """Marca el bloque para el usuario. Devuelve True si hubo cambio real."""
    existing = UserAvailability.query.filter_by(
        user_id=user_id, availability_id=availability_id
    ).first()
    if existing:
        return False

    # Reutiliza la fila oculta si existe: evita duplicar
    # (user_id, availability_id) en cada guardado.
    hidden = find_soft_deleted(
        UserAvailability, user_id=user_id, availability_id=availability_id
    )
    if hidden:
        hidden.restore()
    else:
        scheduler_db.session.add(
            UserAvailability(user_id=user_id, availability_id=availability_id)
        )
    return True


def process_posted_availability(group_id, form_data, group, user_id, active_weekdays=None):
    block_starts = group.block_starts()
    known = _availability_by_minutes(group_id)
    count = 0
    for weekday in (active_weekdays if active_weekdays is not None else range(7)):
        for block_index, start_minutes in enumerate(block_starts):
            key = f"day_{weekday}_hour_{block_index}"
            if key not in form_data:
                continue
            group_availability = _get_or_create_availability(
                group_id, weekday, start_minutes, known
            )
            if mark_user_available(user_id, group_availability.id):
                count += 1
    return count


def active_member_user_ids(group_id):
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


def subgroup_peer_user_ids(group_id, user_id):
    """Ids de miembros activos que comparten algún subgrupo con `user_id`.

    Es el alcance de quien tiene `availability.view_all` sin ver todos los
    subgrupos: solo la gente de su(s) subgrupo(s), él incluido. Si no pertenece
    a ninguno el conjunto es vacío y la vista cae al modo "solo mi horario".
    """
    own_subgroup_ids = [
        subgroup_id
        for (subgroup_id,) in scheduler_db.session.query(SubGroupMember.subgroup_id)
        .join(SubGroup, SubGroup.id == SubGroupMember.subgroup_id)
        .filter(SubGroup.parent_group_id == group_id)
        .filter(SubGroupMember.user_id == user_id)
        .all()
    ]
    if not own_subgroup_ids:
        return set()

    peers = {
        peer_id
        for (peer_id,) in scheduler_db.session.query(SubGroupMember.user_id)
        .filter(SubGroupMember.subgroup_id.in_(own_subgroup_ids))
        .all()
    }
    return peers & active_member_user_ids(group_id)


def count_out_of_range_marks(group_id, start_minutes, end_minutes, weekdays):
    """Cuenta marcas de disponibilidad que el nuevo rango dejaría fuera de la grilla.

    No se borra ninguna: solo dejan de mostrarse mientras el rango las excluya.
    """
    rows = (
        scheduler_db.session.query(Availability.weekday, Availability.start_minutes)
        .join(UserAvailability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
        .filter(UserAvailability.user_id.in_(active_member_user_ids(group_id)))
        .all()
    )
    return sum(
        1
        for weekday, avail_start in rows
        if weekday not in weekdays
        or not start_minutes <= avail_start < end_minutes
    )


def remap_availability_marks(group, old_starts, old_block_minutes, weekdays):
    """Reencaja las respuestas ya guardadas cuando cambia el formato de la grilla.

    Una marca vieja cubre `[inicio, inicio + duración_vieja)`. Si ese intervalo
    ya no coincide con ningún bloque nuevo, se traslada a todos los bloques
    nuevos que solape (un bloque viejo puede repartirse en varios nuevos, o
    varios viejos fundirse en uno) y la marca original se oculta.

    Lo que queda fuera del rango o en un día desactivado NO se toca: sigue
    oculto por la grilla y reaparece intacto si el admin vuelve a ampliar.

    Devuelve cuántas marcas se reubicaron.
    """
    new_starts = group.block_starts()
    if not new_starts:
        return 0

    old_starts = set(old_starts)
    known = _availability_by_minutes(group.id)

    remapped = 0
    for (weekday, minutes), row in list(known.items()):
        # Solo se reencaja lo que pertenecía a la grilla anterior: una marca
        # fuera de rango o de un día apagado se deja tal cual.
        if weekday not in weekdays or minutes not in old_starts:
            continue

        old_end = minutes + old_block_minutes
        targets = [
            start
            for start in new_starts
            if start < old_end and start + group.block_minutes > minutes
        ]
        if targets == [minutes]:
            # El bloque nuevo cubre exactamente el mismo tramo: nada que mover.
            continue

        remapped += _move_marks(group, row, targets, known)

    return remapped


def _move_marks(group, row, targets, known):
    """Copia las marcas de `row` a los bloques nuevos que cubren su horario."""
    minutes = row.start_minutes
    moved = 0
    if not targets:
        # El horario viejo no cae en ningún bloque nuevo (el rango se angostó o
        # el día se apagó). Las marcas se dejan intactas: la grilla ya no las
        # muestra, pero reaparecen tal cual si el admin vuelve a ampliar.
        return 0

    member_ids = active_member_user_ids(group.id)
    for mark in (
        UserAvailability.query.filter_by(availability_id=row.id)
        .filter(UserAvailability.user_id.in_(member_ids))
        .all()
    ):
        for start in targets:
            if start == minutes:
                continue
            target_row = _get_or_create_availability(group.id, row.weekday, start, known)
            mark_user_available(mark.user_id, target_row.id)
        if minutes not in targets:
            # La marca vieja se oculta, no se borra: si el admin revierte el
            # formato, este mismo remapeo la reconstruye desde la grilla actual.
            mark.soft_delete()
        moved += 1
    return moved


def get_availability_data(group_id, limit=AVAILABILITY_SUMMARY_LIMIT, user_ids=None):
    """Bloques del grupo con sus asistentes, del más concurrido al menos.

    `user_ids` acota el agregado a un subconjunto de miembros (el alcance de
    subgrupo de quien mira). Si es None se agregan todos los miembros activos.

    Se resuelve en dos pasos para no traer todas las marcas del grupo en cada
    page view: primero un GROUP BY que ordena los bloques por concurrencia y se
    queda con los `limit` primeros, y recién después las marcas de esos bloques.
    El corte es por la cola (los bloques con menos gente), así que "los horarios
    en que pueden todos" —que es lo que la vista destaca— nunca se pierde.
    """
    if not group_id:
        return {}

    member_ids = active_member_user_ids(group_id) if user_ids is None else set(user_ids)
    if not member_ids:
        return {}

    top_blocks = (
        scheduler_db.session.query(
            Availability.id,
            Availability.weekday,
            Availability.start_minutes,
            func.count(UserAvailability.id).label("count_users"),
        )
        .join(UserAvailability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
        .filter(UserAvailability.user_id.in_(member_ids))
        .group_by(Availability.id, Availability.weekday, Availability.start_minutes)
        # `Availability.id` desempata: sin orden total el LIMIT devuelve
        # bloques distintos entre requests con los mismos datos.
        .order_by(func.count(UserAvailability.id).desc(), Availability.id.asc())
        .limit(limit)
        .all()
    )
    if not top_blocks:
        return {}

    data = {
        availability_id: {
            "availability": SimpleNamespace(
                id=availability_id, weekday=weekday, start_minutes=start_minutes, group_id=group_id
            ),
            "users": [],
            "count_users": count_users,
        }
        for availability_id, weekday, start_minutes, count_users in top_blocks
    }

    rows = (
        scheduler_db.session.query(
            UserAvailability.availability_id, UserAvailability.user_id
        )
        .filter(UserAvailability.availability_id.in_(data.keys()))
        .filter(UserAvailability.user_id.in_(member_ids))
        .all()
    )
    for availability_id, user_id in rows:
        data[availability_id]["users"].append(user_id)

    for entry in data.values():
        entry["count_users"] = len(entry["users"])

    return data
