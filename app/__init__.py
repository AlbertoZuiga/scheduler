import hashlib
import logging
import os
import sys

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import scheduler_db, login_manager
from app.models.user import User
from app.routes import blueprints
from app.soft_delete import install_soft_delete_filter
from config import Config

csrf = CSRFProtect()


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


def _register_static_url(app):
    """Expone `static_url()` en las plantillas: url_for + ?v=<hash del archivo>.

    El CSS compilado y el JS se sirven con el nombre de siempre, así que un
    deploy que cambia su contenido no invalida la copia cacheada del navegador.
    El hash del contenido en el query string sí: cambia solo cuando el archivo
    cambia, y el navegador lo trata como una URL nueva.
    """
    versions = {}

    def static_url(filename):
        version = versions.get(filename)
        if version is None:
            path = os.path.join(app.static_folder, filename)
            try:
                with open(path, "rb") as handle:
                    version = hashlib.sha256(handle.read()).hexdigest()[:10]
            except OSError:
                # El archivo puede no existir todavía (main.css lo genera el
                # build de Tailwind): se sirve sin versión antes que romper. El
                # fallo NO se memoriza: si se cacheara, el worker que atendió una
                # request antes del build serviría el estático sin versión el
                # resto de su vida, que es justo lo que esto viene a evitar.
                return url_for("static", filename=filename)
            versions[filename] = version
        url = url_for("static", filename=filename)
        return f"{url}?v={version}"

    app.jinja_env.globals["static_url"] = static_url


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
    _register_static_url(app)
    scheduler_db.init_app(app)
    # Protege por defecto todo POST/PUT/PATCH/DELETE. El token viaja en el hidden
    # `csrf_token` de los forms o en el header `X-CSRFToken` de los fetch.
    csrf.init_app(app)
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

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        """Token CSRF ausente, inválido o expirado: 400 con una página usable.

        El caso normal no es un ataque sino una sesión que caducó con el
        formulario abierto, así que la página explica que hay que reintentar.
        """
        app.logger.warning(
            "CSRF rechazado en %s %s: %s", request.method, request.path, error.description
        )
        if _wants_json():
            return jsonify({"error": "Token CSRF inválido o expirado. Recarga la página."}), 400
        return render_template("csrf_error.html", reason=error.description), 400

    @app.errorhandler(404)
    def not_found_error(error):
        """Maneja errores 404 Not Found."""
        if _wants_json():
            return jsonify({"error": "Recurso no encontrado."}), 404
        return render_template("404.html"), 404

    @app.errorhandler(429)
    def too_many_requests_error(error):
        """SEC-009: el rate limit del join corta acá, con una página usable."""
        if _wants_json():
            return jsonify({"error": "Demasiados intentos. Espera unos minutos."}), 429
        return render_template("429.html"), 429

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


_scheduler_app = None


def get_app():
    """La app, construida a lo más una vez por proceso.

    `create_app()` no es idempotente: registra blueprints, así que llamarlo dos
    veces sobre el mismo proceso los duplicaría. Por eso el resultado se memoriza acá.
    """
    global _scheduler_app  # pylint: disable=global-statement
    if _scheduler_app is None:
        _scheduler_app = create_app()
    return _scheduler_app


def __getattr__(name):
    """PEP 562: `from app import scheduler_app` recién acá construye la app.

    Antes el factory corría en el cuerpo del módulo (ARCH-002), así que importar
    cualquier submódulo (`app.models.user`, un test, `alembic/env.py`) levantaba
    la app entera con sus blueprints como efecto de import. Ahora ese costo lo
    paga solo quien pide `scheduler_app`, y el esquema es responsabilidad
    exclusiva de `python -m app.db.migrate`.
    """
    if name == "scheduler_app":
        return get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
