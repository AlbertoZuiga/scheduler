"""
Rutas para la gestión de subgrupos optimizados.
"""
import csv
import io
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, abort, jsonify, make_response
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import HTTPException

from app.extensions import scheduler_db
from app.models import GroupMember
from app.models.subgroup import SubGroup, SubGroupMember, DivisionJob
from app.services.group_service import get_group_categories

from app.authz import (
    can_see_member_emails,
    display_name,
    require_group_permission,
    require_subgroup_access,
)
from app.permissions import PERM_EDIT_ALL, PERM_EDIT_OWN, PERM_VIEW_ALL, PERM_VIEW_OWN
from app.services.subgroup_service import (
    SubGroupService,
    add_subgroup_member,
    confirm_division,
    create_manual_subgroup,
    get_group_member_count,
    get_group_members_sorted,
    get_subgroup_member,
    move_subgroup_member,
    remove_subgroup_member,
    save_division_job,
    undo_last_division,
)


subgroup_bp = Blueprint("subgroups", __name__)

GROUP_SHOW_ENDPOINT = 'groups.show'
# Techo duro de subgrupos por división: evita que un num_groups gigante
# aloque listas y cicle miembros × grupos en el servicio (DoS).
MAX_NUM_GROUPS = 200
SUBGROUP_INDEX_ENDPOINT = 'subgroups.index'
# Largo de la columna `SubGroup.name` (String(200)): pasado ese punto el INSERT
# falla en la BD con DataError y el usuario ve un 500 crudo.
SUBGROUP_NAME_MAX_LENGTH = 200
SUBGROUP_NAME_TOO_LONG_MSG = (
    f'El nombre del subgrupo no puede superar los {SUBGROUP_NAME_MAX_LENGTH} caracteres.'
)


def _get_active_job_or_404(group_id, job_id):
    """Job vivo de este grupo, o 404.

    `query.get_or_404` resuelve por identity map y esquiva el filtro de borrado
    lógico: con él, un job de un grupo borrado (o jubilado por la retención)
    seguía siendo exportable.
    """
    return DivisionJob.query.filter_by(id=job_id, parent_group_id=group_id).first_or_404()



def _subgroups_index_redirect(group_id):
    return redirect(url_for(SUBGROUP_INDEX_ENDPOINT, group_id=group_id))


def _get_subgroup_or_404(group_id, subgroup_id):
    return SubGroup.query.filter_by(
        id=subgroup_id,
        parent_group_id=group_id,
    ).first_or_404()



def _without_emails(preview):
    """Copia del preview con el email de cada integrante vaciado."""
    return {
        **preview,
        'groups': [
            {
                **group_data,
                'members': [
                    {**member, 'email': ''}
                    for member in group_data.get('members', [])
                ],
            }
            for group_data in preview.get('groups', [])
        ],
    }

@subgroup_bp.route('/groups/<int:group_id>/subgroups/new', methods=['GET'])
@login_required
def new(group_id):
    """
    Renderiza el formulario para dividir el grupo en subgrupos.
    Requiere poder editar todos los subgrupos.
    """
    # Verificar permisos
    group, membership, _ = require_group_permission(group_id, PERM_EDIT_ALL)
    can_see_emails = can_see_member_emails(group, membership)
    
    categories = get_group_categories(group_id)
    categories_list = [{'id': cat.id, 'name': cat.name} for cat in categories]
    group_members = get_group_members_sorted(group_id)
    member_count = len(group_members)
    members_list = [
        {
            'id': member.user.id,
            'name': display_name(member.user, with_email=can_see_emails),
            # El email es dato de administración: EDIT_ALL no lo abre.
            'email': (
                member.user.email
                if can_see_emails or member.user.id == current_user.id
                else ''
            ),
            'member_id': member.id,
        }
        for member in group_members
    ]
    
    return render_template(
        'groups/subgroups/new.html',
        group=group,
        categories=categories,
        categories_json=categories_list,
        members_json=members_list,
        member_count=member_count
    )


