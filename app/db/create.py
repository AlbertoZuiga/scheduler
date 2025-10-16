import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from config import Config


def create_database():
    # Detectar si estamos usando PostgreSQL o MySQL
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    
    if 'postgresql' in db_uri:
        # Usar PostgreSQL
        try:
            # Conectar a la base de datos 'postgres' por defecto
            conn = psycopg2.connect(
                host=Config.DB_HOST if Config.DB_HOST else 'localhost',
                user=Config.DB_USER if Config.DB_USER else 'postgres',
                password=Config.DB_PASSWORD if Config.DB_PASSWORD else '',
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            print("Verificando base de datos PostgreSQL...")

            # Verificar si la base de datos existe
            db_name = Config.DB_NAME if Config.DB_NAME else 'scheduler'
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s;",
                (db_name,)
            )
            result = cursor.fetchone()
            
            if result:
                print(f"Base de datos '{db_name}' ya existe.\n")
            else:
                cursor.execute(f'CREATE DATABASE "{db_name}";')
                print(f"Base de datos '{db_name}' creada.\n")

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Nota: {e}")
            print("Asumiendo que la base de datos ya existe o se creará automáticamente.\n")
    else:
        # Usar MySQL
        import pymysql
        conn = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cursor = conn.cursor()
        print("Creando base de datos MySQL...")

        cursor.execute(
            f"""SELECT SCHEMA_NAME
            FROM INFORMATION_SCHEMA.SCHEMATA
            WHERE SCHEMA_NAME = '{Config.DB_NAME}';"""
        )
        result = cursor.fetchone()
        if result:
            print(f"Base de datos '{Config.DB_NAME}' ya existe.\n")
        else:
            cursor.execute(
                f"""CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}
                CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"""
            )
            print(f"Base de datos '{Config.DB_NAME}' creada.\n")

        conn.close()
    
    print("Base de datos lista.\n")


if __name__ == "__main__":
    create_database()
