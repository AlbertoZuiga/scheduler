"""BE-005: el motor de disponibilidad, ejercitado sin pasar por las rutas."""

# pylint: disable=redefined-outer-name
import pytest

from app.extensions import scheduler_db
from app.models import Availability, Group, GroupMember, RoleEnum, UserAvailability
from app.models.user import User
from app.services import availability_service as svc


@pytest.fixture()
def group(db_session):
    """Grilla chica y predecible: 08:00-10:00 en bloques de 60 → starts [480, 540]."""
    owner = User(name="Dueño disp", email="owner-disp@example.com")
    db_session.add(owner)
    db_session.commit()
    grupo = Group(
        name="Grupo disp",
        owner_id=owner.id,
        join_token="tok-disp",
        start_minutes=480,
        end_minutes=600,
        block_minutes=60,
        active_weekdays="0,1",
    )
    db_session.add(grupo)
    db_session.commit()
    db_session.add(GroupMember(group_id=grupo.id, user_id=owner.id, role=RoleEnum.ADMIN))
    db_session.commit()
    return grupo


def _add_member(db_session, group, email):
    user = User(name=email, email=email)
    db_session.add(user)
    db_session.commit()
    db_session.add(GroupMember(group_id=group.id, user_id=user.id, role=RoleEnum.MEMBER))
    db_session.commit()
    return user


def _mark(db_session, group, user, weekday, minutes):
    row = Availability(group_id=group.id, weekday=weekday, start_minutes=minutes)
    db_session.add(row)
    db_session.flush()
    db_session.add(UserAvailability(user_id=user.id, availability_id=row.id))
    db_session.commit()
    return row


# --- conversiones puras -----------------------------------------------------


@pytest.mark.parametrize(
    "minutos,esperado",
    [(0, "00:00"), (480, "08:00"), (510, "08:30"), (1439, "23:59")],
)
def test_format_minutes(minutos, esperado):
    assert svc.format_minutes(minutos) == esperado


@pytest.mark.parametrize(
    "texto,esperado",
    [("08:00", 480), ("8:5", 485), (" 13:45 ", 825), ("09:30:00", 570)],
)
def test_parse_time_to_minutes(texto, esperado):
    assert svc.parse_time_to_minutes(texto) == esperado


@pytest.mark.parametrize("texto", ["", "no", "25:00", "08:60", None])
def test_parse_time_to_minutes_rechaza_basura(texto):
    with pytest.raises(ValueError):
        svc.parse_time_to_minutes(texto)


def test_generate_time_blocks(group):
    assert svc.generate_time_blocks(group) == [
        (0, "08:00 - 09:00"),
        (1, "09:00 - 10:00"),
    ]


def test_block_index_for(group):
    assert svc.block_index_for(group, 480) == 0
    assert svc.block_index_for(group, 540) == 1
    # 08:30 no arranca ningún bloque de esta grilla.
    assert svc.block_index_for(group, 510) is None


# --- guardado ---------------------------------------------------------------


def test_process_posted_availability_crea_bloques_y_marcas(db_session, group):
    user = _add_member(db_session, group, "guarda@example.com")

    guardados = svc.process_posted_availability(
        group.id,
        {"day_0_hour_0": "on", "day_1_hour_1": "on"},
        group,
        user.id,
        [0, 1],
    )
    db_session.commit()

    assert guardados == 2
    marcas = {
        (a.weekday, a.start_minutes)
        for a in Availability.query.filter_by(group_id=group.id).all()
    }
    assert marcas == {(0, 480), (1, 540)}
    assert UserAvailability.query.filter_by(user_id=user.id).count() == 2


def test_process_posted_availability_ignora_claves_fuera_de_la_grilla(db_session, group):
    user = _add_member(db_session, group, "fuera@example.com")

    guardados = svc.process_posted_availability(
        group.id,
        {"day_0_hour_9": "on", "day_5_hour_0": "on"},
        group,
        user.id,
        [0, 1],
    )
    db_session.commit()

    assert guardados == 0
    assert Availability.query.filter_by(group_id=group.id).count() == 0


def test_process_posted_availability_es_idempotente(db_session, group):
    user = _add_member(db_session, group, "idem@example.com")
    form = {"day_0_hour_0": "on"}

    assert svc.process_posted_availability(group.id, form, group, user.id, [0, 1]) == 1
    db_session.commit()
    # La segunda vez no hay cambio real: la marca ya existe.
    assert svc.process_posted_availability(group.id, form, group, user.id, [0, 1]) == 0
    db_session.commit()
    assert UserAvailability.query.filter_by(user_id=user.id).count() == 1


def test_clear_existing_availability_solo_toca_lo_visible(db_session, group):
    user = _add_member(db_session, group, "limpia@example.com")
    visible = _mark(db_session, group, user, 0, 480)
    fuera_de_rango = _mark(db_session, group, user, 0, 660)  # 11:00, fuera de la grilla
    dia_apagado = _mark(db_session, group, user, 5, 480)     # sábado, no está activo

    svc.clear_existing_availability(group, user.id, [0, 1])
    db_session.commit()

    activos = {
        ua.availability_id
        for ua in UserAvailability.query.filter_by(user_id=user.id).all()
    }
    assert visible.id not in activos
    assert fuera_de_rango.id in activos
    assert dia_apagado.id in activos


