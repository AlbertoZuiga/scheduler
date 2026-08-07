from app.extensions import scheduler_db
from app.models.mixins import SoftDeleteMixin


class Group(SoftDeleteMixin, scheduler_db.Model):    # pylint: disable=too-few-public-methods
    id = scheduler_db.Column(scheduler_db.Integer, primary_key=True)
    name = scheduler_db.Column(scheduler_db.String(150), nullable=False)
    join_token = scheduler_db.Column(scheduler_db.String(64), unique=True, nullable=False)
    owner_id = scheduler_db.Column(
        scheduler_db.Integer, scheduler_db.ForeignKey("user.id"), nullable=False
    )
    owner = scheduler_db.relationship("User", backref="groups")
    # Rango horario y días visibles en la grilla de disponibilidad del grupo.
    # El rango se guarda en minutos desde medianoche para permitir horas con
    # minutos (08:15, 13:45); `block_minutes` es la extensión de cada bloque.
    start_minutes = scheduler_db.Column(scheduler_db.Integer, nullable=False, default=510)
    end_minutes = scheduler_db.Column(scheduler_db.Integer, nullable=False, default=1170)
    block_minutes = scheduler_db.Column(scheduler_db.Integer, nullable=False, default=60)
    # CSV de índices de día (0=Lunes ... 6=Domingo) activos para el grupo.
    active_weekdays = scheduler_db.Column(
        scheduler_db.String(20), nullable=False, default="0,1,2,3,4,5,6"
    )
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

    def soft_delete_cascade(self):
        return [*self.members, *self.categories, *self.subgroups]

    def get_active_weekdays(self):
        """Devuelve la lista ordenada de índices de día (0=Lunes) activos para el grupo."""
        raw = (self.active_weekdays or "").strip()
        if not raw:
            return list(range(7))
        try:
            days = sorted({int(d) for d in raw.split(",") if d.strip() != "" and 0 <= int(d) <= 6})
        except ValueError:
            return list(range(7))
        return days or list(range(7))

    def block_starts(self):
        """Minutos desde medianoche en que arranca cada bloque de la grilla.

        Los bloques se colocan seguidos desde `start_minutes`; el último que no
        cabe entero antes de `end_minutes` se descarta.
        """
        if self.block_minutes <= 0 or self.end_minutes <= self.start_minutes:
            return []
        return list(
            range(self.start_minutes, self.end_minutes - self.block_minutes + 1, self.block_minutes)
        )
