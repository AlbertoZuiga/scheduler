from app import scheduler_app
from app.extensions import scheduler_db

def reset_database():
    with scheduler_app.app_context():
        scheduler_db.drop_all()
        scheduler_db.create_all()
        print("Base de datos reseteada con éxito.\n")


if __name__ == "__main__":
    reset_database()
