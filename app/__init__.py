import hashlib
import logging
import os
import secrets
import sys

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import login_manager, scheduler_db
from app.models.user import User
from app.routes import blueprints
from app.soft_delete import install_soft_delete_filter
from config import Config

csrf = CSRFProtect()


def _configure_logging(app):
    """Manda los logs a stdout (lo que Render recolecta) con nivel por env."""
    level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s"))
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


def _csp_nonce():
    """Nonce de CSP de esta request: el mismo para el header y para las plantillas.

    Se genera perezosamente y se guarda en `g` porque lo piden dos lados: cada
    `<script nonce="{{ csp_nonce() }}">` al renderizar y el `after_request` al
    armar el header. Si difirieran, el navegador bloquearía el script.
    """
    nonce = g.get("csp_nonce")
    if nonce is None:
        nonce = secrets.token_urlsafe(16)
        g.csp_nonce = nonce
    return nonce


def _content_security_policy(nonce, *, debug=False):
    """CSP por nonce: cada `<script>` inline de la app lleva el nonce de la request.

    La app tiene ~1450 líneas de JS inline repartidas en 11 bloques, así que la
    opción barata era `script-src 'unsafe-inline'`, que no protege de nada: es
    exactamente lo que un XSS necesita. Con nonce esos bloques siguen donde
    están (no hay que extraerlos a archivos) y un `<script>` inyectado no
    corre, porque el atacante no puede adivinar el nonce.

    `style-src` sí lleva `'unsafe-inline'`: quedan dos `<style>` y un atributo
    `style=` en las plantillas, y el atributo no se puede cubrir con nonce
    (el nonce solo aplica a elementos). El riesgo que deja abierto es
    inyección de CSS, muy por debajo de la ejecución de script.

    `img-src` acepta `https:` porque el avatar del usuario lo sirve Google
    desde hosts de `googleusercontent.com` que rotan.
    """
    directivas = [
        "default-src 'self'",
        f"script-src 'self' 'nonce-{nonce}'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: https:",
        "font-src 'self'",
        # Todos los fetch de la app (autosave, bulk_assign, categorías) son al
        # mismo origen; no hay API externa que consultar desde el navegador.
        "connect-src 'self'",
        "base-uri 'self'",
        "form-action 'self'",
        # El login con Google es un redirect del servidor, no un iframe ni un
        # POST cross-origin: nada de esto lo toca.
        "frame-ancestors 'none'",
        "object-src 'none'",
    ]
    if not debug:
        directivas.append("upgrade-insecure-requests")
    return "; ".join(directivas)


def _register_security_headers(app):
    """Headers de seguridad en toda respuesta (fase 9 del roadmap)."""

    app.jinja_env.globals["csp_nonce"] = _csp_nonce

    @app.after_request
    def set_security_headers(response):
        response.headers["Content-Security-Policy"] = _content_security_policy(
            _csp_nonce(), debug=app.config["DEBUG"]
        )
        # Sin esto el navegador puede adivinar el tipo de un archivo subido o de
        # una respuesta y ejecutarlo como HTML/JS.
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Los links de invitación viajan en la URL: no se filtran a terceros.
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # `frame-ancestors` ya lo cubre en navegadores actuales; X-Frame-Options
        # queda para los que no leen CSP nivel 2.
        response.headers["X-Frame-Options"] = "DENY"
        # HSTS solo sobre HTTPS real: mandarlo en dev (http) no hace nada, y
        # mandarlo desde un host que después no sirve TLS deja al usuario sin
        # poder entrar durante un año.
        if not app.config["DEBUG"] and request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


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
    _register_security_headers(app)
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
        """El rate limit del join_token corta acá, con una página usable."""
        retry_after = str(getattr(g, "rate_limit_retry_after", 300))
        if _wants_json():
            resp = jsonify({"error": "Demasiados intentos. Espera unos minutos."})
            resp.headers["Retry-After"] = retry_after
            return resp, 429
        resp = make_response(render_template("429.html"), 429)
        resp.headers["Retry-After"] = retry_after
        return resp

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
        return scheduler_db.session.get(User, int(user_id))

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

    Antes el factory corría en el cuerpo del módulo, así que importar
    cualquier submódulo (`app.models.user`, un test, `alembic/env.py`) levantaba
    la app entera con sus blueprints como efecto de import. Ahora ese costo lo
    paga solo quien pide `scheduler_app`, y el esquema es responsabilidad
    exclusiva de `python -m app.db.migrate`.
    """
    if name == "scheduler_app":
        return get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
