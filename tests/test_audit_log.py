"""Fechas en el dominio y bitácora de las acciones sensibles."""

# pylint: disable=redefined-outer-name
import pytest

from app.models import Category, Group, GroupMember, GroupPermissionGrant, User
from app.models.audit_log import (
    ACTION_PERMISSION_GRANTED,
    ACTION_PERMISSION_REVOKED,
    ACTION_ROLE_CHANGED,
    AuditLog,
)
from app.models.group_member import RoleEnum


@pytest.fixture()
def grupo(db_session):
    duenio = User(email="duenio-audit@example.com", name="Dueño")
    otro = User(email="miembro-audit@example.com", name="Miembro")
    db_session.add_all([duenio, otro])
    db_session.flush()

    group = Group(name="Auditado", join_token="tok-audit", owner_id=duenio.id)
    db_session.add(group)
    db_session.flush()

    miembro = GroupMember(group_id=group.id, user_id=otro.id)
    categoria = Category(group_id=group.id, name="Cat")
    db_session.add_all(
        [GroupMember(group_id=group.id, user_id=duenio.id, role=RoleEnum.ADMIN), miembro, categoria]
    )
    db_session.commit()

    return {"group": group, "duenio": duenio, "miembro": miembro, "categoria": categoria}


@pytest.fixture()
def como_duenio(client, grupo):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(grupo["duenio"].id)
        sess["_fresh"] = True
    return client


def test_las_filas_nuevas_traen_fechas(grupo):
    for fila in (grupo["group"], grupo["miembro"], grupo["categoria"], grupo["duenio"]):
        assert fila.created_at is not None
        assert fila.updated_at is not None


def test_updated_at_avanza_al_modificar(db_session, grupo):
    miembro = grupo["miembro"]
    antes = miembro.updated_at

    miembro.role = RoleEnum.ADMIN
    db_session.commit()

    assert miembro.updated_at > antes


def test_cambiar_un_rol_queda_registrado(como_duenio, grupo):
    response = como_duenio.post(
        f"/groups/{grupo['group'].id}/update_role/{grupo['miembro'].user_id}",
        data={"role": "ADMIN"},
    )

    assert response.status_code == 302
    entrada = AuditLog.query.filter_by(action=ACTION_ROLE_CHANGED).one()
    assert entrada.actor_id == grupo["duenio"].id
    assert entrada.actor_email == grupo["duenio"].email
    assert entrada.subject_type == "member"
    assert entrada.subject_id == grupo["miembro"].id
    assert entrada.detail == {"from": "MEMBER", "to": "ADMIN"}


def test_conceder_y_revocar_permisos_queda_registrado(como_duenio, grupo):
    group_id = grupo["group"].id
    categoria_id = grupo["categoria"].id

    como_duenio.post(
        f"/groups/{group_id}/permissions/set",
        data={"subject": f"category:{categoria_id}", "level": "view_all"},
    )
    concesion = AuditLog.query.filter_by(action=ACTION_PERMISSION_GRANTED).one()
    assert concesion.subject_type == "category"
    assert concesion.subject_id == categoria_id
    assert concesion.detail["level"] == "view_all"

    otorgados = GroupPermissionGrant.query.filter_by(group_id=group_id).count()
    assert otorgados == len(concesion.detail["permissions"])

    como_duenio.post(
        f"/groups/{group_id}/permissions/revoke",
        data={"subject_type": "category", "subject_id": categoria_id},
    )
    revocacion = AuditLog.query.filter_by(action=ACTION_PERMISSION_REVOKED).one()
    assert revocacion.subject_id == categoria_id
    assert revocacion.detail["permissions"] == concesion.detail["permissions"]


def test_la_bitacora_sobrevive_al_borrado_del_actor(db_session, como_duenio, grupo):
    """El actor se va con SET NULL, pero el correo dice quién fue."""
    como_duenio.post(
        f"/groups/{grupo['group'].id}/update_role/{grupo['miembro'].user_id}",
        data={"role": "ADMIN"},
    )

    # El dueño no se puede borrar sin llevarse el grupo (y la bitácora con él),
    # así que se comprueba con el actor apuntando a otro usuario.
    entrada = AuditLog.query.one()
    tercero = User(email="tercero-audit@example.com", name="Tercero")
    db_session.add(tercero)
    db_session.flush()
    entrada.actor_id = tercero.id
    db_session.commit()

    db_session.query(User).filter(User.id == tercero.id).delete(synchronize_session=False)
    db_session.commit()
    db_session.expire_all()

    entrada = AuditLog.query.one()
    assert entrada.actor_id is None
    assert entrada.actor_email == grupo["duenio"].email
