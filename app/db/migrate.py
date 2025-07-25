from app import scheduler_app
from app.extensions import scheduler_db


def migrate_database():
    with scheduler_app.app_context():
        print("Migrando base de datos...")
        scheduler_db.create_all()
        print("Base de datos migrada con éxito.\n")


if __name__ == "__main__":
    migrate_database()
