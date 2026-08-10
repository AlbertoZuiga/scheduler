"""Smoke tests: no dependen de OAuth real ni de una sesión autenticada."""


def test_landing_publica_responde_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_ruta_protegida_redirige_a_login(client):
    response = client.get("/groups/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
