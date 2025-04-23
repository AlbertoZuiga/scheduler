from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.group import Group
from app.models.group_member import GroupMember

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('main/index.html')

@main_bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()

    return render_template('main/dashboard.html', groups=groups)