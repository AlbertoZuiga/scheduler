"""El health check toca la base de datos."""

from sqlalchemy.exc import OperationalError

from app.extensions import scheduler_db


def test_health_responde_ok_con_la_bd_arriba(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ROTO_A_PROPOSITO", "database": "up"}


def test_health_responde_503_con_la_bd_caida(client, monkeypatch):
    def falla(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("conexión rechazada"))

    monkeypatch.setattr(scheduler_db.session, "execute", falla)
    monkeypatch.setattr(scheduler_db.session, "rollback", lambda *a, **k: None)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json() == {"status": "error", "database": "down"}
