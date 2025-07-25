from flask import Flask, flash, redirect, request, session, url_for
from flask_login import current_user

from app.extensions import scheduler_db, login_manager
from app.models.user import User
from app.routes import blueprints
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    scheduler_db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.unauthorized_handler
    def custom_unauthorized():
        if current_user.is_anonymous:
            flash("Necesitas iniciar sesión para acceder a esta página.", "warning")

        session["next_page"] = request.full_path
        return redirect(url_for("auth.login", next=request.full_path))

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    for bp in blueprints:
        app.register_blueprint(bp)

    return app


scheduler_app = create_app()
