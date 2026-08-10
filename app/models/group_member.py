import enum

from app.extensions import scheduler_db
from app.models.mixins import ACTIVE_ROWS, SoftDeleteMixin


class RoleEnum(enum.IntEnum):
    MEMBER = 0
    ADMIN = 1


class GroupMember(SoftDeleteMixin, scheduler_db.Model):    # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group.id"), nullable=False
    )
    user_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("user.id"), nullable=False
    )

    role = scheduler_db.Column(scheduler_db.Enum(RoleEnum), nullable=False, default=RoleEnum.MEMBER)

    group = scheduler_db.relationship("Group", back_populates="members")
    user = scheduler_db.relationship("User", back_populates="memberships")
    # Categories associated to this group member
    categories = scheduler_db.relationship(
        "GroupMemberCategory", back_populates="group_member", cascade="all, delete-orphan"
    )
    permission_grants = scheduler_db.relationship(
        "GroupPermissionGrant", back_populates="group_member", cascade="all, delete-orphan"
    )

    # El filtro global `deleted_at IS NULL` va en cada SELECT, así que los
    # índices de FK lo llevan como última columna (DATA-002).
    __table_args__ = (
        scheduler_db.Index(
            "ix_group_member_group_user_deleted", "group_id", "user_id", "deleted_at"
        ),
        scheduler_db.Index(
            "uq_group_member_active",
            "group_id",
            "user_id",
            unique=True,
            postgresql_where=ACTIVE_ROWS,
            sqlite_where=ACTIVE_ROWS,
        ),
    )

    def soft_delete_cascade(self):
        # La disponibilidad del usuario NO se arrastra: se conserva intacta para
        # que al reingresar al grupo recupere lo que había marcado.
        #
        # SubGroupMember no tiene group_id: sus filas se acotan a este grupo
        # cruzando por el subgrupo padre, para no sacarlo de subgrupos de otros
        # grupos donde sigue siendo miembro.
        from app.models.subgroup import SubGroup, SubGroupMember  # pylint: disable=import-outside-toplevel

        subgroup_memberships = (
            SubGroupMember.query
            .join(SubGroup, SubGroupMember.subgroup_id == SubGroup.id)
            .filter(
                SubGroup.parent_group_id == self.group_id,
                SubGroupMember.user_id == self.user_id,
            )
            .all()
        )
        return [*self.categories, *self.permission_grants, *subgroup_memberships]