@subgroup_bp.route('/groups/<int:group_id>/subgroups/generate', methods=['POST'])
@login_required
def generate(group_id):
    """
    Genera los subgrupos según la configuración recibida.
    Devuelve un preview JSON sin persistir en BD.
    """
    # Verificar permisos
    group, membership, _ = require_group_permission(group_id, PERM_EDIT_ALL)
    can_see_emails = can_see_member_emails(group, membership)

    try:
        config = request.get_json()
        
        # Validar configuración básica
        if not config:
            return jsonify({'error': 'Configuración no proporcionada'}), 400
        
        try:
            num_groups = int(config.get('num_groups'))
        except (TypeError, ValueError):
            return jsonify({'error': 'Número de grupos inválido'}), 400

        member_count = get_group_member_count(group_id)
        max_allowed = min(MAX_NUM_GROUPS, member_count) or 1
        if num_groups < 1 or num_groups > max_allowed:
            return jsonify({
                'error': f'Número de grupos inválido: debe estar entre 1 y {max_allowed}.'
            }), 400
        config['num_groups'] = num_groups

        required_membership_categories = config.get('required_membership_categories', [])
        if required_membership_categories is None:
            required_membership_categories = []
        if not isinstance(required_membership_categories, list):
            return jsonify({'error': 'required_membership_categories debe ser una lista'}), 400
        config['required_membership_categories'] = [str(category).strip() for category in required_membership_categories if str(category).strip()]
        
        # Crear servicio y generar subgrupos
        service = SubGroupService(group_id)
        preview = service.generate_subgroups(config)
        
        job = save_division_job(group_id, current_user.id, config, preview)
        scheduler_db.session.commit()
        preview['job_id'] = job.id

        # El preview persistido conserva el email (el export lo usa si el que
        # descarga es owner/admin); el que se manda al navegador, no.
        if not can_see_emails:
            preview = _without_emails(preview)

        return jsonify(preview), 200

    except HTTPException:
        raise

    except ValueError as e:
        # Mensaje de validación del servicio, pensado para el usuario.
        scheduler_db.session.rollback()
        return jsonify({'error': str(e)}), 400

    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception('Error de BD al generar subgrupos del grupo %s', group_id)
        return jsonify({'error': 'No se pudo generar la división.'}), 500


@subgroup_bp.route('/groups/<int:group_id>/subgroups/confirm', methods=['POST'])
@login_required
def confirm(group_id):
    """
    Confirma y persiste los subgrupos generados en la BD.
    """
    # Verificar permisos
    require_group_permission(group_id, PERM_EDIT_ALL)
    
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        
        if not job_id:
            return jsonify({'error': 'job_id no proporcionado'}), 400
        
        # Buscar el job (vivo y de este grupo)
        job = _get_active_job_or_404(group_id, job_id)
        
        if job.status == 'confirmed':
            return jsonify({'error': 'Este job ya fue confirmado'}), 400
        
        preview = job.result_json
        if not preview or 'groups' not in preview:
            return jsonify({'error': 'Preview inválido'}), 400

        created_subgroups = confirm_division(job)
        scheduler_db.session.commit()

        flash(f'Se crearon {len(created_subgroups)} subgrupos exitosamente.', 'success')
        return jsonify({
            'success': True,
            'subgroups': created_subgroups,
            'redirect_url': url_for(GROUP_SHOW_ENDPOINT, group_id=group_id)
        }), 200
        
    except HTTPException:
        raise

    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception('Error de BD al confirmar subgrupos del grupo %s', group_id)
        return jsonify({'error': 'No se pudieron confirmar los subgrupos.'}), 500


@subgroup_bp.route('/groups/<int:group_id>/subgroups/undo', methods=['POST'])
@login_required
def undo(group_id):
    """
    Revierte la última división confirmada.
    Elimina los subgrupos creados y marca el job como 'undone'.
    """
    # Verificar permisos
    require_group_permission(group_id, PERM_EDIT_ALL)
    
    try:
        last_job, subgroups = undo_last_division(group_id)

        if not last_job:
            return jsonify({'error': 'No hay divisiones confirmadas para deshacer'}), 400

        scheduler_db.session.commit()

        flash('División revertida exitosamente.', 'success')
        return jsonify({
            'success': True,
            'message': f'Se eliminaron {len(subgroups)} subgrupos.'
        }), 200
        
    except HTTPException:
        raise

    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception('Error de BD al deshacer la división del grupo %s', group_id)
        return jsonify({'error': 'No se pudo deshacer la división.'}), 500


