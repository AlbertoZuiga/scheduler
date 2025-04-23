import random
from app import app, scheduler_db

def seed_database():
    print("Creando datos...")

    print("Datos creados correctamente!")

if __name__ == "__main__":
    with app.app_context():
        seed_database()
