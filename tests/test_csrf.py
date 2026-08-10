"""SEC-002: la protección CSRF rechaza mutaciones sin token.

El resto de la suite corre con `WTF_CSRF_ENABLED=False` (ver conftest) para no
tener que firmar cada POST; acá se enciende a propósito para verificar que la
protección existe y que las rutas mutantes ya no responden a GET.
"""

# pylint: disable=redefined-outer-name
import pytest

from app.extensions import scheduler_db
from app.models import Group, GroupMember
from app.models.user import User


@pytest.fixture()
def csrf_client(app):
    """Cliente con CSRF activo (el default de la suite es tenerlo apagado)."""
    previo = app.config.get("WTF_CSRF_ENABLED")
    app.config["WTF_CSRF_ENABLED"] = True
    yield app.test_client()
    app.config["WTF_CSRF_ENABLED"] = previo


@pytest.mark.parametrize(
    "path",
    [
        "/groups/1/delete",           # borrar grupo
        "/groups/1/update_role/2",    # cambiar rol
        "/groups/1/restore",
        "/groups/1/restore_member/2",
    ],
)
def test_post_sin_token_es_rechazado(csrf_client, path):
    response = csrf_client.post(path)
    assert response.status_code == 400


def test_post_sin_token_no_muta_nada(csrf_client, db_session):
    group = Group(name="Grupo CSRF", owner_id=1, join_token="tok-csrf")
    db_session.add(group)
    db_session.commit()

    response = csrf_client.post(f"/groups/{group.id}/delete")

    assert response.status_code == 400
    scheduler_db.session.refresh(group)
    assert group.deleted_at is None


@pytest.mark.parametrize(
    "path",
    ["/groups/1/restore", "/groups/1/restore_member/2"],
)
def test_restore_ya_no_muta_por_get(csrf_client, path):
    """GET sobre las rutas de restore: 405, ya no son disparables por <img>."""
    assert csrf_client.get(path).status_code == 405


def test_join_anonimo_rebota_al_login(csrf_client):
    """El link de invitación sigue siendo GET: el flujo OAuth vuelve a este mismo GET."""
    response = csrf_client.get("/groups/join/tok-inexistente")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_join_por_get_no_une_solo_confirma(csrf_client, db_session):
    """GET sobre el link de invitación: muestra confirmación y no crea membresía."""
    invitado = User(name="Invitado", email="invitado@example.com")
    duenio = User(name="Dueño", email="duenio@example.com")
    db_session.add_all([invitado, duenio])
    db_session.commit()
    group = Group(name="Grupo Join", owner_id=duenio.id, join_token="tok-join")
    db_session.add(group)
    db_session.commit()

    with csrf_client.session_transaction() as sess:
        sess["_user_id"] = str(invitado.id)
        sess["_fresh"] = True

    response = csrf_client.get("/groups/join/tok-join")

    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data
    assert GroupMember.query.filter_by(group_id=group.id, user_id=invitado.id).first() is None


def test_pagina_publica_expone_el_meta_token(csrf_client):
    response = csrf_client.get("/")
    assert response.status_code == 200
    assert b'name="csrf-token"' in response.data
