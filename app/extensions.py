import sqlite3

from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

scheduler_db = SQLAlchemy()
login_manager = LoginManager()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    """SQLite ignora las foreign keys salvo que se pidan por conexión.

    Sin esto el `ondelete` explícito de las FKs sería letra muerta en dev y en
    los tests, y solo Postgres —el motor de producción— aplicaría las cascadas.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
