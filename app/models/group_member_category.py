from app.extensions import scheduler_db


class GroupMemberCategory(scheduler_db.Model):  # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_member_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group_member.id"), nullable=False
    )
    category_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("category.id"), nullable=False
    )

    group_member = scheduler_db.relationship("GroupMember", back_populates="categories")
    category = scheduler_db.relationship("Category")

    def __repr__(self):
        return f"<GroupMemberCategory id={self.id} group_member_id={self.group_member_id} category_id={self.category_id}>"