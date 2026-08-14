"""Entropía, rotación y rate limit del `join_token`."""

# pylint: disable=redefined-outer-name
import pytest

from app import ratelimit
from app.extensions import scheduler_db
from app.models import Group, GroupMember, RoleEnum
from app.models.group import generate_join_token
from app.models.user import User


@pytest.fixture()
def ratelimit_client(app):
    """Cliente con el rate limit encendido (el default de la suite es apagado)."""
    previo = app.config.get("RATELIMIT_ENABLED")
    app.config["RATELIMIT_ENABLED"] = True
    ratelimit.reset()
    yield app.test_client()
    app.config["RATELIMIT_ENABLED"] = previo
    ratelimit.reset()


def _usuario(db_session, email):
    user = User(name=email, email=email)
    db_session.add(user)
    db_session.commit()
    return user


def test_el_token_nuevo_tiene_entropia_de_sobra():
    token = generate_join_token()
    # token_urlsafe(32) = 32 bytes -> 43 chars. El viejo eran 10 chars (40 bits).
    assert len(token) >= 40
    assert len(token) <= 64  # entra en Group.join_token, que es String(64)
    assert generate_join_token() != token


def test_crear_grupo_emite_un_token_largo(client, db_session):
    user = _usuario(db_session, "creador-token@example.com")
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True

    response = client.post("/groups/create", data={"group_name": "Grupo Nuevo"})

    assert response.status_code == 302
    group = Group.query.filter_by(name="Grupo Nuevo").first()
    assert group is not None
    assert len(group.join_token) >= 40


def test_los_tokens_viejos_siguen_funcionando(client, db_session):
    """Compatibilidad: un token de 10 chars ya emitido sigue uniendo al grupo."""
    duenio = _usuario(db_session, "duenio-viejo@example.com")
    invitado = _usuario(db_session, "invitado-viejo@example.com")
    group = Group(name="Grupo Legacy", owner_id=duenio.id, join_token="a1b2c3d4e5")
    db_session.add(group)
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(invitado.id)
        sess["_fresh"] = True

    response = client.post("/groups/join/a1b2c3d4e5")

    assert response.status_code == 302
    assert GroupMember.query.filter_by(group_id=group.id, user_id=invitado.id).first() is not None


def test_el_owner_rota_el_token_y_el_viejo_deja_de_servir(client, db_session):
    duenio = _usuario(db_session, "duenio-rota@example.com")
    invitado = _usuario(db_session, "invitado-rota@example.com")
    group = Group(name="Grupo Rotable", owner_id=duenio.id, join_token="tok-viejo")
    db_session.add(group)
    db_session.commit()
    db_session.add(GroupMember(group_id=group.id, user_id=duenio.id, role=RoleEnum.ADMIN))
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(duenio.id)
        sess["_fresh"] = True

    response = client.post(f"/groups/{group.id}/rotate_token")

    assert response.status_code == 302
    scheduler_db.session.refresh(group)
    assert group.join_token != "tok-viejo"
    assert len(group.join_token) >= 40

    # El link viejo ya no lleva a ningún grupo: rebota sin crear membresía.
    with client.session_transaction() as sess:
        sess["_user_id"] = str(invitado.id)
        sess["_fresh"] = True
    client.post("/groups/join/tok-viejo")
    assert GroupMember.query.filter_by(group_id=group.id, user_id=invitado.id).first() is None


def test_un_admin_que_no_es_owner_no_puede_rotar(client, db_session):
    duenio = _usuario(db_session, "duenio-noadmin@example.com")
    admin = _usuario(db_session, "admin-noowner@example.com")
    group = Group(name="Grupo Ajeno", owner_id=duenio.id, join_token="tok-ajeno")
    db_session.add(group)
    db_session.commit()
    db_session.add(GroupMember(group_id=group.id, user_id=admin.id, role=RoleEnum.ADMIN))
    db_session.commit()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin.id)
        sess["_fresh"] = True

    response = client.post(f"/groups/{group.id}/rotate_token")

    assert response.status_code == 403
    scheduler_db.session.refresh(group)
    assert group.join_token == "tok-ajeno"


def test_el_anonimo_no_puede_rotar(client, db_session):
    duenio = _usuario(db_session, "duenio-anon-rota@example.com")
    group = Group(name="Grupo Anon", owner_id=duenio.id, join_token="tok-anon-rota")
    db_session.add(group)
    db_session.commit()

    response = client.post(f"/groups/{group.id}/rotate_token")

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    scheduler_db.session.refresh(group)
    assert group.join_token == "tok-anon-rota"


def test_el_join_corta_con_429_al_pasarse_del_limite(ratelimit_client):
    """Adivinar tokens desde una IP se frena a los 20 intentos por ventana."""
    for _ in range(20):
        assert ratelimit_client.get("/groups/join/token-que-no-existe").status_code != 429

    response = ratelimit_client.get("/groups/join/token-que-no-existe")

    assert response.status_code == 429


def test_el_rate_limit_no_estorba_al_uso_normal(ratelimit_client, db_session):
    """Abrir el link de invitación un par de veces (rebote por OAuth) no corta."""
    duenio = _usuario(db_session, "duenio-limite@example.com")
    group = Group(name="Grupo Limite", owner_id=duenio.id, join_token="tok-limite")
    db_session.add(group)
    db_session.commit()

    for _ in range(3):
        assert ratelimit_client.get("/groups/join/tok-limite").status_code == 200


def test_el_contador_es_por_endpoint_y_por_ip(ratelimit_client):
    """Agotar la cuota desde una IP no deja afuera a las demás."""
    for _ in range(21):
        ratelimit_client.get("/groups/join/token-inventado")

    otra_ip = ratelimit_client.get(
        "/groups/join/token-inventado", environ_overrides={"REMOTE_ADDR": "10.0.0.9"}
    )

    assert otra_ip.status_code != 429
