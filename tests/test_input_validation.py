"""El largo de los strings de usuario se valida en el server.

Sin esto, un nombre más largo que la columna llega al INSERT y Postgres tira
`DataError` → 500 crudo. En SQLite (el motor de la suite) el largo no se
enforcea, así que los tests verifican lo que sí es observable: la request se
rechaza y no se escribe la fila.
"""

# pylint: disable=redefined-outer-name
import pytest

from app.models import Category, Group, GroupMember, RoleEnum
from app.models.subgroup import SubGroup
from app.models.user import User


@pytest.fixture()
def owner(db_session):
    user = User(name="Dueño largo", email="owner-largo@example.com")
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def logged_client(client, owner):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(owner.id)
        sess["_fresh"] = True
    return client


@pytest.fixture()
def group(db_session, owner):
    grupo = Group(name="Grupo largo", owner_id=owner.id, join_token="tok-largo")
    db_session.add(grupo)
    db_session.commit()
    db_session.add(GroupMember(group_id=grupo.id, user_id=owner.id, role=RoleEnum.ADMIN))
    db_session.commit()
    return grupo


def test_crear_grupo_con_nombre_muy_largo_no_es_500(logged_client, db_session):
    response = logged_client.post("/groups/create", data={"group_name": "x" * 151})

    assert response.status_code == 400
    assert db_session.query(Group).filter_by(name="x" * 151).first() is None


def test_crear_grupo_con_nombre_vacio_no_es_500(logged_client, db_session):
    response = logged_client.post("/groups/create", data={"group_name": "   "})

    assert response.status_code == 400
    assert db_session.query(Group).filter_by(owner_id=None).first() is None


def test_crear_grupo_con_nombre_en_el_limite_funciona(logged_client, db_session):
    nombre = "y" * 150

    response = logged_client.post("/groups/create", data={"group_name": nombre})

    assert response.status_code == 302
    assert db_session.query(Group).filter_by(name=nombre).first() is not None


def test_crear_categoria_con_nombre_muy_largo_no_es_500(logged_client, group, db_session):
    response = logged_client.post(f"/categories/group/{group.id}", json={"name": "z" * 151})

    assert response.status_code == 400
    assert db_session.query(Category).filter_by(group_id=group.id).first() is None


def test_crear_subgrupo_manual_con_nombre_muy_largo_no_es_500(logged_client, group, db_session):
    response = logged_client.post(
        f"/groups/{group.id}/subgroups/create_manual", data={"name": "w" * 201}
    )

    assert response.status_code == 302
    assert db_session.query(SubGroup).filter_by(parent_group_id=group.id).first() is None


def test_renombrar_subgrupo_con_nombre_muy_largo_no_lo_cambia(logged_client, group, db_session):
    subgrupo = SubGroup(parent_group_id=group.id, name="Original", auto_generated=False)
    db_session.add(subgrupo)
    db_session.commit()

    response = logged_client.post(
        f"/groups/{group.id}/subgroups/{subgrupo.id}/rename", data={"name": "v" * 201}
    )

    assert response.status_code == 302
    db_session.refresh(subgrupo)
    assert subgrupo.name == "Original"
