"""baseline: esquema pre-Alembic (no crea nada)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-10

Esta revisión es deliberadamente un no-op. Representa el esquema tal como quedó
tras la era de `create_all()` + el runner DDL manual de `app/db/migrate.py`, que
es lo que ya está desplegado en Render y en las bases locales.

Cómo se llega a esta revisión según el estado de la base (lo resuelve
`app.db.migrate.migrate_database()`):

- Base ya desplegada, con tablas y sin `alembic_version`: se corren las
  migraciones de columnas heredadas (por si a esa base le faltaba alguna) y se
  hace `stamp 0001_baseline`. NO se recrea ni se toca ninguna tabla.
- Base vacía: `create_all()` levanta el esquema completo desde los modelos
  actuales y se hace `stamp head` (ya está al día, no hay nada que migrar).

De 0002 en adelante las revisiones sí hacen DDL real.
"""
from alembic import op  # noqa: F401  pylint: disable=unused-import
import sqlalchemy as sa  # noqa: F401  pylint: disable=unused-import

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
