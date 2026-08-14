"""Construir la app es un acto explícito, no un efecto de import.

Se corre en un subproceso limpio porque el resto de la suite ya importó
`scheduler_app` vía conftest: en este intérprete la app está construida hace
rato y el chequeo no diría nada.
"""

import os
import subprocess
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SIN_EFECTO_DE_IMPORT = """
import app
assert app._scheduler_app is None, "importar el paquete construyó la app"
import app.models.user
import app.permissions
assert app._scheduler_app is None, "importar un submódulo construyó la app"
from app import scheduler_app
assert app._scheduler_app is not None, "pedir scheduler_app no construyó la app"
from app import get_app
assert get_app() is scheduler_app, "get_app() devolvió una app distinta"
"""


def test_importar_la_app_no_ejecuta_el_factory():
    # El entorno lo dejó listo conftest (DATABASE_URL a sqlite, SECRET_KEY);
    # el subproceso lo hereda.
    result = subprocess.run(
        [sys.executable, "-c", _SIN_EFECTO_DE_IMPORT],
        capture_output=True,
        text=True,
        check=False,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
