"""Rate limit por IP en memoria del proceso (SEC-009).

Alcanza para lo que protege: gunicorn corre con `--workers 1` (`Dockerfile`,
`render.yaml`), así que hay un solo proceso por instancia y este diccionario es
el estado compartido de todos sus threads. Si algún día se sube el número de
workers o de instancias, cada uno lleva su propia cuenta y el límite efectivo
se multiplica por esa cantidad: ahí hay que mover el contador a un backend
compartido (Flask-Limiter con `storage_uri` a Redis).

No pretende frenar un ataque distribuido; pretende que adivinar un
`join_token` desde una IP deje de ser gratis.
"""

import threading
import time
from collections import deque
from functools import wraps

from flask import abort, current_app, g, request

# key -> deque de timestamps dentro de la ventana.
_HITS = {}
_LOCK = threading.Lock()

# Techo de claves vivas: sin esto, pegarle desde IPs distintas hace crecer el
# diccionario sin límite. Al tocarlo se barren las ventanas ya vencidas.
_MAX_KEYS = 10_000


def _client_ip():
    # ProxyFix (x_for=1) ya dejó en remote_addr la IP real detrás del proxy de Render.
    return request.remote_addr or "desconocida"


def _prune(now):
    # Cada clave lleva su propia ventana; usarla aquí evita que entradas de
    # endpoints con ventana corta sobrevivan si el GC lo dispara uno de ventana larga.
    for key, (hits, window) in list(_HITS.items()):
        while hits and hits[0] <= now - window:
            hits.popleft()
        if not hits:
            del _HITS[key]


def _register(key, limit, window):
    """True si la request entra dentro del límite; False si lo excede."""
    now = time.monotonic()
    with _LOCK:
        if len(_HITS) > _MAX_KEYS:
            _prune(now)
        entry = _HITS.setdefault(key, (deque(), window))
        hits = entry[0]
        while hits and hits[0] <= now - window:
            hits.popleft()
        if len(hits) >= limit:
            return False
        hits.append(now)
        return True


def reset():
    """Limpia el estado. Solo para los tests: cada uno arranca con la cuenta en cero."""
    with _LOCK:
        _HITS.clear()


def rate_limit(limit, window_seconds, scope=None):
    """Aborta con 429 si una IP supera `limit` requests en `window_seconds`.

    `scope` separa los contadores entre endpoints; por default usa el nombre de
    la vista, así que dos rutas decoradas no se comen la cuota entre sí.
    """

    def decorator(view):
        bucket = scope or view.__name__

        @wraps(view)
        def wrapper(*args, **kwargs):
            if current_app.config.get("RATELIMIT_ENABLED", True):
                key = f"{bucket}:{_client_ip()}"
                if not _register(key, limit, window_seconds):
                    current_app.logger.warning(
                        "rate limit excedido en %s por %s", bucket, _client_ip()
                    )
                    g.rate_limit_retry_after = window_seconds
                    abort(429)
            return view(*args, **kwargs)

        return wrapper

    return decorator