@subgroup_bp.route('/groups/<int:group_id>/subgroups/export', methods=['GET'])
@login_required
def export(group_id):
    """
    Exporta los subgrupos a CSV.
    Parámetro opcional: job_id para exportar un preview específico.
    Si no se proporciona, exporta los subgrupos confirmados actuales.
    """
    # Verificar permisos
    group, membership, _ = require_group_permission(group_id, PERM_VIEW_ALL)
    # La columna de email solo va para owner/admin, igual que en la vista de
    # subgrupos y en groups.export_members_csv.
    can_see_emails = can_see_member_emails(group, membership)
    email_header = ['Usuario Email'] if can_see_emails else []

    job_id = request.args.get('job_id', type=int)
    
    try:
        if job_id:
            # Exportar preview de un job específico
            # El job tiene que seguir vivo y pertenecer a este grupo: si el
            # grupo se borró, la cascada lo ocultó y esta consulta ya no lo ve.
            job = _get_active_job_or_404(group_id, job_id)

            preview = job.result_json
            if not preview or 'groups' not in preview:
                abort(400)
            
            # Construir CSV del preview
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Subgrupo ID',
                'Subgrupo Nombre',
                'Usuario ID',
                'Usuario Nombre',
                *email_header,
                'Categorías',
                'Compatibilidad Promedio'
            ])
            
            for group_data in preview['groups']:
                subgroup_id = group_data['id']
                subgroup_name = group_data['name']
                compatibility_avg = group_data['compatibility_avg']
                
                for member in group_data['members']:
                    writer.writerow([
                        subgroup_id,
                        subgroup_name,
                        member['id'],
                        member['name'],
                        *([member.get('email', '')] if can_see_emails else []),
                        ', '.join(member.get('categories', [])),
                        compatibility_avg
                    ])
        else:
            # Exportar subgrupos confirmados actuales
            subgroups = SubGroup.query.filter_by(
                parent_group_id=group_id
            ).all()
            
            if not subgroups:
                flash('No hay subgrupos para exportar.', 'warning')
                return redirect(url_for(GROUP_SHOW_ENDPOINT, group_id=group_id))
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Subgrupo ID',
                'Subgrupo Nombre',
                'Usuario ID',
                'Usuario Nombre',
                *email_header,
                'Fecha Agregado'
            ])
            
            for subgroup in subgroups:
                for member in subgroup.members:
                    writer.writerow([
                        subgroup.id,
                        subgroup.name,
                        member.user_id,
                        display_name(member.user, with_email=can_see_emails),
                        *([member.user.email if member.user else ''] if can_see_emails else []),
                        member.added_at.isoformat() if member.added_at else ''
                    ])
        
        # Crear respuesta CSV
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=subgroups_group_{group_id}.csv'
        
        return response
        
    except HTTPException:
        raise

    except SQLAlchemyError:
        current_app.logger.exception('Error de BD al exportar subgrupos del grupo %s', group_id)
        flash('No se pudo exportar los subgrupos.', 'danger')
        return redirect(url_for(GROUP_SHOW_ENDPOINT, group_id=group_id))


@subgroup_bp.route('/groups/<int:group_id>/subgroups', methods=['GET'])
@login_required
def index(group_id):
    """
    Lista los subgrupos del grupo: todos con VIEW_ALL, solo el propio con VIEW_OWN.
    """
    # Verificar permisos
    group, membership, perms = require_group_permission(group_id, PERM_VIEW_OWN)
    can_view_all = PERM_VIEW_ALL in perms
    can_edit_all = PERM_EDIT_ALL in perms
    # Los emails del roster son dato de administración: el permiso extra de
    # subgrupos no los abre (la exportación de emails también quedó restringida
    # a owner/admin en groups.export_members_csv).
    can_see_emails = can_see_member_emails(group, membership)

    all_subgroups = (
        SubGroup.query.filter_by(parent_group_id=group_id)
        .options(selectinload(SubGroup.members).selectinload(SubGroupMember.user))
        .order_by(SubGroup.created_at.asc(), SubGroup.id.asc())
        .all()
    )
    subgroup_member_user_ids = {
        subgroup.id: {member.user_id for member in subgroup.members}
        for subgroup in all_subgroups
    }

    if can_view_all:
        subgroups = all_subgroups
    else:
        subgroups = [
            subgroup for subgroup in all_subgroups
            if current_user.id in subgroup_member_user_ids.get(subgroup.id, set())
        ]

    can_edit_own = PERM_EDIT_OWN in perms

    if can_edit_all:
        editable_subgroup_ids = {subgroup.id for subgroup in subgroups}
    elif can_edit_own:
        editable_subgroup_ids = {
            subgroup.id for subgroup in subgroups
            if current_user.id in subgroup_member_user_ids.get(subgroup.id, set())
        }
    else:
        editable_subgroup_ids = set()

    # Roster completo del grupo padre: necesario para el selector "Agregar
    # integrante" incluso con solo EDIT_OWN (el usuario puede sumar a
    # cualquier persona del grupo a SU subgrupo). El panel "sin subgrupo" y
    # las tarjetas de otros subgrupos siguen ocultas sin VIEW_ALL.
    group_members = (
        get_group_members_sorted(group_id)
        if can_view_all or editable_subgroup_ids else []
    )
    assigned_user_ids = {
        member.user_id
        for subgroup in all_subgroups
        for member in subgroup.members
    }
    members_without_subgroup = (
        [member for member in group_members if member.user_id not in assigned_user_ids]
        if can_view_all else []
    )

    return render_template(
        'groups/subgroups/index.html',
        group=group,
        subgroups=subgroups,
        # Destinos posibles de "mover persona": solo los subgrupos que el
        # usuario puede editar, que es lo que exige subgroups.move_member.
        move_targets=[s for s in all_subgroups if s.id in editable_subgroup_ids],
        group_members=group_members,
        subgroup_member_user_ids=subgroup_member_user_ids,
        members_without_subgroup=members_without_subgroup,
        can_view_all=can_view_all,
        can_edit_all=can_edit_all,
        can_see_emails=can_see_emails,
        editable_subgroup_ids=editable_subgroup_ids,
    )


