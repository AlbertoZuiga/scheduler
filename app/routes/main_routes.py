from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.group import Group
from app.models.group_member import GroupMember

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('main/index.html')