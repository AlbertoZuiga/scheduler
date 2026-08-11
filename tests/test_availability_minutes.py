"""DATA-005: el inicio del bloque se guarda en minutos enteros.

El caso que rompía con el Float de horas es una grilla cuyo bloque no divide a
60: un bloque que arranca a los 500 minutos se guardaba como 8.3333… y al
volver a leerlo no calzaba con ningún inicio de la grilla, así que la marca
desaparecía de la vista.
"""
# pylint: disable=redefined-outer-name
import re

import pytest

from app.models import Availability, Group, GroupMember, User, UserAvailability
from app.routes.group_routes import _block_index_for, format_minutes


@pytest.fixture()
def grupo_20min(db_session):
    """Grilla de 08:20 a 10:00 en bloques de 20 minutos (500, 520, ... 580)."""
    user = User(email="minutos@example.com", name="M")
    db_session.add(user)
    db_session.flush()

    group = Group(
        name="Veinte",
        join_token="tok-min",
        owner_id=user.id,
        start_minutes=500,
        end_minutes=600,
        block_minutes=20,
    )
    db_session.add(group)
    db_session.flush()
    db_session.add(GroupMember(group_id=group.id, user_id=user.id))
    db_session.commit()

    return {"group": group, "user": user}


@pytest.fixture()
def como_usuario(client, grupo_20min):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(grupo_20min["user"].id)
        sess["_fresh"] = True
    return client


def test_la_columna_es_entera(db_session, grupo_20min):
    fila = Availability(group_id=grupo_20min["group"].id, weekday=0, start_minutes=500)
    db_session.add(fila)
    db_session.commit()
    db_session.expire_all()

    guardado = db_session.get(Availability, fila.id)
    assert guardado.start_minutes == 500
    assert isinstance(guardado.start_minutes, int)


def test_el_bloque_no_divisible_por_60_calza(grupo_20min):
    """8h20 = 500 minutos: con float de horas esto era 8.3333… y no calzaba."""
    group = grupo_20min["group"]
    assert group.block_starts() == [500, 520, 540, 560, 580]
    assert _block_index_for(group, 500) == 0
    assert _block_index_for(group, 540) == 2
    assert _block_index_for(group, 505) is None


def test_guardar_y_releer_conserva_la_marca(como_usuario, grupo_20min, db_session):
    group_id = grupo_20min["group"].id

    respuesta = como_usuario.post(
        f"/groups/{group_id}/availability",
        data={"day_0_hour_0": "on", "day_2_hour_2": "on"},
    )
    assert respuesta.status_code == 302

    guardadas = {
        (fila.weekday, fila.start_minutes)
        for fila in Availability.query.filter_by(group_id=group_id).all()
    }
    assert guardadas == {(0, 500), (2, 540)}
    assert UserAvailability.query.count() == 2

    # La grilla vuelve a marcar exactamente esos dos bloques.
    pagina = como_usuario.get(f"/groups/{group_id}/availability")
    assert pagina.status_code == 200
    marcados = {
        (int(dia), int(bloque))
        for dia, bloque in re.findall(
            r'id="availability_(\d+)_(\d+)"[^>]*\n?[^>]*checked', pagina.data.decode()
        )
    }
    assert marcados == {(0, 0), (2, 2)}


def test_el_resumen_muestra_la_hora_correcta(como_usuario, grupo_20min):
    group_id = grupo_20min["group"].id
    como_usuario.post(f"/groups/{group_id}/availability", data={"day_0_hour_0": "on"})

    pagina = como_usuario.get(f"/groups/{group_id}")

    assert pagina.status_code == 200
    assert b'data-start-minutes="500"' in pagina.data
    assert "08:20".encode() in pagina.data


def test_el_csv_cuenta_los_bloques_marcados(como_usuario, grupo_20min):
    group_id = grupo_20min["group"].id
    como_usuario.post(
        f"/groups/{group_id}/availability",
        data={"day_0_hour_0": "on", "day_1_hour_4": "on"},
    )

    csv_response = como_usuario.get(f"/groups/{group_id}/members/export.csv")

    assert csv_response.status_code == 200
    fila = csv_response.data.decode().strip().splitlines()[1]
    assert fila.endswith(",2")


def test_format_minutes(grupo_20min):
    assert format_minutes(500) == "08:20"
    assert format_minutes(0) == "00:00"
    with pytest.raises(ValueError):
        format_minutes("no es un número")
