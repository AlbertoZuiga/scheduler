from app.extensions import scheduler_db
from app.models.mixins import ACTIVE_ROWS, SoftDeleteMixin


class UserAvailability(SoftDeleteMixin, scheduler_db.Model):    # pylint: disable=too-few-public-methods
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

    __table_args__ = (
        scheduler_db.Index(
            "ix_user_availability_user_avail_deleted",
            "user_id",
            "availability_id",
            "deleted_at",
        ),
        scheduler_db.Index(
            "uq_user_availability_active",
            "user_id",
            "availability_id",
            unique=True,
            postgresql_where=ACTIVE_ROWS,
            sqlite_where=ACTIVE_ROWS,
        ),
    )
