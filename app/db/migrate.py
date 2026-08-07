from sqlalchemy import DateTime, inspect, text

from app import scheduler_app
from app.extensions import scheduler_db
from app.models.mixins import SoftDeleteMixin

# Migraciones aditivas por tabla: (columna, DDL). Se consulta el schema antes de
# cada ALTER, así que un fallo real (permisos, lock) rompe el build en vez de
# quedar silenciado. ADD COLUMN IF NOT EXISTS no existe en todas las versiones
# de MySQL, por eso no se usa.
COLUMN_MIGRATIONS = {
    # Rango horario y días visibles en la grilla de disponibilidad del grupo.
    "group": [
        ("start_hour", "ALTER TABLE {table} ADD COLUMN start_hour INTEGER NOT NULL DEFAULT 8"),
        ("end_hour", "ALTER TABLE {table} ADD COLUMN end_hour INTEGER NOT NULL DEFAULT 19"),
        (
            "active_weekdays",
            "ALTER TABLE {table} ADD COLUMN active_weekdays VARCHAR(20) "
            "NOT NULL DEFAULT '0,1,2,3,4,5,6'",
        ),
    ],
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
        for column, statement in migrations:
            if column in existing_columns:
                continue
            print(f"  Agregando columna {table}.{column}...")
            scheduler_db.session.execute(text(statement.format(table=quoted)))
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


def migrate_database():
    with scheduler_app.app_context():
        print("Migrando base de datos...")
        scheduler_db.create_all()
        _run_column_migrations()
        print("Base de datos migrada con éxito.\n")


if __name__ == "__main__":
    migrate_database()
