import enum

from app.extensions import scheduler_db


class RoleEnum(enum.IntEnum):
    MEMBER = 0
    ADMIN = 1


class GroupMember(scheduler_db.Model):    # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group.id"), nullable=False
    )
    user_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("user.id"), nullable=False
    )

    role = scheduler_db.Column(scheduler_db.Enum(RoleEnum), nullable=False, default=RoleEnum.MEMBER)

    group = scheduler_db.relationship("Group", backref="members")
    user = scheduler_db.relationship("User", backref="memberships")
