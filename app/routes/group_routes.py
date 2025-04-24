def assign_colors_to_members(members):
    COLORS = ['bg-primary', 'bg-success', 'bg-warning', 'bg-danger', 'bg-info', 'bg-dark', 'bg-light', 'bg-secondary', 'bg-pink', 'bg-teal']
    return {member.user.id: COLORS[i % len(COLORS)] for i, member in enumerate(members)}
from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from app import scheduler_db
from app.models import Group, GroupMember, Availability, UserAvailability, RoleEnum
import uuid
from sqlalchemy.orm import joinedload

group_bp = Blueprint('groups', __name__, url_prefix='/group')

def convert_hour_to_integer(hour):
    """Convert a time string in 'HH:MM' format to a float representing hours."""
    try:
        hours, minutes = map(int, hour.split("-")[0].split(':'))
        return hours + minutes / 60
    except ValueError:
        raise ValueError("Invalid time format. Expected 'HH:MM'.")

def convert_float_to_time_string(hour):
    """Convert a float representing hours to a time string in 'HH:MM' format."""
    try:
        hour_on_clock = int(hour)
        minutes = int(round((hour - hour_on_clock) * 60))
        return f"{hour_on_clock:02}:{minutes:02}"
    except (ValueError, TypeError):
        raise ValueError("Invalid hour value. Expected a float.")

def get_availability_data(group_id):
    if not group_id:
        return {}

    results = (
        scheduler_db.session.query(
            Availability.id,
            Availability.weekday,
            Availability.hour,
            Availability.group_id,
            UserAvailability.user_id
        )
        .join(UserAvailability, UserAvailability.availability_id == Availability.id)
        .filter(Availability.group_id == group_id)
        .all()
    )

    data = {}
    for availability_id, weekday, hour, _, user_id in results:
        if availability_id not in data:
            data[availability_id] = {
                'availability': Availability(id=availability_id, weekday=weekday, hour=hour, group_id=group_id),
                'users': [],
                'count_users': 0
            }
        data[availability_id]['users'].append(user_id)
        data[availability_id]['count_users'] += 1


    sorted_data = dict(sorted(data.items(), key=lambda item: item[1]['count_users'], reverse=True))

    return sorted_data

@group_bp.route('/', methods=['GET'])
@login_required
def index():
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()

    return render_template('groups/index.html', groups=groups)

@group_bp.route('/<int:id>', methods=['GET'])
@login_required
def show(id):
    STARTING_HOUR = 8
    ENDING_HOUR = 19
    blocks = [f"{hour:02}:30 - {(hour + 1):02}:20" for hour in range(STARTING_HOUR, ENDING_HOUR)]

    group = Group.query.get_or_404(id)
    members = GroupMember.query.filter_by(group_id=group.id).all()
    color_map = assign_colors_to_members(members)
    user_info_map = {member.user.id: {'name': member.user.name, 'email': member.user.email} for member in members}
    
    membership = GroupMember.query.filter_by(group_id=group.id, user_id=current_user.id).first()
    is_admin = membership and membership.role == RoleEnum.ADMIN
    
    if group.owner_id == current_user.id or is_admin:
        availability = (
            scheduler_db.session.query(UserAvailability.user_id, Availability.weekday, Availability.hour)
            .join(Availability, UserAvailability.availability_id == Availability.id)
            .filter(Availability.group_id == group.id)
            .all()
        )
    else:
        availability = (
            scheduler_db.session.query(UserAvailability.user_id, Availability.weekday, Availability.hour)
            .join(Availability, Availability.id == UserAvailability.availability_id)
            .filter(Availability.group_id == group.id)
            .filter(UserAvailability.user_id == current_user.id)
            .all()
        )    
    selected = set()
    for user_id, weekday, hour in availability:
        block_index = int(hour - STARTING_HOUR)
        if 0 <= block_index < len(blocks):
            selected.add((weekday, blocks[block_index]))
    
    availability_data = get_availability_data(id)
    
    return render_template(
        'groups/show.html',
        group=group,
        availability=availability,
        selected=selected,
        blocks=blocks,
        convert_float_to_time_string=convert_float_to_time_string,
        availability_data=availability_data,
        color_map=color_map,
        user_info_map=user_info_map,
        is_admin=is_admin
    )

