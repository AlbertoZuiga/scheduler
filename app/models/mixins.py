from datetime import datetime

from sqlalchemy import text

from app.extensions import scheduler_db

# Predicado de los índices unique parciales de las tablas con borrado lógico.
# Una fila oculta comparte la clave con la activa que la reemplazó, así que un
# unique simple rechazaría reingresos legítimos. Postgres es el motor de
# producción; `sqlite_where` replica la misma garantía en los tests.
ACTIVE_ROWS = text("deleted_at IS NULL")


class SoftDeleteMixin:
    """Borrado lógico: la fila nunca se elimina, solo se marca y se oculta.

    El filtro `deleted_at IS NULL` se aplica global y automáticamente a todas
    las consultas ORM (ver app/soft_delete.py), incluidas las relaciones lazy.
    """

    deleted_at = scheduler_db.Column(scheduler_db.DateTime, nullable=True, index=True)

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self, at=None):
        """Marca la fila y sus hijos como borrados. Idempotente.

        Toda la cascada comparte el mismo `deleted_at`: ese timestamp es lo que
        identifica el lote y permite restaurar exactamente lo que se ocultó
        junto, sin resucitar lo que ya estaba borrado de antes.
        """
        at = at or datetime.utcnow()
        if self.deleted_at is None:
            self.deleted_at = at
        for child in self.soft_delete_cascade():
            child.soft_delete(at)

    def restore(self):
        """Revierte el borrado lógico de esta fila (no de sus hijos)."""
        self.deleted_at = None

    def soft_delete_cascade(self):
        """Hijos que deben marcarse como borrados junto a esta fila."""
        return []
