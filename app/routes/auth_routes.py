import os
import pathlib
from urllib.parse import urljoin, urlparse

import google.auth.transport.requests
import google.oauth2.id_token
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from google_auth_oauthlib.flow import Flow

from app.models.user import User
from config import Config

auth_bp = Blueprint("auth", __name__)

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _build_flow(state=None):
    if Config.DEBUG:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_secrets_file = os.path.join(
        pathlib.Path(__file__).parent.parent.parent, "client_secret.json"
    )
    return Flow.from_client_secrets_file(
        client_secrets_file=client_secrets_file,
        scopes=OAUTH_SCOPES,
        redirect_uri=f"{Config.URL}/auth/google/callback",
        state=state,
    )


@auth_bp.route("/login")
def login():
    """Pantalla de login: el salto a Google lo dispara el usuario, no el request.

    Antes esta ruta redirigía sola a Google, así que en redes lentas el usuario
    veía una pantalla en blanco y no sabía qué estaba pasando.
    """
    # `next` lo pone el unauthorized_handler y también los links de invitación
    # para anónimos; se guarda en sesión porque el rebote por Google pierde la query.
    next_url = request.args.get("next")
    if not next_url or not is_safe_url(next_url):
        next_url = None

    if current_user.is_authenticated:
        # Con sesión abierta en otra pestaña, el link de invitación igual tiene
        # que llevar a la invitación y no a "Mis Grupos".
        session.pop("next_page", None)
        return redirect(next_url or url_for("groups.index"))

    # Un `next_page` viejo de un login abandonado desviaría este intento.
    session.pop("next_page", None)
    if next_url:
        session["next_page"] = next_url

    return render_template("auth/login.html")


@auth_bp.route("/login/google")
def login_google():
    try:
        flow = _build_flow()
        authorization_url, state = flow.authorization_url()
    except Exception:  # pylint: disable=broad-except
        current_app.logger.exception("No se pudo iniciar el flujo OAuth con Google")
        return (
            render_template(
                "auth/error.html",
                message="No pudimos conectarnos con Google para iniciar sesión.",
            ),
            502,
        )

    session["state"] = state
    return redirect(authorization_url)


@auth_bp.route("/auth/google/callback")
def callback():
    state = session.pop("state", None)
    if not state or state != request.args.get("state"):
        flash("La sesión expiró, intenta de nuevo", "warning")
        return redirect(url_for("main.index"))

    try:
        flow = _build_flow(state=state)
        flow.fetch_token(authorization_response=request.url)

        request_session = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(
            flow.credentials.id_token, request_session, flow.client_config["client_id"]
        )
    except Exception:  # pylint: disable=broad-except
        current_app.logger.exception("Falló el intercambio de tokens con Google")
        return (
            render_template(
                "auth/error.html",
                message="No pudimos completar el inicio de sesión con Google.",
            ),
            400,
        )

    if id_info.get("email_verified") is not True:
        return (
            render_template(
                "auth/error.html",
                message=(
                    "La cuenta de Google que elegiste no tiene el email verificado. "
                    "Verifícalo en Google y vuelve a intentarlo."
                ),
            ),
            400,
        )

    user = User.get_or_create_from_oauth(id_info)
    if not user:
        current_app.logger.error("get_or_create_from_oauth devolvió None para un id_info válido")
        return (
            render_template(
                "auth/error.html",
                message="No pudimos crear tu cuenta a partir de los datos de Google.",
            ),
            400,
        )

    login_user(user)

    next_page = session.pop("next_page", None)
    if not next_page or not is_safe_url(next_page):
        next_page = url_for("groups.index")
    return redirect(next_page)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))
