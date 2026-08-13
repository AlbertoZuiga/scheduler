from sqlalchemy import func

from app.extensions import scheduler_db
from app.models.mixins import _utcnow

# Acciones registradas. Son las que cambian quién puede hacer qué dentro de un
# grupo: hasta DATA-008 no dejaban rastro de quién las ejecutó.
ACTION_ROLE_CHANGED = "member.role_changed"
ACTION_PERMISSION_GRANTED = "permission.granted"
ACTION_PERMISSION_REVOKED = "permission.revoked"


class AuditLog(scheduler_db.Model):  # pylint: disable=too-few-public-methods
    """Registro append-only de las acciones sensibles sobre un grupo.

    No lleva borrado lógico ni `updated_at`: una bitácora que se puede editar o
    esconder no sirve como bitácora. Lo único que la borra es la desaparición
    física del grupo, por la cascada de la FK.

    `actor_id` es SET NULL para que el registro sobreviva al borrado de quien
    ejecutó la acción; `actor_email` guarda a quién apuntaba en ese momento.
    """

    __tablename__ = "audit_log"

    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer,
        scheduler_db.ForeignKey("group.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id = scheduler_db.Column(
        scheduler_db.Integer,
        scheduler_db.ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email = scheduler_db.Column(scheduler_db.String(150), nullable=False)
    action = scheduler_db.Column(scheduler_db.String(50), nullable=False)
    # Sobre quién recayó: ("member", group_member_id) o ("category", category_id).
    subject_type = scheduler_db.Column(scheduler_db.String(20), nullable=False)
    subject_id = scheduler_db.Column(scheduler_db.Integer, nullable=False)
    # Qué cambió exactamente: {"from": "MEMBER", "to": "ADMIN"} o {"level": ...}.
    detail = scheduler_db.Column(scheduler_db.JSON, nullable=True)
    created_at = scheduler_db.Column(
        scheduler_db.DateTime,
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )

    __table_args__ = (
        scheduler_db.Index("ix_audit_log_group_created", "group_id", "created_at"),
    )

    def __repr__(self):
        return (
            f"<AuditLog id={self.id} group_id={self.group_id} action={self.action} "
            f"subject={self.subject_type}:{self.subject_id}>"
        )


def record_action(group_id, actor, action, subject_type, subject_id, detail=None):
    """Encola una entrada de bitácora en la sesión abierta.

    No hace commit: la entrada tiene que viajar en la misma transacción que el
    cambio que describe, o quedaría bitácora sin hecho (o al revés).
    """
    scheduler_db.session.add(
        AuditLog(
            group_id=group_id,
            actor_id=actor.id,
            actor_email=actor.email,
            action=action,
            subject_type=subject_type,
            subject_id=subject_id,
            detail=detail,
        )
    )
