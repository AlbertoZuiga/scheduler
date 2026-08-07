from sqlalchemy import DateTime, inspect, text

from app import scheduler_app
from app.extensions import scheduler_db
from app.models.mixins import SoftDeleteMixin

# Migraciones aditivas por tabla: (columna, DDL) o (columna, DDL, backfill). El
# backfill corre una sola vez, justo después de crear la columna, para poblarla
# a partir de datos preexistentes. Se consulta el schema antes de cada ALTER,
# así que un fallo real (permisos, lock) rompe el build en vez de quedar
# silenciado. ADD COLUMN IF NOT EXISTS no existe en todas las versiones de
# MySQL, por eso no se usa.
#
# Los grupos anteriores guardaban el rango como horas enteras y la grilla
# arrancaba siempre a y media (bloques "08:30 - 09:20"), así que el backfill
# reproduce esa misma grilla en minutos: start_hour*60+30 con bloques de 60.
COLUMN_MIGRATIONS = {
    # Rango horario y días visibles en la grilla de disponibilidad del grupo.
    "group": [
        (
            "start_minutes",
            "ALTER TABLE {table} ADD COLUMN start_minutes INTEGER NOT NULL DEFAULT 510",
            ("start_hour", "UPDATE {table} SET start_minutes = start_hour * 60 + 30"),
        ),
        (
            "end_minutes",
            "ALTER TABLE {table} ADD COLUMN end_minutes INTEGER NOT NULL DEFAULT 1170",
            ("end_hour", "UPDATE {table} SET end_minutes = end_hour * 60 + 30"),
        ),
        (
            "block_minutes",
            "ALTER TABLE {table} ADD COLUMN block_minutes INTEGER NOT NULL DEFAULT 60",
        ),
        (
            "active_weekdays",
            "ALTER TABLE {table} ADD COLUMN active_weekdays VARCHAR(20) "
            "NOT NULL DEFAULT '0,1,2,3,4,5,6'",
        ),
    ],
}

# Columnas obsoletas que deben eliminarse. Solo se dropean si existen, y solo
# después de que las migraciones aditivas ya corrieron (el backfill ya movió
# los datos a las columnas nuevas).
DROP_COLUMN_MIGRATIONS = {
    "group": ["start_hour", "end_hour"],
}


def _soft_delete_tables():
    """Tablas de modelos con borrado lógico, según el mapeo real del ORM."""
    return sorted(
        mapper.class_.__tablename__
        for mapper in scheduler_db.Model.registry.mappers
        if issubclass(mapper.class_, SoftDeleteMixin)
    )


def _pending_migrations():
    """Construye el plan completo: columnas explícitas + deleted_at por tabla."""
    plan = {table: list(columns) for table, columns in COLUMN_MIGRATIONS.items()}
    # El tipo lo compila el dialecto: DATETIME en MySQL/SQLite, TIMESTAMP en Postgres.
    datetime_sql = scheduler_db.engine.dialect.type_compiler.process(DateTime())
    for table in _soft_delete_tables():
        plan.setdefault(table, []).append(
            (
                "deleted_at",
                f"ALTER TABLE {{table}} ADD COLUMN deleted_at {datetime_sql} NULL",
            )
        )
    return plan


def _run_column_migrations():
    inspector = inspect(scheduler_db.engine)
    preparer = scheduler_db.engine.dialect.identifier_preparer
    existing_tables = set(inspector.get_table_names())

    for table, migrations in _pending_migrations().items():
        if table not in existing_tables:
            # create_all() ya la creó con el schema actual.
            continue

        quoted = preparer.quote(table)
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        for column, statement, *rest in migrations:
            if column not in existing_columns:
                print(f"  Agregando columna {table}.{column}...")
                scheduler_db.session.execute(text(statement.format(table=quoted)))
                scheduler_db.session.commit()

            backfill = rest[0] if rest else None
            # El backfill lee una columna vieja: en una base nueva no existe y
            # el DEFAULT de la columna recién creada ya es el valor correcto.
            #
            # Corre siempre que la columna origen siga viva, no solo en la
            # corrida que creó la destino: el ADD COLUMN y el UPDATE se
            # commitean por separado, así que un proceso que muere entre ambos
            # dejaría la columna nueva vacía, y la re-corrida la daría por
            # migrada justo antes de que _run_drop_migrations borre el origen.
            # Repetirlo es inocuo: el UPDATE es idempotente.
            if backfill and backfill[0] in existing_columns:
                print(f"  Poblando {table}.{column} desde {table}.{backfill[0]}...")
                scheduler_db.session.execute(text(backfill[1].format(table=quoted)))
                scheduler_db.session.commit()

        _ensure_deleted_at_index(inspector, table, quoted)


def _ensure_deleted_at_index(inspector, table, quoted_table):
    """El índice de deleted_at solo lo crea create_all() en tablas nuevas."""
    if table not in _soft_delete_tables():
        return

    index_name = f"ix_{table}_deleted_at"
    if any(idx["name"] == index_name for idx in inspector.get_indexes(table)):
        return

    print(f"  Creando índice {index_name}...")
    scheduler_db.session.execute(
        text(f"CREATE INDEX {index_name} ON {quoted_table} (deleted_at)")
    )
    scheduler_db.session.commit()


def _run_drop_migrations():
    inspector = inspect(scheduler_db.engine)
    preparer = scheduler_db.engine.dialect.identifier_preparer
    existing_tables = set(inspector.get_table_names())

    for table, columns in DROP_COLUMN_MIGRATIONS.items():
        if table not in existing_tables:
            continue
        quoted = preparer.quote(table)
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        for column in columns:
            if column not in existing_columns:
                continue
            print(f"  Dropeando columna obsoleta {table}.{column}...")
            scheduler_db.session.execute(
                text(f"ALTER TABLE {quoted} DROP COLUMN {preparer.quote(column)}")
            )
            scheduler_db.session.commit()


def migrate_database():
    with scheduler_app.app_context():
        print("Migrando base de datos...")
        scheduler_db.create_all()
        _run_column_migrations()
        _run_drop_migrations()
        print("Base de datos migrada con éxito.\n")


if __name__ == "__main__":
    migrate_database()
