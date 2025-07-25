from app import scheduler_app


def seed_database():
    print("Creando datos...")

    print("Datos creados correctamente!")


if __name__ == "__main__":
    with scheduler_app.app_context():
        seed_database()
