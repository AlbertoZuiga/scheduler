"""Índices compuestos (fk, deleted_at)

Revision ID: 0003_fk_indexes
Revises: 0002_unique_constraints
Create Date: 2026-08-10

Postgres —el motor de producción— no indexa las foreign keys por su cuenta
(MySQL, el fallback de desarrollo, sí: por eso el problema no se veía en local).
Y como el filtro de borrado lógico agrega `deleted_at IS NULL` a *cada* SELECT,
el índice útil no es el de la FK sola sino el compuesto que la termina.

`division_jobs` no está acá: la tabla todavía no tiene `deleted_at`. Su índice
va en 0004, junto con la columna.
"""
from alembic import op

revision = "0003_fk_indexes"
down_revision = "0002_unique_constraints"
branch_labels = None
depends_on = None

INDEXES = [
    ("ix_group_member_group_user_deleted", "group_member", ["group_id", "user_id", "deleted_at"]),
    ("ix_availability_group", "availability", ["group_id"]),
    (
        "ix_user_availability_user_avail_deleted",
        "user_availability",
        ["user_id", "availability_id", "deleted_at"],
    ),
    ("ix_category_group_deleted", "category", ["group_id", "deleted_at"]),
    (
        "ix_group_member_category_member_cat_deleted",
        "group_member_category",
        ["group_member_id", "category_id", "deleted_at"],
    ),
    ("ix_group_owner_deleted", "group", ["owner_id", "deleted_at"]),
    ("ix_subgroups_parent_deleted", "subgroups", ["parent_group_id", "deleted_at"]),
    (
        "ix_perm_grant_member_cat_deleted",
        "group_permission_grant",
        ["group_member_id", "category_id", "deleted_at"],
    ),
]


def upgrade():
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade():
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
