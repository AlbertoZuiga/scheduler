from app import app
from app.extensions import scheduler_db


with app.app_context():
    scheduler_db.create_all()

if __name__ == "__main__":
    app.run()
