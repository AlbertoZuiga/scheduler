"""Filtro global de borrado lógico.

Todas las consultas ORM excluyen automáticamente las filas con `deleted_at`
seteado. Para incluirlas (papelera, restauración) se usa:

    Group.query.execution_options(include_deleted=True)
"""

import contextvars
from contextlib import contextmanager

from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria

from app.extensions import scheduler_db
from app.models.mixins import SoftDeleteMixin

INCLUDE_DELETED = "include_deleted"

# Desactiva el filtro para todo lo que se cargue dentro del bloque, incluidas
# las relaciones lazy (que no heredan las execution_options de la consulta que
# las originó). Es un contextvar y no un flag global para no filtrarse entre
# hilos cuando el servidor atiende varias peticiones a la vez.
_include_deleted_scope = contextvars.ContextVar("include_deleted_scope", default=False)


@contextmanager
def including_deleted():
    """Dentro del bloque, las consultas ORM también ven las filas borradas."""
    token = _include_deleted_scope.set(True)
    try:
        yield
    finally:
        _include_deleted_scope.reset(token)


def _filter_soft_deleted(execute_state):
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get(INCLUDE_DELETED, False):
        return
    if _include_deleted_scope.get():
        return
    # Refrescar columnas expiradas de una fila ya cargada no debe filtrarse:
    # rompería el acceso a una instancia que el código ya tiene en la mano.
    if execute_state.is_column_load:
        return

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


def install_soft_delete_filter():
    """Registra el filtro. Idempotente: seguro de llamar más de una vez."""
    if not event.contains(scheduler_db.session, "do_orm_execute", _filter_soft_deleted):
        event.listen(scheduler_db.session, "do_orm_execute", _filter_soft_deleted)


def active_or_404(instance):
    """404 para instancias obtenidas por identidad (`query.get`), que esquivan el filtro."""
    from flask import abort  # import local: evita ciclo al cargar los modelos

    if instance is None or getattr(instance, "is_deleted", False):
        abort(404)
    return instance


def restore_batch(root):
    """Restaura `root` y todo lo que se ocultó en la misma operación.

    Se recorre la misma cascada que usó `soft_delete`, así que la restauración
    es su inverso exacto. Dentro de esa cascada solo se revive lo que comparte
    el `deleted_at` del root: lo que ya estaba borrado de antes (un miembro
    expulsado, una categoría eliminada) permanece oculto.

    El lote NO se busca por `deleted_at` en toda la base: el DATETIME de MySQL
    trunca a segundos, así que dos borrados simultáneos de usuarios distintos
    comparten timestamp y restaurar uno resucitaría lo del otro.
    """
    deleted_at = root.deleted_at
    if deleted_at is None:
        return

    # Las relaciones de la cascada apuntan a filas ocultas: sin este bloque el
    # filtro global las esconde y la restauración dejaría a los hijos borrados.
    with including_deleted():
        _restore_tree(root, deleted_at)


def _restore_tree(node, deleted_at):
    if node.deleted_at != deleted_at:
        return
    node.restore()
    for child in node.soft_delete_cascade():
        _restore_tree(child, deleted_at)


def find_soft_deleted(model, **filters):
    """Busca una fila borrada lógicamente que coincida con los filtros dados."""
    return (
        model.query.execution_options(**{INCLUDE_DELETED: True})
        .filter_by(**filters)
        .filter(model.deleted_at.isnot(None))
        .order_by(model.deleted_at.desc())
        .first()
    )
