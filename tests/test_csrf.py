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
    duenio = User(name="Dueño csrf delete", email="duenio-csrf-delete@example.com")
    db_session.add(duenio)
    db_session.commit()
    group = Group(name="Grupo CSRF", owner_id=duenio.id, join_token="tok-csrf")
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


def test_join_anonimo_ve_el_grupo_y_el_login(csrf_client, db_session):
    """UX-003: el invitado anónimo ve a qué grupo lo invitaron antes de loguearse."""
    duenio = User(name="Dueño anónimo", email="duenio-anon@example.com")
    db_session.add(duenio)
    db_session.commit()
    group = Group(name="Grupo Anónimo", owner_id=duenio.id, join_token="tok-anon")
    db_session.add(group)
    db_session.commit()

    response = csrf_client.get("/groups/join/tok-anon")

    assert response.status_code == 200
    assert "Grupo Anónimo".encode() in response.data
    assert b"/login?next=" in response.data


def test_join_anonimo_por_post_es_rechazado_sin_token_csrf(csrf_client, db_session):
    """Con CSRF activo el POST anónimo ni siquiera llega a la vista."""
    duenio = User(name="Dueño csrf", email="duenio-csrf@example.com")
    db_session.add(duenio)
    db_session.commit()
    group = Group(name="Grupo CSRF join", owner_id=duenio.id, join_token="tok-csrf-join")
    db_session.add(group)
    db_session.commit()

    response = csrf_client.post("/groups/join/tok-csrf-join")

    assert response.status_code == 400
    assert GroupMember.query.filter_by(group_id=group.id).first() is None


def test_join_anonimo_por_post_va_al_login(client, db_session):
    """El POST sin sesión no une a nadie: manda al login preservando el destino."""
    duenio = User(name="Dueño post", email="duenio-post@example.com")
    db_session.add(duenio)
    db_session.commit()
    group = Group(name="Grupo Post", owner_id=duenio.id, join_token="tok-post")
    db_session.add(group)
    db_session.commit()

    response = client.post("/groups/join/tok-post")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    with client.session_transaction() as sess:
        assert sess["next_page"] == "/groups/join/tok-post"
    assert GroupMember.query.filter_by(group_id=group.id).first() is None


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
