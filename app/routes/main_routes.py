from flask import Blueprint, current_app, jsonify, render_template
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import scheduler_db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("main/index.html")


@main_bp.route("/health")
def health():
    """Liveness + readiness: 503 si la BD no responde.

    El health check de docker-compose pegaba a `/`, que solo renderiza una
    plantilla estática: el contenedor se reportaba sano con Postgres caído.
    """
    try:
        scheduler_db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        # La sesión queda inutilizable tras el fallo: se descarta para no
        # arrastrar la transacción rota a la próxima request de este worker.
        scheduler_db.session.rollback()
        current_app.logger.exception("health: la base de datos no responde")
        return jsonify({"status": "error", "database": "down"}), 503
    return jsonify({"status": "ok", "database": "up"}), 200
