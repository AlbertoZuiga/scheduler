from app import scheduler_db
import enum

class RoleEnum(enum.IntEnum):
    MEMBER = 0
    ADMIN = 1

class GroupMember(scheduler_db.Model):
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('group.id'), nullable=False)
    user_id = scheduler_db.Column(scheduler_db.Integer, scheduler_db.ForeignKey('user.id'), nullable=False)

    role = scheduler_db.Column(scheduler_db.Enum(RoleEnum), nullable=False, default=RoleEnum.MEMBER)

    group = scheduler_db.relationship('Group', backref='members')
    user = scheduler_db.relationship('User', backref='memberships')