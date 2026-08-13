from sqlalchemy import func

from app.extensions import scheduler_db
from app.models.mixins import ACTIVE_ROWS, SoftDeleteMixin, TimestampMixin


class Category(TimestampMixin, SoftDeleteMixin, scheduler_db.Model):  # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer,
        scheduler_db.ForeignKey("group.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = scheduler_db.Column(scheduler_db.String(150), nullable=False)

    group = scheduler_db.relationship("Group", back_populates="categories")
    assignments = scheduler_db.relationship(
        "GroupMemberCategory",
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    permission_grants = scheduler_db.relationship(
        "GroupPermissionGrant",
        back_populates="category",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # El nombre es único sin distinguir mayúsculas: es como lo compara la ruta
    # que crea categorías (`_category_exists`), así que el índice va sobre
    # lower(name) para que la BD imponga exactamente el mismo criterio.
    __table_args__ = (
        scheduler_db.Index("ix_category_group_deleted", "group_id", "deleted_at"),
        scheduler_db.Index(
            "uq_category_active_name",
            "group_id",
            func.lower(name),
            unique=True,
            postgresql_where=ACTIVE_ROWS,
            sqlite_where=ACTIVE_ROWS,
        ),
    )

    def soft_delete_cascade(self):
        return [*self.assignments, *self.permission_grants]

    def __repr__(self):
        return f"<Category id={self.id} group_id={self.group_id} name={self.name}>"