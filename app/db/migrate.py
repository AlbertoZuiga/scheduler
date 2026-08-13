"""Punto de entrada de las migraciones. Alembic gobierna el esquema.

Qué hace:
- Bases nuevas: `create_all()` + stamp en `head` (sin recorrer el historial).
- Bases existentes ya versionadas: `upgrade("head")` aplica las revisiones pendientes.
"""
import os

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext

from app import scheduler_app
from app.extensions import scheduler_db

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_ALEMBIC_INI = os.path.join(_PROJECT_ROOT, "alembic.ini")
_SCRIPT_LOCATION = os.path.join(_PROJECT_ROOT, "alembic")

# Los unique parciales de DATA-001 (`WHERE deleted_at IS NULL`) no existen en
# MySQL: el índice quedaría total y rechazaría reingresos a grupos/categorías
# borrados. Fallar acá es más seguro que dejar la base mal.
SUPPORTED_DIALECTS = ("postgresql", "sqlite")


def _alembic_config(connection):
    config = AlembicConfig(_ALEMBIC_INI)
    config.set_main_option("script_location", _SCRIPT_LOCATION)
    config.attributes["connection"] = connection
    return config


def migrate_database():
    with scheduler_app.app_context():
        dialect = scheduler_db.engine.dialect.name
        if dialect not in SUPPORTED_DIALECTS:
            raise RuntimeError(
                f"El esquema no se puede migrar sobre '{dialect}': las revisiones "
                f"usan índices unique parciales, que solo soportan "
                f"{' y '.join(SUPPORTED_DIALECTS)}."
            )
        print("Migrando base de datos...")
        with scheduler_db.engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()

        if current is None:
            print("  Base vacía: creando el esquema desde los modelos...")
            scheduler_db.create_all()
            with scheduler_db.engine.begin() as connection:
                command.stamp(_alembic_config(connection), "head")
        else:
            with scheduler_db.engine.begin() as connection:
                command.upgrade(_alembic_config(connection), "head")

        print("Base de datos migrada con éxito.\n")


if __name__ == "__main__":
    migrate_database()
