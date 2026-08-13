"""DATA-001: deduplicar y aplicar los unique faltantes

Revision ID: 0002_unique_constraints
Revises: 0001_baseline
Create Date: 2026-08-10

Dos fases dentro de la misma transacción, en este orden obligatorio:

1. **Dedup.** Aplicar un unique sobre datos con duplicados falla la migración,
   así que primero se limpian. En las tablas con borrado lógico se conserva la
   fila de menor `id` por clave y el resto se soft-deletea (no se borra: la
   papelera y el historial siguen siendo alcanzables). `availability` no tiene
   borrado lógico y además la referencian filas de `user_availability`, así que
   sus duplicados se *fusionan*: se repuntan las referencias a la fila que se
   conserva y recién ahí se borra la duplicada. Por eso `availability` va antes
   que `user_availability`: la fusión puede generar duplicados nuevos ahí.

2. **Constraints.** Unique parcial `WHERE deleted_at IS NULL` en las cinco
   tablas con borrado lógico (un unique total chocaría con las filas ocultas que
   comparten clave con la activa) y unique total en `availability`.
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "0002_unique_constraints"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

ACTIVE = sa.text("deleted_at IS NULL")

# (índice, tabla, columnas de la clave)
PARTIAL_UNIQUES = [
    ("uq_group_member_active", "group_member", ["group_id", "user_id"]),
    ("uq_user_availability_active", "user_availability", ["user_id", "availability_id"]),
    (
        "uq_group_member_category_active",
        "group_member_category",
        ["group_member_id", "category_id"],
    ),
    ("uq_subgroup_member_active", "subgroup_members", ["subgroup_id", "user_id"]),
]


def _merge_duplicate_availability(connection):
    """Fusiona filas de `availability` que representan el mismo bloque."""
    rows = connection.execute(
        sa.text("SELECT id, group_id, weekday, hour FROM availability ORDER BY id")
    ).fetchall()

    keepers = {}
    merged = 0
    for row_id, group_id, weekday, hour in rows:
        # La clave real del bloque son sus minutos: el FLOAT no conserva 8.25 ni
        # 8.3333 con precisión para comparar por igualdad (mismo criterio que
        # `_hour_to_minutes` en group_routes).
        key = (group_id, weekday, int(round(float(hour) * 60)))
        keeper = keepers.get(key)
        if keeper is None:
            keepers[key] = row_id
            continue
        connection.execute(
            sa.text(
                "UPDATE user_availability SET availability_id = :keeper "
                "WHERE availability_id = :dup"
            ),
            {"keeper": keeper, "dup": row_id},
        )
        connection.execute(
            sa.text("DELETE FROM availability WHERE id = :dup"), {"dup": row_id}
        )
        merged += 1
    return merged


def _soft_delete_duplicates(connection, table, key_columns, deleted_at):
    """Oculta todas las filas activas duplicadas menos la más antigua por clave."""
    keys = ", ".join(key_columns)
    result = connection.execute(
        sa.text(
            f"UPDATE {table} SET deleted_at = :deleted_at "
            f"WHERE deleted_at IS NULL AND id NOT IN ("
            f"  SELECT MIN(id) FROM {table} WHERE deleted_at IS NULL GROUP BY {keys}"
            f")"
        ),
        {"deleted_at": deleted_at},
    )
    return result.rowcount


def upgrade():
    connection = op.get_bind()
    # Un timestamp propio y compartido por todo el dedup: es lo que identifica
    # el lote, igual que hace `SoftDeleteMixin.soft_delete`.
    deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)

    _merge_duplicate_availability(connection)
    for _, table, key_columns in PARTIAL_UNIQUES:
        _soft_delete_duplicates(connection, table, key_columns, deleted_at)
    # `category` se deduplica por nombre normalizado, no por la columna cruda.
    _soft_delete_duplicates(connection, "category", ["group_id", "lower(name)"], deleted_at)

    for index_name, table, key_columns in PARTIAL_UNIQUES:
        op.create_index(
            index_name,
            table,
            key_columns,
            unique=True,
            postgresql_where=ACTIVE,
            sqlite_where=ACTIVE,
        )
    op.create_index(
        "uq_category_active_name",
        "category",
        ["group_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=ACTIVE,
        sqlite_where=ACTIVE,
    )
    with op.batch_alter_table("availability") as batch:
        batch.create_unique_constraint(
            "uq_availability_slot", ["group_id", "weekday", "hour"]
        )


def downgrade():
    # El dedup no se revierte: las filas ocultadas quedan en la papelera y
    # restaurarlas a ciegas reintroduciría los duplicados que causaron el
    # problema. Solo se sueltan los constraints.
    with op.batch_alter_table("availability") as batch:
        batch.drop_constraint("uq_availability_slot", type_="unique")
    op.drop_index("uq_category_active_name", table_name="category")
    for index_name, table, _ in reversed(PARTIAL_UNIQUES):
        op.drop_index(index_name, table_name=table)
