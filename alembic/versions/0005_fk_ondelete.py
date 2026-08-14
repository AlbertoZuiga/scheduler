"""Ondelete explícito en las foreign keys que no lo tenían

Revision ID: 0005_fk_ondelete
Revises: 0004_division_jobs_soft_delete
Create Date: 2026-08-10

Doce de las FKs del dominio se declararon sin `ondelete`, así que la BD usaba el
default (`NO ACTION`) y el borrado real de una fila padre fallaba o dejaba
huérfanos. El seed convivía con eso a mano: borraba `Availability`,
`UserAvailability`, `SubGroupMember`, `DivisionJob` y los grupos del dueño en el
orden justo antes de poder borrar un usuario. Con la cascada declarada, ese
andamiaje sobra.

Todas quedan en CASCADE: son filas que no significan nada sin su padre
(membresías, asignaciones, marcas de disponibilidad, concesiones de permiso). El
caso menos obvio es `group.owner_id`, que es NOT NULL: no hay un "grupo sin
dueño" representable, así que el grupo se va con él. Las FKs que ya traían
`ondelete` (subgrupos, `division_jobs`) no se tocan.

El cambio se aplica solo sobre Postgres —el motor de producción—. En SQLite
cambiar una FK obliga a recrear la tabla entera, y esas tablas llevan índices
unique parciales que la reflexión no reproduce con fidelidad; como una base
SQLite nueva sale de `create_all()` (que ya lee el `ondelete` de los modelos),
el único hueco sería una base SQLite de desarrollo preexistente.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_fk_ondelete"
down_revision = "0004_division_jobs_soft_delete"
branch_labels = None
depends_on = None

# (tabla, columna, tabla referida, columna referida)
FOREIGN_KEYS = [
    ("availability", "group_id", "group", "id"),
    ("user_availability", "user_id", "user", "id"),
    ("user_availability", "availability_id", "availability", "id"),
    ("category", "group_id", "group", "id"),
    ("group_member", "group_id", "group", "id"),
    ("group_member", "user_id", "user", "id"),
    ("group_member_category", "group_member_id", "group_member", "id"),
    ("group_member_category", "category_id", "category", "id"),
    ("group", "owner_id", "user", "id"),
    ("group_permission_grant", "group_id", "group", "id"),
    ("group_permission_grant", "group_member_id", "group_member", "id"),
    ("group_permission_grant", "category_id", "category", "id"),
]


def _constraint_name(inspector, table, column):
    """Nombre de la FK que restringe `column`, o None si no está declarada."""
    for fk in inspector.get_foreign_keys(table):
        if fk["constrained_columns"] == [column] and fk["name"]:
            return fk["name"]
    return None


def _new_name(table, column, referred_table):
    return f"fk_{table}_{column}_{referred_table}"


def _recreate(ondelete):
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    for table, column, referred_table, referred_column in FOREIGN_KEYS:
        existing = _constraint_name(inspector, table, column)
        if existing:
            op.drop_constraint(existing, table, type_="foreignkey")
        op.create_foreign_key(
            _new_name(table, column, referred_table),
            table,
            referred_table,
            [column],
            [referred_column],
            ondelete=ondelete,
        )


def upgrade():
    _recreate("CASCADE")


def downgrade():
    # Vuelve al default (NO ACTION), que es lo que había antes de esta revisión.
    _recreate(None)