@subgroup_bp.route('/groups/<int:group_id>/subgroups/create_manual', methods=['POST'])
@login_required
def create_manual(group_id):
    """
    Crea un subgrupo manual vacío para ajustes posteriores.
    """
    require_group_permission(group_id, PERM_EDIT_ALL)

    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Debes indicar un nombre para el subgrupo manual.', 'warning')
        return _subgroups_index_redirect(group_id)
    if len(name) > SUBGROUP_NAME_MAX_LENGTH:
        flash(SUBGROUP_NAME_TOO_LONG_MSG, 'warning')
        return _subgroups_index_redirect(group_id)

    try:
        create_manual_subgroup(group_id, name)
        scheduler_db.session.commit()
        flash(f'Subgrupo "{name}" creado correctamente.', 'success')
    except HTTPException:
        raise
    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception('Error de BD al crear subgrupo manual en el grupo %s', group_id)
        flash('No se pudo crear el subgrupo manual.', 'danger')

    return _subgroups_index_redirect(group_id)


@subgroup_bp.route('/groups/<int:group_id>/subgroups/<int:subgroup_id>/rename', methods=['POST'])
@login_required
def rename(group_id, subgroup_id):
    """
    Renombra un subgrupo existente.
    """
    _, _, subgroup, _ = require_subgroup_access(group_id, subgroup_id, edit=True)

    new_name = (request.form.get('name') or '').strip()
    if not new_name:
        flash('El nombre del subgrupo no puede estar vacío.', 'warning')
        return _subgroups_index_redirect(group_id)
    if len(new_name) > SUBGROUP_NAME_MAX_LENGTH:
        flash(SUBGROUP_NAME_TOO_LONG_MSG, 'warning')
        return _subgroups_index_redirect(group_id)

    subgroup.name = new_name

    try:
        scheduler_db.session.commit()
        flash(f'Subgrupo renombrado a "{new_name}".', 'success')
    except HTTPException:
        raise
    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception('Error de BD al renombrar el subgrupo %s', subgroup_id)
        flash('No se pudo renombrar el subgrupo.', 'danger')

    return _subgroups_index_redirect(group_id)


@subgroup_bp.route('/groups/<int:group_id>/subgroups/<int:subgroup_id>/delete', methods=['POST'])
@login_required
def delete(group_id, subgroup_id):
    """
    Elimina un subgrupo y sus membresías.
    """
    require_group_permission(group_id, PERM_EDIT_ALL)
    subgroup = _get_subgroup_or_404(group_id, subgroup_id)
    subgroup_name = subgroup.name

    try:
        subgroup.soft_delete()
        scheduler_db.session.commit()
        flash(f'Se eliminó el subgrupo "{subgroup_name}".', 'success')
    except HTTPException:
        raise
    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception('Error de BD al eliminar el subgrupo %s', subgroup_id)
        flash('No se pudo eliminar el subgrupo.', 'danger')

    return _subgroups_index_redirect(group_id)


