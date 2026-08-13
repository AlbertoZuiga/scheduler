"""Headers de seguridad (fase 9): CSP por nonce + el resto del set.

El test que importa es `test_todo_script_inline_lleva_el_nonce_de_la_request`:
la app tiene ~1450 líneas de JS inline, y un bloque sin nonce no falla en
pytest ni en el render — falla en el navegador, en silencio, cuando la CSP lo
bloquea. Acá se verifica mecánicamente sobre el HTML servido.
"""

# pylint: disable=redefined-outer-name
import re

import pytest

from app.extensions import scheduler_db
from app.models import Group, GroupMember, RoleEnum
from app.models.user import User

SCRIPT_TAG = re.compile(rb"<script\b[^>]*>")


def _directivas(response):
    csp = response.headers["Content-Security-Policy"]
    return {
        parte.strip().split(" ", 1)[0]: parte.strip()
        for parte in csp.split(";")
        if parte.strip()
    }


@pytest.fixture()
def grupo_con_owner(db_session):
    """Owner logueado + grupo del que es miembro: habilita las vistas con más JS."""
    owner = User(name="Owner headers", email="owner-headers@example.com")
    db_session.add(owner)
    db_session.commit()
    group = Group(name="Grupo Headers", owner_id=owner.id, join_token="tok-headers")
    db_session.add(group)
    db_session.commit()
    db_session.add(GroupMember(group_id=group.id, user_id=owner.id, role=RoleEnum.ADMIN))
    db_session.commit()
    scheduler_db.session.refresh(group)
    return owner, group


def test_headers_basicos_en_toda_respuesta(client):
    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_headers_tambien_en_las_paginas_de_error(client):
    response = client.get("/ruta-que-no-existe")

    assert response.status_code == 404
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers


def test_la_csp_no_permite_script_inline_sin_nonce(client):
    directivas = _directivas(client.get("/"))

    script_src = directivas["script-src"]
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src
    assert "'nonce-" in script_src


def test_la_csp_cierra_frames_objetos_y_base(client):
    directivas = _directivas(client.get("/"))

    assert directivas["frame-ancestors"] == "frame-ancestors 'none'"
    assert directivas["object-src"] == "object-src 'none'"
    assert directivas["base-uri"] == "base-uri 'self'"
    assert directivas["form-action"] == "form-action 'self'"


def test_la_csp_deja_pasar_los_fetch_al_mismo_origen(client):
    """Autosave de disponibilidad y bulk_assign son fetch same-origin."""
    directivas = _directivas(client.get("/"))

    assert directivas["connect-src"] == "connect-src 'self'"


def test_la_csp_deja_pasar_el_avatar_de_google(client):
    """El `<img>` del navbar apunta a googleusercontent, que rota de host."""
    directivas = _directivas(client.get("/"))

    assert "https:" in directivas["img-src"]


def test_el_nonce_cambia_en_cada_request(client):
    primero = _directivas(client.get("/"))["script-src"]
    segundo = _directivas(client.get("/"))["script-src"]

    assert primero != segundo


def _assert_scripts_con_nonce(response, path):
    assert response.status_code == 200, f"{path} devolvió {response.status_code}"
    nonce = re.search(r"'nonce-([^']+)'", response.headers["Content-Security-Policy"]).group(1)
    tags = SCRIPT_TAG.findall(response.data)
    assert tags, f"{path} no trajo ningún <script>: el test dejó de probar algo"
    sin_nonce = [tag for tag in tags if f'nonce="{nonce}"'.encode() not in tag]
    assert not sin_nonce, f"scripts sin el nonce en {path}: {sin_nonce}"


@pytest.mark.parametrize(
    "path",
    ["/", "/groups/", "/groups/{group_id}", "/groups/{group_id}/availability",
     "/groups/{group_id}/members", "/groups/{group_id}/subgroups",
     "/groups/{group_id}/subgroups/new"],
)
def test_todo_script_inline_lleva_el_nonce_de_la_request(client, grupo_con_owner, path):
    """Un `<script>` sin nonce lo bloquea el navegador sin avisar: acá falla."""
    owner, group = grupo_con_owner
    with client.session_transaction() as sess:
        sess["_user_id"] = str(owner.id)
        sess["_fresh"] = True

    _assert_scripts_con_nonce(client.get(path.format(group_id=group.id)), path)


@pytest.mark.parametrize("path", ["/login", "/groups/join/tok-headers"])
# `grupo_con_owner` está por su efecto: crea el grupo que responde a /join.
def test_las_paginas_anonimas_tambien_llevan_el_nonce(  # pylint: disable=unused-argument
    client, grupo_con_owner, path
):
    """El login y el link de invitación se ven sin sesión: heredan base.html."""
    _assert_scripts_con_nonce(client.get(path), path)


def test_no_quedan_handlers_inline_en_el_html(client, grupo_con_owner):
    """`onclick=` y compañía no los cubre el nonce: la CSP los bloquearía."""
    owner, group = grupo_con_owner
    with client.session_transaction() as sess:
        sess["_user_id"] = str(owner.id)
        sess["_fresh"] = True

    for path in ("/", "/groups/", f"/groups/{group.id}"):
        data = client.get(path).data
        for handler in (b"onclick=", b"onchange=", b"onsubmit=", b"oninput="):
            assert handler not in data, f"{handler.decode()} en {path}"


def test_hsts_no_se_manda_sobre_http(client):
    """Mandar HSTS desde un host sin TLS deja al usuario sin poder entrar."""
    assert "Strict-Transport-Security" not in client.get("/").headers


def test_hsts_se_manda_sobre_https(client):
    """Detrás del proxy de Render (ProxyFix marca is_secure) sí va."""
    response = client.get("/", base_url="https://localhost")

    assert response.headers["Strict-Transport-Security"] == (
        "max-age=31536000; includeSubDomains"
    )
