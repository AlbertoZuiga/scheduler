from sqlalchemy import text

from app import scheduler_app
from app.extensions import scheduler_db
from app.db.migrate import migrate_database

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
