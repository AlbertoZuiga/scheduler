from sqlalchemy import text

# `scheduler_app` lo fabrica el __getattr__ (PEP 562) de app/__init__.py, que
# pylint no puede inferir estaticamente.
from app import scheduler_app  # pylint: disable=no-name-in-module
from app.db.migrate import migrate_database
from app.extensions import scheduler_db


def reset_database():
    with scheduler_app.app_context():
        scheduler_db.drop_all()
        # También la tabla de versiones: si sobrevive, la base queda estampada
        # en head sin tener las tablas y `migrate` no volvería a crearlas.
        scheduler_db.session.execute(text("DROP TABLE IF EXISTS alembic_version"))
        scheduler_db.session.commit()
    migrate_database()
    print("Base de datos reseteada con éxito.\n")


if __name__ == "__main__":
    reset_database()
