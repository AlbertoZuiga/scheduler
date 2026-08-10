import logging
import os
import sys

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import scheduler_db, login_manager
from app.models.user import User
from app.routes import blueprints
from app.soft_delete import install_soft_delete_filter
from config import Config


def _configure_logging(app):
    """Manda los logs a stdout (lo que Render recolecta) con nivel por env."""
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
    ))
    app.logger.handlers = [handler]
    app.logger.setLevel(level)
    app.logger.propagate = False


def _wants_json():
    """True si el cliente espera JSON (fetch de la app o consumidor de API)."""
    if request.path.startswith("/api/"):
        return True
    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    accept = request.accept_mimetypes
    return accept["application/json"] > accept["text/html"]


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    _configure_logging(app)
    # Detrás del proxy TLS de Render: sin esto request.is_secure es False y
    # url_for(_external=True) genera http://.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    scheduler_db.init_app(app)
    install_soft_delete_filter()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.unauthorized_handler
    def custom_unauthorized():
        if current_user.is_anonymous:
            flash("Necesitas iniciar sesión para acceder a esta página.", "warning")

        session["next_page"] = request.full_path
        return redirect(url_for("auth.login", next=request.full_path))

    @app.errorhandler(403)
    def forbidden_error(error):
        """Maneja errores 403 Forbidden sin degradarlos a 302."""
        if _wants_json():
            return jsonify({"error": "No tienes permiso para realizar esta acción."}), 403
        # Un redirect con status 403 no lo sigue el navegador: dejaría al usuario
        # en la página stub de werkzeug. Se renderiza la página de error, que
        # además muestra el flash que authz.py deja antes del abort(403).
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        """Maneja errores 404 Not Found."""
        if _wants_json():
            return jsonify({"error": "Recurso no encontrado."}), 404
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        # Flask ya loguea la excepción con stack trace en app.logger antes de
        # llegar acá (app.log_exception), así que no se vuelve a loguear.
        scheduler_db.session.rollback()
        if _wants_json():
            return jsonify({"error": "Error interno del servidor."}), 500
        return render_template("500.html"), 500

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    for bp in blueprints:
        app.register_blueprint(bp)

    return app


scheduler_app = create_app()
