import os
import pathlib
from urllib.parse import urljoin, urlparse

import google.auth.transport.requests
import google.oauth2.id_token
from flask import Blueprint, redirect, request, session, url_for
from flask_login import login_required, login_user, logout_user
from google_auth_oauthlib.flow import Flow

from app.models.user import User
from config import Config

auth_bp = Blueprint("auth", __name__)


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


@auth_bp.route("/login")
def login():
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    client_secrets_file = os.path.join(
        pathlib.Path(__file__).parent.parent.parent, "client_secret.json"
    )

    flow = Flow.from_client_secrets_file(
        client_secrets_file=client_secrets_file,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ],
        redirect_uri=f"{Config.URL}/auth/google/callback",
    )

    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@auth_bp.route("/auth/google/callback")
def callback():
    client_secrets_file = os.path.join(
        pathlib.Path(__file__).parent.parent.parent, "client_secret.json"
    )
    flow = Flow.from_client_secrets_file(
        client_secrets_file=client_secrets_file,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "openid",
        ],
        redirect_uri=f"{Config.URL}/auth/google/callback",
    )

    flow.fetch_token(authorization_response=request.url)

    if session["state"] != request.args["state"]:
        return "Estado inválido", 500

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()
    id_info = google.oauth2.id_token.verify_oauth2_token(
        credentials._id_token, request_session, flow.client_config["client_id"]
    )

    user = User.get_or_create_from_oauth(id_info)
    if user:
        login_user(user)

        next_page = session.pop("next_page", None)
        if not next_page or not is_safe_url(next_page):
            next_page = url_for("groups.index")
        return redirect(next_page)
    else:
        return "No se pudo autenticar el usuario", 400


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.index"))