@subgroup_bp.route('/groups/<int:group_id>/subgroups/<int:subgroup_id>/members/add', methods=['POST'])
@login_required
def add_member(group_id, subgroup_id):
    """
    Agrega manualmente un miembro del grupo a un subgrupo.
    """
    _, _, subgroup, _ = require_subgroup_access(group_id, subgroup_id, edit=True)
    user_id = request.form.get('user_id', type=int)

    if not user_id:
        flash('Selecciona una persona para agregar al subgrupo.', 'warning')
        return _subgroups_index_redirect(group_id)

    group_member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if not group_member:
        flash('La persona seleccionada no pertenece a este grupo.', 'danger')
        return _subgroups_index_redirect(group_id)

    if get_subgroup_member(subgroup.id, user_id):
        flash('Esa persona ya pertenece a este subgrupo.', 'info')
        return _subgroups_index_redirect(group_id)

    try:
        add_subgroup_member(subgroup.id, user_id)
        scheduler_db.session.commit()
        flash(
            f'{display_name(group_member.user, with_email=False)} fue agregado a "{subgroup.name}".',
            'success',
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception(
            'Error de BD al agregar al usuario %s en el subgrupo %s', user_id, subgroup_id
        )
        flash('No se pudo agregar la persona al subgrupo.', 'danger')

    return _subgroups_index_redirect(group_id)


@subgroup_bp.route('/groups/<int:group_id>/subgroups/<int:subgroup_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(group_id, subgroup_id, user_id):
    """
    Quita una persona de un subgrupo específico.
    """
    _, _, subgroup, _ = require_subgroup_access(group_id, subgroup_id, edit=True)
    membership = get_subgroup_member(subgroup.id, user_id)

    if not membership:
        flash('La persona ya no está en este subgrupo.', 'warning')
        return _subgroups_index_redirect(group_id)

    user = membership.user

    try:
        remove_subgroup_member(subgroup, user_id)
        scheduler_db.session.commit()
        flash(
            f'{display_name(user, with_email=False)} fue quitado de "{subgroup.name}".',
            'success',
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception(
            'Error de BD al quitar al usuario %s del subgrupo %s', user_id, subgroup_id
        )
        flash('No se pudo quitar la persona del subgrupo.', 'danger')

    return _subgroups_index_redirect(group_id)


@subgroup_bp.route('/groups/<int:group_id>/subgroups/<int:subgroup_id>/members/<int:user_id>/move', methods=['POST'])
@login_required
def move_member(group_id, subgroup_id, user_id):
    """
    Mueve una persona desde un subgrupo a otro dentro del mismo grupo.

    Origen y destino exigen permiso de edición: mover es agregar en el destino,
    y con solo lectura ahí el usuario estaría escribiendo en un subgrupo ajeno.
    En la práctica esto deja "mover" como acción de quien edita todo; con
    "_own" no hay dos subgrupos propios entre los cuales mover.
    """
    _, _, source_subgroup, _ = require_subgroup_access(group_id, subgroup_id, edit=True)
    target_subgroup_id = request.form.get('target_subgroup_id', type=int)

    if not target_subgroup_id:
        flash('Selecciona el subgrupo destino para mover a la persona.', 'warning')
        return _subgroups_index_redirect(group_id)

    if target_subgroup_id == source_subgroup.id:
        flash('El subgrupo destino debe ser distinto al origen.', 'warning')
        return _subgroups_index_redirect(group_id)

    _, _, target_subgroup, _ = require_subgroup_access(group_id, target_subgroup_id, edit=True)
    source_membership = get_subgroup_member(source_subgroup.id, user_id)

    if not source_membership:
        flash('La persona ya no pertenece al subgrupo de origen.', 'warning')
        return _subgroups_index_redirect(group_id)

    user = source_membership.user

    try:
        move_subgroup_member(source_subgroup, target_subgroup, user_id)
        scheduler_db.session.commit()
        flash(
            f'{display_name(user, with_email=False)} fue movido de "{source_subgroup.name}" a "{target_subgroup.name}".',
            'success',
        )
    except HTTPException:
        raise
    except SQLAlchemyError:
        scheduler_db.session.rollback()
        current_app.logger.exception(
            'Error de BD al mover al usuario %s del subgrupo %s al %s',
            user_id, subgroup_id, target_subgroup.id
        )
        flash('No se pudo mover la persona entre subgrupos.', 'danger')

    return _subgroups_index_redirect(group_id)
