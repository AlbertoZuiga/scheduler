"""DATA-008: created_at/updated_at en el dominio y bitácora de acciones sensibles

Revision ID: 0007_timestamps_and_audit_log
Revises: 0006_perm_grant_subject_xor
Create Date: 2026-08-10

Ocho tablas del dominio no guardaban ninguna fecha: no había forma de saber
cuándo entró un miembro, cuándo se creó una categoría ni cuándo se marcó un
bloque. Y los cambios que mueven poder dentro de un grupo —cambiar un rol,
conceder o revocar permisos— no dejaban rastro de quién los hizo.

La revisión:

1. agrega `created_at` / `updated_at` a las ocho tablas. Las filas existentes
   quedan con la fecha de la migración: es un backfill, no una reconstrucción
   del pasado, y no hay dato del que sacar la fecha real;
2. crea `audit_log`, append-only (sin borrado lógico ni `updated_at`), con el
   actor, la acción, el sujeto y el detalle del cambio.

Las columnas se agregan con NOT NULL solo en Postgres. En SQLite `ALTER TABLE
ADD COLUMN` no acepta un default no constante, y hacerlo por `batch_alter_table`
implica recrear la tabla: la reflexión de SQLite no conserva el `WHERE
deleted_at IS NULL` de los unique parciales, así que la recreación los
convertiría en unique totales y rompería el reingreso. En SQLite las columnas
quedan nullable y con backfill; una base SQLite nueva sale de `create_all()` con
el esquema completo.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_timestamps_and_audit_log"
down_revision = "0006_perm_grant_subject_xor"
branch_labels = None
depends_on = None

TIMESTAMPED_TABLES = [
    "user",
    "group",
    "group_member",
    "group_member_category",
    "category",
    "group_permission_grant",
    "availability",
    "user_availability",
]

COLUMNS = ("created_at", "updated_at")


def upgrade():
    bind = op.get_bind()
    es_postgres = bind.dialect.name == "postgresql"

    for table in TIMESTAMPED_TABLES:
        for column in COLUMNS:
            if es_postgres:
                op.add_column(
                    table,
                    sa.Column(
                        column,
                        sa.DateTime(),
                        nullable=False,
                        server_default=sa.func.now(),
                    ),
                )
            else:
                op.add_column(table, sa.Column(column, sa.DateTime(), nullable=True))
                op.execute(
                    sa.text(
                        f'UPDATE "{table}" SET {column} = CURRENT_TIMESTAMP '
                        f"WHERE {column} IS NULL"
                    )
                )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id",
            sa.Integer(),
            sa.ForeignKey("group.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # El actor se va, la bitácora queda: por eso SET NULL y el correo
        # copiado, que es lo único que sigue diciendo quién fue.
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(length=150), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("subject_type", sa.String(length=20), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_audit_log_group_created", "audit_log", ["group_id", "created_at"]
    )


def downgrade():
    op.drop_index("ix_audit_log_group_created", table_name="audit_log")
    op.drop_table("audit_log")
    for table in TIMESTAMPED_TABLES:
        for column in COLUMNS:
            op.drop_column(table, column)
