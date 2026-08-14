import random

from app import scheduler_app, scheduler_db
from app.soft_delete import including_deleted

from ..models import (
    Availability,
    Category,
    Group,
    GroupMember,
    GroupMemberCategory,
    GroupPermissionGrant,
    User,
    UserAvailability,
)

_SEED_EMAILS = {
    "ana@example.com",
    "bruno@example.com",
    "carla@example.com",
    "david@example.com",
    "elena@example.com",
    "felipe@example.com",
}
_SEED_TOKENS = {"alphatoken", "mathstoken", "sporttoken"}


def _clear_seed_data():
    """Borra físicamente los datos del seed anterior para poder recrearlos.

    Con el `ondelete` explícito de las FKs basta borrar las raíces:
    la BD se lleva membresías, categorías, asignaciones, concesiones, bloques,
    marcas y jobs. Antes había que ordenar esos borrados a mano.

    La consulta corre dentro de `including_deleted()` porque el filtro global
    escondería las filas ya borradas lógicamente, que también hay que barrer.
    """
    with including_deleted():
        seed_user_ids = [
            row[0]
            for row in scheduler_db.session.query(User.id)
            .filter(User.email.in_(_SEED_EMAILS))
            .all()
        ]

        # Un grupo cuyo dueño es un usuario del seed cae con él (owner_id es
        # CASCADE), pero los grupos del owner fijo hay que pedirlos por token.
        group_filter = Group.join_token.in_(_SEED_TOKENS)
        if seed_user_ids:
            group_filter = group_filter | Group.owner_id.in_(seed_user_ids)
        scheduler_db.session.query(Group).filter(group_filter).delete(synchronize_session=False)

        if seed_user_ids:
            scheduler_db.session.query(User).filter(User.id.in_(seed_user_ids)).delete(
                synchronize_session=False
            )

        scheduler_db.session.commit()


