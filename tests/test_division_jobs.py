"""Cascada y retención de DivisionJob."""

# pylint: disable=redefined-outer-name
from datetime import UTC, datetime, timedelta

import pytest
from werkzeug.exceptions import NotFound

from app.models import Group, User
from app.models.subgroup import DivisionJob
from app.routes.subgroup_routes import _get_active_job_or_404
from app.services.subgroup_service import (
    RETAINED_JOBS_PER_GROUP,
)
from app.services.subgroup_service import (
    prune_division_jobs as _prune_division_jobs,
)


@pytest.fixture()
def group_with_jobs(db_session):
    """Un grupo con más jobs de los que la retención conserva."""
    user = User(email=f"j{datetime.now(UTC).timestamp()}@x.test", name="J")
    db_session.add(user)
    db_session.flush()

    group = Group(name="G", join_token=f"j{user.id}", owner_id=user.id)
    db_session.add(group)
    db_session.flush()

    base = datetime(2026, 1, 1)
    jobs = [
        DivisionJob(
            parent_group_id=group.id,
            created_by=user.id,
            config_json={},
            result_json={"groups": []},
            status="confirmed" if index == 0 else "pending",
            timestamp=base + timedelta(days=index),
        )
        for index in range(RETAINED_JOBS_PER_GROUP + 5)
    ]
    db_session.add_all(jobs)
    db_session.flush()
    return group, jobs


def test_borrar_el_grupo_hace_inaccesibles_sus_jobs(db_session, group_with_jobs):
    group, jobs = group_with_jobs
    job_id = jobs[-1].id
    assert _get_active_job_or_404(group.id, job_id) is not None

    group.soft_delete()
    db_session.flush()

    # El filtro global de borrado lógico ya no los devuelve: `export` responde
    # 404 en vez de servir el CSV con los correos del grupo borrado.
    assert DivisionJob.query.filter_by(parent_group_id=group.id).count() == 0
    with pytest.raises(NotFound):
        _get_active_job_or_404(group.id, job_id)


def test_la_retencion_acota_los_jobs_por_grupo(db_session, group_with_jobs):
    group, jobs = group_with_jobs

    _prune_division_jobs(group.id)
    db_session.flush()

    activos = DivisionJob.query.filter_by(parent_group_id=group.id).all()
    ids_activos = {job.id for job in activos}

    # Los más recientes, más el confirmado más viejo que `undo` necesita.
    esperado = {job.id for job in jobs[-RETAINED_JOBS_PER_GROUP:]} | {jobs[0].id}
    assert ids_activos == esperado
