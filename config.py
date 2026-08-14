import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:  # pylint: disable=too-few-public-methods
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URI",
        os.getenv("DATABASE_URL", f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"),
    )

    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        if DEBUG:
            SECRET_KEY = "dev-secret-key-no-usar-en-produccion"
        else:
            raise RuntimeError(
                "SECRET_KEY no está definida en el entorno. "
                "Es obligatoria fuera de modo debug: sin ella las sesiones firmadas "
                "no sobreviven a un restart ni son válidas entre workers."
            )

    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not DEBUG

    URL = os.getenv("URL")
