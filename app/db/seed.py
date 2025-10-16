from app import scheduler_app, scheduler_db
import random
from ..models import User, Group, Category, GroupMember, GroupMemberCategory, Availability, UserAvailability


def seed_database():
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
        GroupMemberCategory(group_member_id=group_members[0].id, category_id=categories[0].id),  # Owner -> Men
        GroupMemberCategory(group_member_id=group_members[3].id, category_id=categories[0].id),  # Ana -> Men
        GroupMemberCategory(group_member_id=group_members[5].id, category_id=categories[0].id),  # Carla -> Men
        GroupMemberCategory(group_member_id=group_members[4].id, category_id=categories[1].id),  # Bruno -> Women
        GroupMemberCategory(group_member_id=group_members[5].id, category_id=categories[1].id),  # Carla -> Women (multiple categories)
        # Estudio Matemáticas
        GroupMemberCategory(group_member_id=group_members[1].id, category_id=categories[3].id),  # Owner -> High
        GroupMemberCategory(group_member_id=group_members[6].id, category_id=categories[3].id),  # Bruno -> High
        GroupMemberCategory(group_member_id=group_members[7].id, category_id=categories[3].id),  # Ana -> High
        GroupMemberCategory(group_member_id=group_members[8].id, category_id=categories[3].id),  # David -> High
        GroupMemberCategory(group_member_id=group_members[9].id, category_id=categories[3].id),  # Elena -> High
        # Equipo Deportivo
        GroupMemberCategory(group_member_id=group_members[2].id, category_id=categories[5].id),  # Owner -> Fast
        GroupMemberCategory(group_member_id=group_members[10].id, category_id=categories[5].id),  # Carla -> Fast
        GroupMemberCategory(group_member_id=group_members[11].id, category_id=categories[5].id),  # Felipe -> Fast
    ]
    scheduler_db.session.add_all(group_member_categories)
    scheduler_db.session.commit()

    # === AVAILABILITY ===
    # Horario de 8:30 a 19:20 -> intervalos de 1 hora
    hours = [8.5 + i for i in range(11)]  # 8.5 → 19.5
    availability_list = []
    for group in groups:
        for weekday in range(7):  # Lunes a domingo
            for hour in random.sample(hours, k=3):  # 3 horarios disponibles al azar por día
                availability_list.append(Availability(group_id=group.id, weekday=weekday, hour=hour))
    scheduler_db.session.add_all(availability_list)
    scheduler_db.session.commit()

    # === USER AVAILABILITY ===
    # Crear disponibilidad solo para miembros del grupo correspondiente
    for group_member in group_members:
        # Obtener las disponibilidades del grupo de este miembro
        group_availabilities = Availability.query.filter_by(group_id=group_member.group_id).all()
        if group_availabilities:
            # Seleccionar algunas disponibilidades al azar (máximo 10 o todas si hay menos)
            num_to_select = min(10, len(group_availabilities))
            selected_availabilities = random.sample(group_availabilities, k=num_to_select)
            for avail in selected_availabilities:
                scheduler_db.session.add(UserAvailability(user_id=group_member.user_id, availability_id=avail.id))
    scheduler_db.session.commit()
    
    print("Datos creados correctamente!")


if __name__ == "__main__":
    with scheduler_app.app_context():
        seed_database()
