"""
Rutas para la gestión de subgrupos optimizados.
"""
import csv
import io
from flask import Blueprint, flash, redirect, render_template, request, url_for, abort, jsonify, make_response
from flask_login import current_user, login_required

from app.extensions import scheduler_db
from app.models import Group, GroupMember, RoleEnum, Category
from app.models.subgroup import SubGroup, SubGroupMember, DivisionJob
from app.authz import require_group_admin_or_owner, require_group_member
from app.services.subgroup_service import SubGroupService


subgroup_bp = Blueprint("subgroups", __name__)


@subgroup_bp.route('/groups/<int:group_id>/subgroups/new')
@login_required
def new(group_id):
    """
    Renderiza el formulario para dividir el grupo en subgrupos.
    Solo accesible por Owners/Admins.
    """
    # Verificar permisos
    group, _ = require_group_admin_or_owner(group_id)
    
    # Obtener categorías disponibles en el grupo
    categories = Category.query.filter_by(group_id=group_id).all()
    
    # Convertir categorías a formato serializable
    categories_list = [{'id': cat.id, 'name': cat.name} for cat in categories]
    
    # Contar miembros del grupo
    member_count = GroupMember.query.filter_by(
        group_id=group_id
    ).count()
    
    return render_template(
        'groups/subgroups/new.html',
        group=group,
        categories=categories,
        categories_json=categories_list,
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
    require_group_admin_or_owner(group_id)
    
    try:
        config = request.get_json()
        
        # Validar configuración básica
        if not config:
            return jsonify({'error': 'Configuración no proporcionada'}), 400
        
        num_groups = config.get('num_groups')
        if not num_groups or num_groups < 1:
            return jsonify({'error': 'Número de grupos inválido'}), 400
        
        # Crear servicio y generar subgrupos
        service = SubGroupService(group_id)
        preview = service.generate_subgroups(config)
        
        # Guardar job en BD con estado 'pending'
        job = DivisionJob(
            parent_group_id=group_id,
            created_by=current_user.id,
            config_json=config,
            result_json=preview,
            status='pending'
        )
        scheduler_db.session.add(job)
        scheduler_db.session.commit()
        
        # Añadir job_id al preview
        preview['job_id'] = job.id
        
        return jsonify(preview), 200
        
    except Exception as e:
        scheduler_db.session.rollback()
        return jsonify({'error': f'Error al generar subgrupos: {str(e)}'}), 500


@subgroup_bp.route('/groups/<int:group_id>/subgroups/confirm', methods=['POST'])
@login_required
def confirm(group_id):
    """
    Confirma y persiste los subgrupos generados en la BD.
    """
    # Verificar permisos
    require_group_admin_or_owner(group_id)
    
    try:
        data = request.get_json()
        job_id = data.get('job_id')
        
        if not job_id:
            return jsonify({'error': 'job_id no proporcionado'}), 400
        
        # Buscar el job
        job = DivisionJob.query.get_or_404(job_id)
        
        if job.parent_group_id != group_id:
            return jsonify({'error': 'Job no corresponde a este grupo'}), 400
        
        if job.status == 'confirmed':
            return jsonify({'error': 'Este job ya fue confirmado'}), 400
        
        # Obtener preview del job
        preview = job.result_json
        if not preview or 'groups' not in preview:
            return jsonify({'error': 'Preview inválido'}), 400
        
        # Persistir subgrupos
        created_subgroups = []
        
        for group_data in preview['groups']:
            # Crear SubGroup
            subgroup = SubGroup(
                parent_group_id=group_id,
                name=group_data['name'],
                auto_generated=True,
                meta={
                    'compatibility_avg': group_data['compatibility_avg'],
                    'rules_status': group_data['rules_status']
                }
            )
            scheduler_db.session.add(subgroup)
            scheduler_db.session.flush()  # Para obtener el ID
            
            # Añadir miembros
            for member_data in group_data['members']:
                subgroup_member = SubGroupMember(
                    subgroup_id=subgroup.id,
                    user_id=member_data['id']
                )
                scheduler_db.session.add(subgroup_member)
            
            created_subgroups.append(subgroup.to_dict())
        
        # Actualizar estado del job
        job.status = 'confirmed'
        scheduler_db.session.commit()
        
        flash(f'Se crearon {len(created_subgroups)} subgrupos exitosamente.', 'success')
        return jsonify({
            'success': True,
            'subgroups': created_subgroups,
            'redirect_url': url_for('groups.show', group_id=group_id)
        }), 200
        
    except Exception as e:
        scheduler_db.session.rollback()
        return jsonify({'error': f'Error al confirmar subgrupos: {str(e)}'}), 500


@subgroup_bp.route('/groups/<int:group_id>/subgroups/undo', methods=['POST'])
@login_required
def undo(group_id):
    """
    Revierte la última división confirmada.
    Elimina los subgrupos creados y marca el job como 'undone'.
    """
    # Verificar permisos
    require_group_admin_or_owner(group_id)
    
    try:
        # Buscar el último job confirmado
        last_job = DivisionJob.query.filter_by(
            parent_group_id=group_id,
            status='confirmed'
        ).order_by(DivisionJob.timestamp.desc()).first()
        
        if not last_job:
            return jsonify({'error': 'No hay divisiones confirmadas para deshacer'}), 400
        
        # Eliminar todos los subgrupos autogenerados del grupo
        subgroups = SubGroup.query.filter_by(
            parent_group_id=group_id,
            auto_generated=True
        ).all()
        
        for subgroup in subgroups:
            scheduler_db.session.delete(subgroup)
        
        # Marcar job como undone
        last_job.status = 'undone'
        scheduler_db.session.commit()
        
        flash('División revertida exitosamente.', 'success')
        return jsonify({
            'success': True,
            'message': f'Se eliminaron {len(subgroups)} subgrupos.'
        }), 200
        
    except Exception as e:
        scheduler_db.session.rollback()
        return jsonify({'error': f'Error al deshacer división: {str(e)}'}), 500


@subgroup_bp.route('/groups/<int:group_id>/subgroups/export')
@login_required
def export(group_id):
    """
    Exporta los subgrupos a CSV.
    Parámetro opcional: job_id para exportar un preview específico.
    Si no se proporciona, exporta los subgrupos confirmados actuales.
    """
    # Verificar permisos
    require_group_admin_or_owner(group_id)
    
    job_id = request.args.get('job_id', type=int)
    
    try:
        if job_id:
            # Exportar preview de un job específico
            job = DivisionJob.query.get_or_404(job_id)
            
            if job.parent_group_id != group_id:
                abort(403)
            
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
                'Usuario Email',
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
                        member.get('email', ''),
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
                return redirect(url_for('groups.show', group_id=group_id))
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                'Subgrupo ID',
                'Subgrupo Nombre',
                'Usuario ID',
                'Usuario Nombre',
                'Usuario Email',
                'Fecha Agregado'
            ])
            
            for subgroup in subgroups:
                for member in subgroup.members:
                    writer.writerow([
                        subgroup.id,
                        subgroup.name,
                        member.user_id,
                        member.user.name if member.user else '',
                        member.user.email if member.user else '',
                        member.added_at.isoformat() if member.added_at else ''
                    ])
        
        # Crear respuesta CSV
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=subgroups_group_{group_id}.csv'
        
        return response
        
    except Exception as e:
        flash(f'Error al exportar: {str(e)}', 'danger')
        return redirect(url_for('groups.show', group_id=group_id))


@subgroup_bp.route('/groups/<int:group_id>/subgroups')
@login_required
def index(group_id):
    """
    Lista todos los subgrupos del grupo.
    """
    # Verificar permisos
    group, _ = require_group_admin_or_owner(group_id)
    subgroups = SubGroup.query.filter_by(parent_group_id=group_id).all()
    
    return render_template(
        'groups/subgroups/index.html',
        group=group,
        subgroups=subgroups
    )
