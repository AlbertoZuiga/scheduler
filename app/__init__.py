from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from flask_login import LoginManager

scheduler_db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    scheduler_db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.unauthorized_handler
    def custom_unauthorized():
        from flask import request, session, redirect, url_for, flash
        from flask_login import current_user

        # Solo mostrar el mensaje si el usuario es anónimo de verdad
        if current_user.is_anonymous:
            flash("Necesitas iniciar sesión para acceder a esta página.", "warning")

        session['next_page'] = request.full_path
        return redirect(url_for('auth.login', next=request.full_path))

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User

        return User.query.get(int(user_id))

    from app.routes import blueprints
    for bp in blueprints:
        app.register_blueprint(bp)

    return app

app = create_app()