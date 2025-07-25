from app import app, scheduler_db


def reset_database():
    with app.app_context():
        scheduler_db.drop_all()
        scheduler_db.create_all()
        print("Base de datos reseteada con éxito.\n")


if __name__ == "__main__":
    reset_database()
