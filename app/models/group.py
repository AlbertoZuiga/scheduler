from app.extensions import scheduler_db


class Group(scheduler_db.Model):    # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    name = scheduler_db.Column(scheduler_db.String(150), nullable=False)
    join_token = scheduler_db.Column(scheduler_db.String(64), unique=True, nullable=False)
    owner_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("user.id"), nullable=False
    )
    owner = scheduler_db.relationship("User", backref="groups")
    members = scheduler_db.relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )
    # Categories that belong to this group
    categories = scheduler_db.relationship(
        "Category", back_populates="group", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Group id={self.id} name={self.name} "
            f"owner={self.owner.name} "
            f"member_count={len(self.members)}>"
        )