@group_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        group_name = request.form['group_name']
        
        join_token = uuid.uuid4().hex[:10]
        user_id = current_user.id

        new_group = Group(name=group_name, join_token=join_token, owner_id=user_id)
        scheduler_db.session.add(new_group)
        scheduler_db.session.commit()

        
        group_member = GroupMember(group_id=new_group.id, user_id=user_id, role=RoleEnum.ADMIN)
        scheduler_db.session.add(group_member)
        scheduler_db.session.commit()

        flash('Grupo creado con éxito. El link para unirse es: {}'.format(request.url_root + 'group/join/{}'.format(join_token)), 'success')
        return redirect(url_for('groups.show', id=new_group.id))
    return render_template('groups/create.html')

@group_bp.route('/join/<token>', methods=['GET'])
@login_required
def join(token):
    group = Group.query.filter_by(join_token=token).first()

    if not group:
        flash('Grupo no encontrado o token inválido.', 'danger')
        return redirect(url_for('groups.index'))

    user_id = current_user.id

    print(group, user_id)
    
    if GroupMember.query.filter_by(group_id=group.id, user_id=user_id).first():
        flash('Ya estás en este grupo.', 'info')
        return redirect(url_for('groups.show', id=group.id))

    
    new_member = GroupMember(group_id=group.id, user_id=user_id, role=RoleEnum.MEMBER)
    scheduler_db.session.add(new_member)
    scheduler_db.session.commit()

    flash('Te has unido al grupo con éxito.', 'success')
    return redirect(url_for('groups.show', id=group.id))

@group_bp.route('/<int:group_id>/members', methods=['GET'])
@login_required
def members(group_id):
    group = Group.query.get_or_404(group_id)
    members = GroupMember.query.filter_by(group_id=group.id).all()
    return render_template('groups/members.html', group=group, members=members)

@group_bp.route('/<int:group_id>/availability', methods=['GET', 'POST'])
@login_required
def availability(group_id):
    STARTING_HOUR = 8
    ENDING_HOUR = 19
    
    blocks = []
    for i, hour in enumerate(range(STARTING_HOUR, ENDING_HOUR)):
        blocks.append((i, f"{hour:02}:30 - {(hour + 1):02}:20"))

    BLOCK_COUNT = len(blocks)
    
    if request.method == 'POST':

        user_avails = scheduler_db.session.query(UserAvailability).join(Availability).filter(UserAvailability.user_id == current_user.id, Availability.group_id == group_id).all()
        for ua in user_avails:
            scheduler_db.session.delete(ua)
        scheduler_db.session.commit()
        
        count = 0
        for weekday in range(7):
            for block_index in range(BLOCK_COUNT):
                key = f'day_{weekday}_hour_{block_index}'
                if key in request.form:
                    hour_str = blocks[block_index][1].split(' - ')[0]
                    hour_as_float = convert_hour_to_integer(hour_str)
                    availability = Availability.query.filter_by(group_id=group_id, weekday=weekday, hour=hour_as_float).first()
                    if not availability:
                        availability = Availability(
                            group_id=group_id,
                            weekday=weekday,
                            hour=hour_as_float
                        )
                        scheduler_db.session.add(availability)
                        scheduler_db.session.commit()
                    user_availability = UserAvailability(user_id=current_user.id, availability_id=availability.id)
                    scheduler_db.session.add(user_availability)
                    count += 1
        print(f"Total availability blocks saved: {count}")
        scheduler_db.session.commit()
        saved_count = scheduler_db.session.query(UserAvailability).join(Availability).filter(UserAvailability.user_id == current_user.id, Availability.group_id == group_id).count()
        if saved_count == 0:
            flash('No se guardó ninguna disponibilidad. Verifica tu selección.', 'warning')
            return render_template('groups/availability.html', group_id=group_id, selected={}, blocks=blocks)
        else:
            flash(f'Disponibilidad actualizada con éxito. ({saved_count} bloques guardados)', 'success')
            return redirect(url_for('groups.show', id=group_id))

    user_availability = scheduler_db.session.query(UserAvailability.user_id, Availability.weekday, Availability.hour).join(Availability).join(Group).filter(UserAvailability.user_id == current_user.id, Availability.group_id == group_id).all()
    selected = set()
    for _, weekday, hour in user_availability:
        block_index = int(hour - STARTING_HOUR)
        if 0 <= block_index < len(blocks):
            selected.add((weekday, block_index))
        print(f"Selected availability: {selected}")
    return render_template('groups/availability.html', group_id=group_id, selected=selected, blocks=blocks)

