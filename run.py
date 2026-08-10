import os

from app import scheduler_app

# El esquema NO se crea acá. Antes este módulo hacía `create_all()` al importar,
# así que cada worker de gunicorn emitía DDL al arrancar. Ahora las migraciones
# son responsabilidad de Alembic vía `python -m app.db.migrate`, que corre una
# sola vez en el build (`render-build.sh`) o al levantar el contenedor.

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = scheduler_app.config.get("DEBUG", False)
    scheduler_app.run(host=host, port=port, debug=debug)
