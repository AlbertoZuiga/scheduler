"""Fixtures de pytest para la app Flask.

El factory `create_app()` se ejecuta en tiempo de import (`app/__init__.py`), y
`config.py` lee la configuración desde variables de entorno. Por eso hay que
setear el entorno ANTES de importar cualquier módulo de la app.
"""

import atexit
import os
import tempfile

import pytest

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".sqlite")
os.close(_DB_FD)
# El archivo se crea al importar conftest, así que se borra al salir del proceso:
# una corrida que no llegue a usar el fixture `app` igual lo tiene que limpiar.
atexit.register(lambda: os.path.exists(_DB_PATH) and os.unlink(_DB_PATH))

os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["DATABASE_URI"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "test"
os.environ["URL"] = "http://localhost"
os.environ["GOOGLE_CLIENT_ID"] = "test-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-client-secret"

# pylint: disable=wrong-import-position
from app import scheduler_app  # noqa: E402
from app.extensions import scheduler_db  # noqa: E402


@pytest.fixture(scope="session")
def app():
    scheduler_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with scheduler_app.app_context():
        scheduler_db.create_all()
    yield scheduler_app
    with scheduler_app.app_context():
        scheduler_db.drop_all()


@pytest.fixture()
def client(app):  # pylint: disable=redefined-outer-name
    return app.test_client()


@pytest.fixture()
def db_session(app):  # pylint: disable=redefined-outer-name
    """Sesión de BD limpia por test: todo lo escrito se revierte al terminar."""
    with app.app_context():
        yield scheduler_db.session
        scheduler_db.session.rollback()
        for table in reversed(scheduler_db.metadata.sorted_tables):
            scheduler_db.session.execute(table.delete())
        scheduler_db.session.commit()
        scheduler_db.session.remove()
