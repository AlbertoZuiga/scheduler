from sqlalchemy import inspect, text

from app import scheduler_app
from app.extensions import scheduler_db

# Columnas agregadas a `group` para el rango horario configurable de disponibilidad.
# ADD COLUMN IF NOT EXISTS no existe en todas las versiones de MySQL, así que se
# consulta el schema antes de cada ALTER (migración idempotente).
GROUP_COLUMN_MIGRATIONS = [
    ("start_hour", "ALTER TABLE {table} ADD COLUMN start_hour INTEGER NOT NULL DEFAULT 8"),
    ("end_hour", "ALTER TABLE {table} ADD COLUMN end_hour INTEGER NOT NULL DEFAULT 19"),
    (
        "active_weekdays",
        "ALTER TABLE {table} ADD COLUMN active_weekdays VARCHAR(20) "
        "NOT NULL DEFAULT '0,1,2,3,4,5,6'",
    ),
]


def _run_group_column_migrations():
    preparer = scheduler_db.engine.dialect.identifier_preparer
    table = preparer.quote("group")
    existing = {col["name"] for col in inspect(scheduler_db.engine).get_columns("group")}
    for column, statement in GROUP_COLUMN_MIGRATIONS:
        if column in existing:
            continue
        print(f"  Agregando columna group.{column}...")
        scheduler_db.session.execute(text(statement.format(table=table)))
        scheduler_db.session.commit()


def migrate_database():
    with scheduler_app.app_context():
        print("Migrando base de datos...")
        scheduler_db.create_all()
        _run_group_column_migrations()
        print("Base de datos migrada con éxito.\n")


if __name__ == "__main__":
    migrate_database()
