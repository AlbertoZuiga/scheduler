"""
Modelos para subgrupos optimizados y división automática de grupos.
"""
from datetime import datetime
from app.extensions import scheduler_db


class SubGroup(scheduler_db.Model):
    """
    Representa un subgrupo creado automáticamente a partir de un grupo padre.
    """
    __tablename__ = 'subgroups'

    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    parent_group_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('group.id', ondelete='CASCADE'), nullable=False)
    name = scheduler_db.Column(scheduler_db.String(200), nullable=False)
    auto_generated = scheduler_db.Column(scheduler_db.Boolean, default=True, nullable=False)
    meta = scheduler_db.Column(scheduler_db.JSON, default=dict)  # Almacena compatibilidad promedio, reglas cumplidas, etc.
    created_at = scheduler_db.Column(scheduler_db.DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    parent_group = scheduler_db.relationship('Group', backref=scheduler_db.backref('subgroups', lazy='dynamic', cascade='all, delete-orphan'))
    members = scheduler_db.relationship('SubGroupMember', back_populates='subgroup', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<SubGroup {self.name} (parent: {self.parent_group_id})>'

    def to_dict(self):
        """Serializa el subgrupo a diccionario."""
        return {
            'id': self.id,
            'parent_group_id': self.parent_group_id,
            'name': self.name,
            'auto_generated': self.auto_generated,
            'meta': self.meta,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'member_count': len(self.members)
        }


class SubGroupMember(scheduler_db.Model):
    """
    Tabla de relación many-to-many entre SubGroup y User.
    Permite que un usuario pertenezca a múltiples subgrupos si allow_multiple_membership=True.
    """
    __tablename__ = 'subgroup_members'

    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    subgroup_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('subgroups.id', ondelete='CASCADE'), nullable=False)
    user_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    added_at = scheduler_db.Column(scheduler_db.DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    subgroup = scheduler_db.relationship('SubGroup', back_populates='members')
    user = scheduler_db.relationship('User', backref=scheduler_db.backref('subgroup_memberships', lazy='dynamic'))

    # Constraint único si allow_multiple_membership=False (se valida en lógica de negocio)
    __table_args__ = (
        scheduler_db.Index('idx_subgroup_user', 'subgroup_id', 'user_id'),
    )

    def __repr__(self):
        return f'<SubGroupMember subgroup={self.subgroup_id} user={self.user_id}>'

    def to_dict(self):
        """Serializa la membresía a diccionario."""
        return {
            'id': self.id,
            'subgroup_id': self.subgroup_id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'user_email': self.user.email if self.user else None,
            'added_at': self.added_at.isoformat() if self.added_at else None
        }


class DivisionJob(scheduler_db.Model):
    """
    Historial de trabajos de división automática.
    Permite hacer undo y tracking de configuraciones previas.
    """
    __tablename__ = 'division_jobs'

    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    parent_group_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('group.id', ondelete='CASCADE'), nullable=False)
    created_by = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    config_json = scheduler_db.Column(scheduler_db.JSON, nullable=False)  # Configuración de entrada (num_groups, rules, etc.)
    result_json = scheduler_db.Column(scheduler_db.JSON, nullable=True)   # Resultado completo (preview)
    status = scheduler_db.Column(scheduler_db.String(50), default='pending', nullable=False)  # pending, confirmed, undone
    timestamp = scheduler_db.Column(scheduler_db.DateTime, default=datetime.utcnow, nullable=False)

    # Relaciones
    parent_group = scheduler_db.relationship('Group', backref=scheduler_db.backref('division_jobs', lazy='dynamic'))
    creator = scheduler_db.relationship('User', backref=scheduler_db.backref('division_jobs_created', lazy='dynamic'))

    def __repr__(self):
        return f'<DivisionJob {self.id} group={self.parent_group_id} status={self.status}>'

    def to_dict(self):
        """Serializa el job a diccionario."""
        return {
            'id': self.id,
            'parent_group_id': self.parent_group_id,
            'created_by': self.created_by,
            'creator_name': self.creator.name if self.creator else None,
            'config': self.config_json,
            'result': self.result_json,
            'status': self.status,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