@group_bp.route('/<int:group_id>/delete', methods=['POST'])
@login_required
def delete(group_id):
    group = Group.query.get_or_404(group_id)

    if group.owner_id != current_user.id:
        flash("No tienes permiso para eliminar este grupo.", "danger")
        return redirect(url_for('groups.show', id=group_id))

    availability_ids = [a.id for a in Availability.query.filter_by(group_id=group_id).all()]
    if availability_ids:
        UserAvailability.query.filter(UserAvailability.availability_id.in_(availability_ids)).delete(synchronize_session=False)

    Availability.query.filter_by(group_id=group_id).delete()
    GroupMember.query.filter_by(group_id=group_id).delete()


    scheduler_db.session.delete(group)
    scheduler_db.session.commit()

    flash("Grupo eliminado exitosamente.", "success")
    return redirect(url_for('groups.index'))

@group_bp.route('/<int:group_id>/leave', methods=['POST'])
@login_required
def leave(group_id):
    ua_ids = scheduler_db.session.query(UserAvailability.id).join(Availability).filter(
        UserAvailability.user_id == current_user.id,
        Availability.group_id == group_id
    ).all()
    ua_ids = [id for (id,) in ua_ids]
    if ua_ids:
        scheduler_db.session.query(UserAvailability).filter(UserAvailability.id.in_(ua_ids)).delete(synchronize_session=False)

    membership = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()
    if membership:
        scheduler_db.session.delete(membership)

    group = Group.query.get_or_404(group_id)

    if group.owner_id == current_user.id:
        remaining_members = GroupMember.query.filter_by(group_id=group_id).all()
        if remaining_members:
            group.owner_id = remaining_members[0].user_id
        else:
            # Delete all related availability and the group
            availability_ids = [a.id for a in Availability.query.filter_by(group_id=group_id).all()]
            if availability_ids:
                UserAvailability.query.filter(UserAvailability.availability_id.in_(availability_ids)).delete(synchronize_session=False)
            Availability.query.filter_by(group_id=group_id).delete()
            scheduler_db.session.delete(group)

    scheduler_db.session.commit()

    flash("Grupo abandonado exitosamente.", "success")
    return redirect(url_for('groups.index'))


@group_bp.route('/<int:group_id>/remove/<int:user_id>', methods=['POST'])
@login_required
def remove(group_id, user_id):
    ua_ids = scheduler_db.session.query(UserAvailability.id).join(Availability).filter(
        UserAvailability.user_id == user_id,
        Availability.group_id == group_id
    ).all()
    ua_ids = [id for (id,) in ua_ids]
    if ua_ids:
        scheduler_db.session.query(UserAvailability).filter(UserAvailability.id.in_(ua_ids)).delete(synchronize_session=False)

    membership = GroupMember.query.filter_by(user_id=user_id, group_id=group_id).first()
    if membership:
        scheduler_db.session.delete(membership)

    scheduler_db.session.commit()

    flash("Miembro eliminado exitosamente.", "success")
    return redirect(url_for('groups.show', id=group_id))


@group_bp.route('/<int:group_id>/update_role/<int:user_id>', methods=['POST'])
@login_required
def update_role(group_id, user_id):
    group = Group.query.get_or_404(group_id)

    if group.owner_id != current_user.id:
        flash("No tienes permiso para modificar los roles.", "danger")
        return redirect(url_for('groups.show', id=group_id))

    role_str = request.form.get('role')
    if role_str not in RoleEnum.__members__:
        flash("Rol inválido.", "danger")
        return redirect(url_for('groups.show', id=group_id))

    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first_or_404()
    member.role = RoleEnum[role_str]
    scheduler_db.session.commit()

    flash("Rol actualizado con éxito.", "success")
    return redirect(url_for('groups.show', id=group_id))

