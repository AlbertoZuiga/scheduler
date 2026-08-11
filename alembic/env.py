"""Entorno de Alembic conectado a la app.

La metadata objetivo es la del ORM real (`scheduler_db.metadata`, poblada al
importar `app.models`) y la conexión sale de la config de la app, no de
`alembic.ini`. Con eso, `alembic revision --autogenerate` compara contra los
mismos modelos que usa Flask y `alembic upgrade` apunta a la misma base.
"""
from logging.config import fileConfig

from alembic import context

from app import scheduler_app
from app.extensions import scheduler_db
import app.models  # noqa: F401  pylint: disable=unused-import  (registra los modelos en la metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = scheduler_db.metadata


def _configure_and_run(connection):
    if connection.dialect.name == "sqlite":
        # Batch mode recrea la tabla (DROP + CREATE + copia). Desde DATA-006 la
        # app enciende `PRAGMA foreign_keys` en cada conexión, así que ese DROP
        # lo rechazan las FKs que apuntan a la tabla. Se apagan durante la
        # migración y se vuelven a encender al terminar para no contaminar el pool.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        # El PRAGMA abre la transacción implícita de SQLAlchemy; sin cerrarla
        # acá, la que abre Alembic después no es la misma y las migraciones se
        # pierden al soltar la conexión.
        connection.commit()

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        # SQLite no sabe hacer ALTER de constraints: batch mode recrea la tabla.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def run_migrations_offline():
    """Genera el SQL sin conectarse (alembic upgrade --sql)."""
    context.configure(
        url=scheduler_app.config["SQLALCHEMY_DATABASE_URI"],
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Cuando Alembic se invoca desde la app (app/db/migrate.py) la conexión ya
    # viene abierta sobre el engine de Flask-SQLAlchemy; desde la CLI hay que
    # abrirla dentro del contexto de aplicación.
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure_and_run(connection)
        return

    with scheduler_app.app_context():
        with scheduler_db.engine.connect() as conn:
            _configure_and_run(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
