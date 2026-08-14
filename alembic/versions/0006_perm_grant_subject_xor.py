"""CHECK que obliga a una concesión de permiso a tener un solo sujeto

Revision ID: 0006_perm_grant_subject_xor
Revises: 0005_fk_ondelete
Create Date: 2026-08-10

`group_permission_grant` admite sujeto por miembro o por categoría, y ambas
columnas son nullable. Nada a nivel de esquema impedía dejar las dos en NULL: la
fila se guardaba con `subject_key = "cNone"`, no concedía el permiso a nadie y
además ocupaba la clave única `(group_id, permission, subject_key)`, con lo que
la concesión real por categoría chocaba contra un fantasma. La única defensa
estaba en la ruta que concede.

El CHECK no puede ser parcial, así que las filas inválidas se limpian en esta
misma revisión, antes de crearlo:

1. las que tienen los dos sujetos en NULL se borran físicamente — no representan
   ninguna concesión, ni siquiera revocada;
2. las que tienen los dos seteados (no las produce ninguna ruta, pero el CHECK
   también las rechaza) se normalizan dejando el sujeto que indica
   `subject_key`, que es el que manda para la unicidad.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_perm_grant_subject_xor"
down_revision = "0005_fk_ondelete"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "ck_perm_grant_subject_xor"
CONDITION = (
    "(CASE WHEN group_member_id IS NULL THEN 0 ELSE 1 END"
    " + CASE WHEN category_id IS NULL THEN 0 ELSE 1 END) = 1"
)


def _clean_rows(connection):
    connection.execute(
        sa.text(
            "DELETE FROM group_permission_grant "
            "WHERE group_member_id IS NULL AND category_id IS NULL"
        )
    )
    # Con los dos sujetos puestos, `subject_key` desempata: es el discriminador
    # con el que ya se venía comparando la unicidad.
    connection.execute(
        sa.text(
            "UPDATE group_permission_grant SET category_id = NULL "
            "WHERE group_member_id IS NOT NULL AND category_id IS NOT NULL "
            "AND subject_key LIKE 'm%'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE group_permission_grant SET group_member_id = NULL "
            "WHERE group_member_id IS NOT NULL AND category_id IS NOT NULL "
            "AND subject_key NOT LIKE 'm%'"
        )
    )


def upgrade():
    _clean_rows(op.get_bind())
    # `batch_alter_table`: SQLite no sabe agregar un CHECK con ALTER TABLE y
    # necesita recrear la tabla. En Postgres el batch pasa de largo.
    with op.batch_alter_table("group_permission_grant") as batch_op:
        batch_op.create_check_constraint(CONSTRAINT_NAME, CONDITION)


def downgrade():
    with op.batch_alter_table("group_permission_grant") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
