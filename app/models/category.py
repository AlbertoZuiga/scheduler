from app.extensions import scheduler_db


class Category(scheduler_db.Model):  # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("group.id"), nullable=False
    )
    name = scheduler_db.Column(scheduler_db.String(150), nullable=False)

    group = scheduler_db.relationship("Group", back_populates="categories")

    def __repr__(self):
        return f"<Category id={self.id} group_id={self.group_id} name={self.name}>"