"""DATA-001: los unique parciales rechazan duplicados activos.

Cada caso verifica las dos mitades de la garantía:

1. dos filas activas con la misma clave son rechazadas por la BD;
2. tras el borrado lógico de la primera, la misma clave se puede volver a
   insertar — que es justo lo que un unique total rompería (reingresar a un
   grupo, recrear una categoría, volver a marcar un bloque).
"""
# pylint: disable=redefined-outer-name
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Availability,
    Category,
    Group,
    GroupMember,
    GroupMemberCategory,
    User,
    UserAvailability,
)
from app.models.subgroup import SubGroup, SubGroupMember


def _flush_expecting_conflict(session, row):
    """El conflicto se revierte con un SAVEPOINT, no con la transacción entera.

    Un `rollback()` completo se llevaría también las filas del fixture, y la
    segunda mitad de cada test —reinsertar la clave tras el borrado lógico—
    pasaría por vacuidad, sobre una tabla vacía.
    """
    savepoint = session.begin_nested()
    session.add(row)
    with pytest.raises(IntegrityError):
        session.flush()
    savepoint.rollback()


@pytest.fixture()
def fixture_group(db_session):
    """Un grupo con un miembro, una categoría y un subgrupo, ya persistidos."""
    user = User(email=f"u{datetime.utcnow().timestamp()}@x.test", name="U")
    db_session.add(user)
    db_session.flush()

    group = Group(name="G", join_token=f"t{user.id}", owner_id=user.id)
    db_session.add(group)
    db_session.flush()

    member = GroupMember(group_id=group.id, user_id=user.id)
    category = Category(group_id=group.id, name="Ayudante")
    subgroup = SubGroup(parent_group_id=group.id, name="S")
    db_session.add_all([member, category, subgroup])
    db_session.flush()

    return {
        "user": user,
        "group": group,
        "member": member,
        "category": category,
        "subgroup": subgroup,
    }


def test_group_member_rechaza_duplicado_y_permite_reingreso(db_session, fixture_group):
    group, user = fixture_group["group"], fixture_group["user"]

    _flush_expecting_conflict(
        db_session, GroupMember(group_id=group.id, user_id=user.id)
    )

    fixture_group["member"].soft_delete()
    db_session.flush()
    db_session.add(GroupMember(group_id=group.id, user_id=user.id))
    db_session.flush()


def test_category_rechaza_duplicado_sin_distinguir_mayusculas(db_session, fixture_group):
    group = fixture_group["group"]

    # El índice va sobre lower(name): "AYUDANTE" es el mismo nombre.
    _flush_expecting_conflict(db_session, Category(group_id=group.id, name="AYUDANTE"))

    fixture_group["category"].soft_delete()
    db_session.flush()
    db_session.add(Category(group_id=group.id, name="ayudante"))
    db_session.flush()


def test_group_member_category_rechaza_duplicado(db_session, fixture_group):
    member, category = fixture_group["member"], fixture_group["category"]
    assoc = GroupMemberCategory(group_member_id=member.id, category_id=category.id)
    db_session.add(assoc)
    db_session.flush()

    _flush_expecting_conflict(
        db_session,
        GroupMemberCategory(group_member_id=member.id, category_id=category.id),
    )

    assoc.soft_delete()
    db_session.flush()
    db_session.add(
        GroupMemberCategory(group_member_id=member.id, category_id=category.id)
    )
    db_session.flush()


def test_subgroup_member_rechaza_duplicado(db_session, fixture_group):
    subgroup, user = fixture_group["subgroup"], fixture_group["user"]
    membership = SubGroupMember(subgroup_id=subgroup.id, user_id=user.id)
    db_session.add(membership)
    db_session.flush()

    _flush_expecting_conflict(
        db_session, SubGroupMember(subgroup_id=subgroup.id, user_id=user.id)
    )

    membership.soft_delete()
    db_session.flush()
    db_session.add(SubGroupMember(subgroup_id=subgroup.id, user_id=user.id))
    db_session.flush()


def test_user_availability_rechaza_duplicado(db_session, fixture_group):
    group, user = fixture_group["group"], fixture_group["user"]
    slot = Availability(group_id=group.id, weekday=0, hour=8.5)
    db_session.add(slot)
    db_session.flush()

    mark = UserAvailability(user_id=user.id, availability_id=slot.id)
    db_session.add(mark)
    db_session.flush()

    _flush_expecting_conflict(
        db_session, UserAvailability(user_id=user.id, availability_id=slot.id)
    )

    mark.soft_delete()
    db_session.flush()
    db_session.add(UserAvailability(user_id=user.id, availability_id=slot.id))
    db_session.flush()


def test_availability_rechaza_bloque_duplicado(db_session, fixture_group):
    """`availability` no tiene borrado lógico: acá el unique es total."""
    group = fixture_group["group"]
    db_session.add(Availability(group_id=group.id, weekday=0, hour=8.5))
    db_session.flush()

    _flush_expecting_conflict(
        db_session, Availability(group_id=group.id, weekday=0, hour=8.5)
    )
