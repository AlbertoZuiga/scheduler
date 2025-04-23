from app import app, scheduler_db
from config import Config

with app.app_context():
    scheduler_db.create_all()

if __name__ == '__main__':
    app.run(port=Config.APP_PORT, host=Config.APP_HOST)