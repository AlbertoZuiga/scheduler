"""DATA-003: borrado lógico, cascada y retención de division_jobs

Revision ID: 0004_division_jobs_soft_delete
Revises: 0003_fk_indexes
Create Date: 2026-08-10

`division_jobs` era la única tabla del dominio sin `deleted_at`: crecía sin cota
(una fila JSON gorda por cada click en "Generar") y sobrevivía al borrado de su
grupo, quedando exportable con los nombres y correos de todo el grupo.

La migración agrega la columna, su índice, y pone al día los datos:

1. los jobs de grupos ya borrados se ocultan con el `deleted_at` del grupo, que
   es lo que habría hecho la cascada si hubiera existido;
2. se aplica la retención hacia atrás: por grupo quedan los más recientes más el
   último confirmado (el que necesita `undo`).
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0004_division_jobs_soft_delete"
down_revision = "0003_fk_indexes"
branch_labels = None
depends_on = None

RETAINED_JOBS_PER_GROUP = 10


def _retire_old_jobs(connection, deleted_at):
    """Oculta los jobs que sobran por grupo, respetando el último confirmado."""
    rows = connection.execute(
        sa.text(
            "SELECT id, parent_group_id, status FROM division_jobs "
            "WHERE deleted_at IS NULL ORDER BY parent_group_id, timestamp DESC, id DESC"
        )
    ).fetchall()

    seen_per_group = {}
    confirmed_kept = set()
    to_retire = []
    for job_id, group_id, status in rows:
        position = seen_per_group.get(group_id, 0)
        seen_per_group[group_id] = position + 1
        if position < RETAINED_JOBS_PER_GROUP:
            if status == "confirmed":
                confirmed_kept.add(group_id)
            continue
        # Fuera de la ventana: solo se salva el confirmado más reciente del
        # grupo si la ventana no alcanzó a incluir ninguno.
        if status == "confirmed" and group_id not in confirmed_kept:
            confirmed_kept.add(group_id)
            continue
        to_retire.append(job_id)

    for job_id in to_retire:
        connection.execute(
            sa.text("UPDATE division_jobs SET deleted_at = :ts WHERE id = :id"),
            {"ts": deleted_at, "id": job_id},
        )


def upgrade():
    with op.batch_alter_table("division_jobs") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_index("ix_division_jobs_deleted_at", "division_jobs", ["deleted_at"])
    op.create_index(
        "ix_division_jobs_parent_deleted", "division_jobs", ["parent_group_id", "deleted_at"]
    )

    connection = op.get_bind()
    # Cascada retroactiva: los jobs heredan el deleted_at de su grupo borrado.
    connection.execute(
        sa.text(
            'UPDATE division_jobs SET deleted_at = ('
            '  SELECT g.deleted_at FROM "group" g WHERE g.id = division_jobs.parent_group_id'
            ') WHERE parent_group_id IN ('
            '  SELECT id FROM "group" WHERE deleted_at IS NOT NULL'
            ')'
        )
    )
    _retire_old_jobs(connection, datetime.now(timezone.utc).replace(tzinfo=None))


def downgrade():
    op.drop_index("ix_division_jobs_parent_deleted", table_name="division_jobs")
    op.drop_index("ix_division_jobs_deleted_at", table_name="division_jobs")
    with op.batch_alter_table("division_jobs") as batch:
        batch.drop_column("deleted_at")
