"""DATA-005: `availability.hour` (float de horas) pasa a `start_minutes` (entero)

Revision ID: 0008_availability_start_minutes
Revises: 0007_timestamps_and_audit_log
Create Date: 2026-08-10

El inicio del bloque se guardaba como float de horas, pero la grilla del grupo
se define en minutos (`group.start_minutes`, `block_minutes`) y todo el código
lo devolvía a minutos con `int(round(hour * 60))` para poder comparar por
igualdad: con bloques de 20 o 25 minutos el float no representa el inicio con
exactitud y la comparación fallaba. El dato es discreto; se guarda discreto.

La conversión es la misma que hacía el código: `round(hour * 60)`. Se hace en
SQL para no depender de la app, y respetando el unique
`(group_id, weekday, start_minutes)`: dos filas distintas en float pueden
redondear al mismo minuto, así que las duplicadas se funden —sus marcas de
`user_availability` se reapuntan a la fila que se conserva (la de menor id) y la
sobrante se borra— antes de crear el unique nuevo.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_availability_start_minutes"
down_revision = "0007_timestamps_and_audit_log"
branch_labels = None
depends_on = None


def _merge_duplicates(connection):
    """Funde las filas que caen en el mismo (group_id, weekday, minuto)."""
    filas = connection.execute(
        sa.text(
            "SELECT id, group_id, weekday, start_minutes FROM availability "
            "ORDER BY group_id, weekday, start_minutes, id"
        )
    ).fetchall()

    canonica = {}
    for fila_id, group_id, weekday, start_minutes in filas:
        clave = (group_id, weekday, start_minutes)
        if clave not in canonica:
            canonica[clave] = fila_id
            continue
        destino = canonica[clave]
        # La marca sobreviviente es la del bloque que se conserva; si el usuario
        # ya la tenía en ambas filas, la duplicada se descarta (el unique de
        # user_availability es sobre (user_id, availability_id)).
        connection.execute(
            sa.text(
                "DELETE FROM user_availability WHERE availability_id = :sobra "
                "AND user_id IN (SELECT user_id FROM user_availability "
                "WHERE availability_id = :destino)"
            ),
            {"sobra": fila_id, "destino": destino},
        )
        connection.execute(
            sa.text(
                "UPDATE user_availability SET availability_id = :destino "
                "WHERE availability_id = :sobra"
            ),
            {"destino": destino, "sobra": fila_id},
        )
        connection.execute(
            sa.text("DELETE FROM availability WHERE id = :sobra"), {"sobra": fila_id}
        )


def upgrade():
    connection = op.get_bind()

    op.add_column("availability", sa.Column("start_minutes", sa.Integer(), nullable=True))
    # CAST(x + 0.5 AS INTEGER) trunca hacia cero para positivos: round-half-up.
    # Python `round()` usa banker's rounding (round-half-even), que difiere en
    # valores exactamente a mitad (p.ej. 2.5 → 2 en Python, 3 en SQL). Con los
    # slots reales (múltiplos de minutos enteros) hour*60 no produce medios, así
    # que no hay divergencia en la práctica.
    connection.execute(
        sa.text(
            "UPDATE availability SET start_minutes = CAST(hour * 60 + 0.5 AS INTEGER)"
        )
    )
    _merge_duplicates(connection)

    with op.batch_alter_table("availability") as batch_op:
        batch_op.drop_constraint("uq_availability_slot", type_="unique")
        batch_op.alter_column("start_minutes", nullable=False)
        batch_op.drop_column("hour")
        batch_op.create_unique_constraint(
            "uq_availability_slot", ["group_id", "weekday", "start_minutes"]
        )


def downgrade():
    connection = op.get_bind()
    op.add_column("availability", sa.Column("hour", sa.Float(), nullable=True))
    connection.execute(sa.text("UPDATE availability SET hour = start_minutes / 60.0"))

    with op.batch_alter_table("availability") as batch_op:
        batch_op.drop_constraint("uq_availability_slot", type_="unique")
        batch_op.alter_column("hour", nullable=False)
        batch_op.drop_column("start_minutes")
        batch_op.create_unique_constraint(
            "uq_availability_slot", ["group_id", "weekday", "hour"]
        )
