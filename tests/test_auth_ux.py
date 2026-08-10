"""UX-001: /login es una pantalla real, no un redirect ciego a Google."""

from app.models.user import User


def test_login_renderiza_pantalla_con_boton_de_google(client):
    response = client.get("/login")

    assert response.status_code == 200
    assert "Iniciar sesión con Google".encode() in response.data
    assert b'href="/login/google"' in response.data


def test_login_guarda_el_destino_seguro_en_la_sesion(client):
    client.get("/login?next=/groups/join/tok-x")

    with client.session_transaction() as sess:
        assert sess["next_page"] == "/groups/join/tok-x"


def test_login_ignora_un_destino_externo(client):
    client.get("/login?next=https://evil.example.com/")

    with client.session_transaction() as sess:
        assert "next_page" not in sess


def test_login_descarta_un_destino_viejo(client):
    client.get("/login?next=/groups/join/tok-viejo")
    client.get("/login")

    with client.session_transaction() as sess:
        assert "next_page" not in sess


def test_login_con_sesion_abierta_respeta_el_next(client, db_session):
    usuario = User(name="Ya logueado", email="ya-logueado@example.com")
    db_session.add(usuario)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(usuario.id)

    response = client.get("/login?next=/groups/join/tok-invitacion")

    assert response.status_code == 302
    assert response.headers["Location"] == "/groups/join/tok-invitacion"
