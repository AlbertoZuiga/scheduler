from app.extensions import scheduler_db
from app.models.mixins import SoftDeleteMixin


class GroupPermissionGrant(SoftDeleteMixin, scheduler_db.Model):  # pylint: disable=too-few-public-methods
    """Concesión puntual de un permiso extra sobre subgrupos.

    Otorgada por el owner del grupo a un miembro específico o a una categoría
    (todos los miembros que la tengan asignada, dinámicamente). Exactamente
    uno de `group_member_id` / `category_id` debe estar seteado; se valida en
    la ruta que crea la concesión, no acá.
    """
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group.id"), nullable=False
    )
    permission = scheduler_db.Column(scheduler_db.String(50), nullable=False)
    group_member_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group_member.id"), nullable=True
    )
    category_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("category.id"), nullable=True
    )
    # Discriminador del sujeto ("m<id>" / "c<id>") para poder hacer UNIQUE. No
    # se puede usar (group_member_id, category_id) directamente: uno de los dos
    # es siempre NULL y MySQL considera distintos dos NULL, así que la
    # restricción no se aplicaría nunca.
    subject_key = scheduler_db.Column(scheduler_db.String(20), nullable=False)

    group_member = scheduler_db.relationship("GroupMember", back_populates="permission_grants")
    category = scheduler_db.relationship("Category", back_populates="permission_grants")

    __table_args__ = (
        scheduler_db.Index("idx_perm_grant_group", "group_id", "permission"),
        scheduler_db.Index(
            "ix_perm_grant_member_cat_deleted",
            "group_member_id",
            "category_id",
            "deleted_at",
        ),
        # Incluye las concesiones revocadas (soft delete): la ruta que otorga
        # revive la fila oculta en vez de insertar una nueva.
        scheduler_db.UniqueConstraint(
            "group_id", "permission", "subject_key", name="uq_perm_grant_subject"
        ),
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.subject_key is None:
            self.subject_key = (
                f"m{self.group_member_id}"
                if self.group_member_id is not None
                else f"c{self.category_id}"
            )

    def __repr__(self):
        return (
            f"<GroupPermissionGrant id={self.id} group_id={self.group_id} "
            f"permission={self.permission} group_member_id={self.group_member_id} "
            f"category_id={self.category_id}>"
        )
