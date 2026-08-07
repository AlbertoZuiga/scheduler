import enum

from app.extensions import scheduler_db
from app.models.mixins import SoftDeleteMixin


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

    def soft_delete_cascade(self):
        # La disponibilidad del usuario NO se arrastra: se conserva intacta para
        # que al reingresar al grupo recupere lo que había marcado.
        return list(self.categories)