def seed_database():
    print("Limpiando datos anteriores...")
    _clear_seed_data()
    print("Creando datos...")

    # === USERS ===
    users = [
        User(email="ana@example.com", name="Ana Pérez"),
        User(email="bruno@example.com", name="Bruno Díaz"),
        User(email="carla@example.com", name="Carla Soto"),
        User(email="david@example.com", name="David Ramos"),
        User(email="elena@example.com", name="Elena Fuentes"),
        User(email="felipe@example.com", name="Felipe Núñez"),
    ]
    scheduler_db.session.add_all(users)
    scheduler_db.session.commit()

    owner = User.query.filter_by(email="azuiga@miuandes.cl").first()
    if not owner:
        owner = User(email="azuiga@miuandes.cl", name="Alberto Zúñiga")
        scheduler_db.session.add(owner)
        scheduler_db.session.commit()

    # === GROUPS ===
    groups = [
        Group(name="Proyecto Alpha", join_token="alphatoken", owner=owner),
        Group(name="Estudio Matemáticas", join_token="mathstoken", owner=owner),
        Group(name="Equipo Deportivo", join_token="sporttoken", owner=owner),
    ]
    scheduler_db.session.add_all(groups)
    scheduler_db.session.commit()

    # === CATEGORIES ===
    categories = [
        Category(group_id=groups[0].id, name="Men"),
        Category(group_id=groups[0].id, name="Women"),
        Category(group_id=groups[0].id, name="Great"),
        Category(group_id=groups[1].id, name="High"),
        Category(group_id=groups[1].id, name="Low"),
        Category(group_id=groups[2].id, name="Fast"),
        Category(group_id=groups[2].id, name="Slow"),
    ]
    scheduler_db.session.add_all(categories)
    scheduler_db.session.commit()

    # === GROUP MEMBERS ===
    group_members = [
        # Owner debe ser miembro ADMIN de todos sus grupos
        GroupMember(group_id=groups[0].id, user_id=owner.id, role="ADMIN"),
        GroupMember(group_id=groups[1].id, user_id=owner.id, role="ADMIN"),
        GroupMember(group_id=groups[2].id, user_id=owner.id, role="ADMIN"),
        # Otros miembros
        GroupMember(group_id=groups[0].id, user_id=users[0].id, role="ADMIN"),
        GroupMember(group_id=groups[0].id, user_id=users[1].id, role="MEMBER"),
        GroupMember(group_id=groups[0].id, user_id=users[2].id, role="MEMBER"),
        GroupMember(group_id=groups[1].id, user_id=users[1].id, role="ADMIN"),
        GroupMember(group_id=groups[1].id, user_id=users[0].id, role="MEMBER"),
        GroupMember(group_id=groups[1].id, user_id=users[3].id, role="MEMBER"),
        GroupMember(group_id=groups[1].id, user_id=users[4].id, role="MEMBER"),
        GroupMember(group_id=groups[2].id, user_id=users[2].id, role="ADMIN"),
        GroupMember(group_id=groups[2].id, user_id=users[5].id, role="MEMBER"),
    ]
    scheduler_db.session.add_all(group_members)
    scheduler_db.session.commit()

    # === GROUP MEMBER CATEGORIES ===
    group_member_categories = [
        # Proyecto Alpha
        GroupMemberCategory(
            group_member_id=group_members[0].id, category_id=categories[0].id
        ),  # Owner -> Men
        GroupMemberCategory(
            group_member_id=group_members[3].id, category_id=categories[0].id
        ),  # Ana -> Men
        GroupMemberCategory(
            group_member_id=group_members[5].id, category_id=categories[0].id
        ),  # Carla -> Men
        GroupMemberCategory(
            group_member_id=group_members[4].id, category_id=categories[1].id
        ),  # Bruno -> Women
        GroupMemberCategory(
            group_member_id=group_members[5].id, category_id=categories[1].id
        ),  # Carla -> Women (multiple categories)
        # Estudio Matemáticas
        GroupMemberCategory(
            group_member_id=group_members[1].id, category_id=categories[3].id
        ),  # Owner -> High
        GroupMemberCategory(
            group_member_id=group_members[6].id, category_id=categories[3].id
        ),  # Bruno -> High
        GroupMemberCategory(
            group_member_id=group_members[7].id, category_id=categories[3].id
        ),  # Ana -> High
        GroupMemberCategory(
            group_member_id=group_members[8].id, category_id=categories[3].id
        ),  # David -> High
        GroupMemberCategory(
            group_member_id=group_members[9].id, category_id=categories[3].id
        ),  # Elena -> High
        # Equipo Deportivo
        GroupMemberCategory(
            group_member_id=group_members[2].id, category_id=categories[5].id
        ),  # Owner -> Fast
        GroupMemberCategory(
            group_member_id=group_members[10].id, category_id=categories[5].id
        ),  # Carla -> Fast
        GroupMemberCategory(
            group_member_id=group_members[11].id, category_id=categories[5].id
        ),  # Felipe -> Fast
    ]
    scheduler_db.session.add_all(group_member_categories)
    scheduler_db.session.commit()

    # === PERMISSION GRANTS (subgrupos) ===
    # Ejemplo de los dos modos de concesión: por categoría (dinámico, afecta a
    # quien tenga "Women" en Proyecto Alpha) y directo a una persona puntual.
    permission_grants = [
        GroupPermissionGrant(
            group_id=groups[0].id,
            permission="subgroups.view_all",
            category_id=categories[1].id,  # Women
        ),
        GroupPermissionGrant(
            group_id=groups[0].id,
            permission="subgroups.edit_own",
            group_member_id=group_members[5].id,  # Carla, MEMBER en Proyecto Alpha
        ),
    ]
    scheduler_db.session.add_all(permission_grants)
    scheduler_db.session.commit()

    # === AVAILABILITY ===
    availability_list = []
    for group in groups:
        block_starts = group.block_starts()
        for weekday in range(7):
            for start_minutes in random.sample(block_starts, k=min(3, len(block_starts))):
                availability_list.append(
                    Availability(group_id=group.id, weekday=weekday, start_minutes=start_minutes)
                )
    scheduler_db.session.add_all(availability_list)
    scheduler_db.session.commit()

    # === USER AVAILABILITY ===
    for group_member in group_members:
        group_availabilities = Availability.query.filter_by(group_id=group_member.group_id).all()
        if group_availabilities:
            selected = random.sample(group_availabilities, k=min(10, len(group_availabilities)))
            for avail in selected:
                scheduler_db.session.add(
                    UserAvailability(user_id=group_member.user_id, availability_id=avail.id)
                )
    scheduler_db.session.commit()

    print("Datos creados correctamente!")


if __name__ == "__main__":
    with scheduler_app.app_context():
        seed_database()
