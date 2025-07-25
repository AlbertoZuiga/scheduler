from app.extensions import scheduler_db


class UserAvailability(scheduler_db.Model):
    __tablename__ = "user_availability"
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    user_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("user.id"), nullable=False
    )
    availability_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("availability.id"), nullable=False
    )

    user = scheduler_db.relationship("User", backref="availabilities")
    availability = scheduler_db.relationship("Availability", backref="users")
