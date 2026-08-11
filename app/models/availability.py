from app.extensions import scheduler_db
from app.models.mixins import TimestampMixin


class Availability(TimestampMixin, scheduler_db.Model):    # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    group_id = scheduler_db.Column(
        scheduler_db.Integer,
        scheduler_db.ForeignKey("group.id", ondelete="CASCADE"),
        nullable=False,
    )
    weekday = scheduler_db.Column(scheduler_db.Integer, nullable=False)
    hour = scheduler_db.Column(scheduler_db.Float, nullable=False)

    # Sin borrado lógico en esta tabla: el unique es total, no parcial.
    __table_args__ = (
        scheduler_db.Index("ix_availability_group", "group_id"),
        scheduler_db.UniqueConstraint(
            "group_id", "weekday", "hour", name="uq_availability_slot"
        ),
    )

    def __repr__(self):
        return f"<Availability group_id={self.group_id} weekday={self.weekday} hour={self.hour}>"
