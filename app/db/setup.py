from app import scheduler_app
from app.db.create import create_database
from app.db.migrate import migrate_database
from app.db.seed import seed_database


def setup():
    with scheduler_app.app_context():
        create_database()
        migrate_database()
        seed_database()


if __name__ == "__main__":
    setup()
