# `scheduler_app` lo fabrica el __getattr__ (PEP 562) de app/__init__.py, que
# pylint no puede inferir estaticamente.
from app import scheduler_app  # pylint: disable=no-name-in-module
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
