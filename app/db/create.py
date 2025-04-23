import pymysql
from config import Config

def create_database():
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    cursor = conn.cursor()
    print("Creando base de datos...")

    cursor.execute(
        f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{Config.DB_NAME}';"
    )
    result = cursor.fetchone()
    if result:
        print(f"Base de datos '{Config.DB_NAME}' ya existe.\n")
    else:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        print(f"Base de datos '{Config.DB_NAME}' creada.\n")

    conn.close()

if __name__ == "__main__":
    create_database()
