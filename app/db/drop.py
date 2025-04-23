import pymysql
from config import Config

def drop_database():
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    cursor = conn.cursor()
    print("Eliminando base de datos...")

    cursor.execute(
        f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = '{Config.DB_NAME}';"
    )
    result = cursor.fetchone()
    if result:
        cursor.execute(f"DROP DATABASE {Config.DB_NAME};")
        print(f"Base de datos '{Config.DB_NAME}' eliminada.\n")
    else:
        print(f"La base de datos '{Config.DB_NAME}' no existe.\n")

    conn.close()

if __name__ == "__main__":
    drop_database()