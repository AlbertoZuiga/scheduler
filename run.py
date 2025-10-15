from app import scheduler_app
from app.extensions import scheduler_db
import os


with scheduler_app.app_context():
    scheduler_db.create_all()


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = scheduler_app.config.get("DEBUG", False)
    scheduler_app.run(host=host, port=port, debug=debug)
