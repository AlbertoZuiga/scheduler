from app import scheduler_app
from app.extensions import scheduler_db


with scheduler_app.app_context():
    scheduler_db.create_all()

if __name__ == "__main__":
    scheduler_app.run()
