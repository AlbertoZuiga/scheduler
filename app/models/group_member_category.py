from app.extensions import scheduler_db
from app.models.mixins import ACTIVE_ROWS, SoftDeleteMixin


class GroupMemberCategory(SoftDeleteMixin, scheduler_db.Model):  # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_member_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group_member.id"), nullable=False
    )
    category_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("category.id"), nullable=False
    )

    group_member = scheduler_db.relationship("GroupMember", back_populates="categories")
    category = scheduler_db.relationship("Category", back_populates="assignments")

    __table_args__ = (
        scheduler_db.Index(
            "uq_group_member_category_active",
            "group_member_id",
            "category_id",
            unique=True,
            postgresql_where=ACTIVE_ROWS,
            sqlite_where=ACTIVE_ROWS,
        ),
    )

    def __repr__(self):
        return f"<GroupMemberCategory id={self.id} group_member_id={self.group_member_id} category_id={self.category_id}>"