def test_marcar_de_nuevo_reusa_la_fila_oculta(db_session, group):
    user = _add_member(db_session, group, "reusa@example.com")
    _mark(db_session, group, user, 0, 480)

    svc.clear_existing_availability(group, user.id, [0, 1])
    svc.process_posted_availability(
        group.id, {"day_0_hour_0": "on"}, group, user.id, [0, 1]
    )
    db_session.commit()

    todas = UserAvailability.query.execution_options(include_deleted=True).filter_by(
        user_id=user.id
    ).all()
    assert len(todas) == 1
    assert todas[0].deleted_at is None


# --- cambios de grilla ------------------------------------------------------


def test_count_out_of_range_marks(db_session, group):
    user = _add_member(db_session, group, "rango@example.com")
    _mark(db_session, group, user, 0, 480)
    _mark(db_session, group, user, 0, 540)
    _mark(db_session, group, user, 1, 540)

    # Rango nuevo 09:00-10:00, solo lunes: quedan fuera la de 08:00 y la del martes.
    assert svc.count_out_of_range_marks(group.id, 540, 600, {0}) == 2


def test_count_out_of_range_marks_ignora_a_los_que_ya_no_son_miembros(db_session, group):
    ex = _add_member(db_session, group, "ex-rango@example.com")
    _mark(db_session, group, ex, 0, 480)
    GroupMember.query.filter_by(group_id=group.id, user_id=ex.id).first().soft_delete()
    db_session.commit()

    assert svc.count_out_of_range_marks(group.id, 540, 600, {0}) == 0


def test_remap_reparte_un_bloque_viejo_en_los_nuevos_que_solapa(db_session, group):
    user = _add_member(db_session, group, "remap@example.com")
    _mark(db_session, group, user, 0, 480)
    old_starts = group.block_starts()
    old_block_minutes = group.block_minutes

    # La grilla pasa a bloques de 30: 08:00-09:00 se reparte en 08:00 y 08:30.
    group.block_minutes = 30
    db_session.flush()
    remapeadas = svc.remap_availability_marks(group, old_starts, old_block_minutes, {0})
    db_session.commit()

    assert remapeadas == 1
    minutos = {
        a.start_minutes
        for a in Availability.query.filter_by(group_id=group.id, weekday=0).all()
        if UserAvailability.query.filter_by(availability_id=a.id, user_id=user.id).first()
    }
    assert minutos == {480, 510}


def test_remap_no_toca_los_dias_apagados(db_session, group):
    user = _add_member(db_session, group, "remap-dia@example.com")
    fila = _mark(db_session, group, user, 5, 480)
    old_starts = group.block_starts()

    group.block_minutes = 30
    db_session.flush()
    remapeadas = svc.remap_availability_marks(group, old_starts, 60, {0, 1})
    db_session.commit()

    assert remapeadas == 0
    marca = UserAvailability.query.filter_by(
        availability_id=fila.id, user_id=user.id
    ).first()
    assert marca is not None and marca.deleted_at is None


def test_remap_sin_bloques_nuevos_no_hace_nada(db_session, group):
    user = _add_member(db_session, group, "remap-vacio@example.com")
    _mark(db_session, group, user, 0, 480)
    old_starts = group.block_starts()

    group.end_minutes = group.start_minutes  # grilla vacía
    db_session.flush()

    assert svc.remap_availability_marks(group, old_starts, 60, {0}) == 0


# --- resumen ----------------------------------------------------------------


def test_get_availability_data_agrupa_por_bloque(db_session, group):
    ana = _add_member(db_session, group, "ana@example.com")
    beto = _add_member(db_session, group, "beto@example.com")
    fila = _mark(db_session, group, ana, 0, 480)
    db_session.add(UserAvailability(user_id=beto.id, availability_id=fila.id))
    db_session.commit()

    data = svc.get_availability_data(group.id)

    assert data[fila.id]["count_users"] == 2
    assert sorted(data[fila.id]["users"]) == sorted([ana.id, beto.id])


def test_get_availability_data_excluye_a_los_que_se_fueron(db_session, group):
    ex = _add_member(db_session, group, "ex@example.com")
    _mark(db_session, group, ex, 0, 480)
    GroupMember.query.filter_by(group_id=group.id, user_id=ex.id).first().soft_delete()
    db_session.commit()

    assert svc.get_availability_data(group.id) == {}


def test_get_availability_data_sin_group_id(db_session):  # pylint: disable=unused-argument
    assert svc.get_availability_data(None) == {}


def test_get_availability_data_respeta_el_limite(db_session, group):
    user = _add_member(db_session, group, "limite@example.com")
    _mark(db_session, group, user, 0, 480)
    _mark(db_session, group, user, 1, 480)

    assert len(svc.get_availability_data(group.id, limit=1)) == 1
    assert len(svc.get_availability_data(group.id)) == 2


def test_el_servicio_no_commitea_solo(db_session, group):
    """La transacción la maneja la ruta: un rollback debe deshacer todo."""
    user = _add_member(db_session, group, "tx@example.com")

    svc.process_posted_availability(
        group.id, {"day_0_hour_0": "on"}, group, user.id, [0, 1]
    )
    scheduler_db.session.rollback()

    assert Availability.query.filter_by(group_id=group.id).count() == 0
