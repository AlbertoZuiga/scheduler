from app.routes.auth_routes import auth_bp
from app.routes.group_routes import group_bp
from app.routes.main_routes import main_bp
from app.routes.category_routes import category_bp

blueprints = [main_bp, auth_bp, group_bp, category_bp]
