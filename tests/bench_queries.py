"""Medición de queries por vista (PERF-001).

No es un test: es un script reproducible para contar cuántas consultas SQL
dispara cada vista caliente con datos de prueba realistas. Se corre a mano
antes y después de optimizar, y su salida es la evidencia del cambio.

    python tests/bench_queries.py           # tabla de conteos
    python tests/bench_queries.py --echo    # además vuelca el SQL a stderr

Se usa SQLite en un archivo temporal: los conteos de queries no dependen del
motor, y así la medición no necesita una base levantada.
"""

import argparse
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".sqlite")
os.close(_DB_FD)
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"
os.environ["DATABASE_URI"] = f"sqlite:///{_DB_PATH}"
os.environ["SECRET_KEY"] = "bench"
os.environ["URL"] = "http://localhost"
os.environ["GOOGLE_CLIENT_ID"] = "bench"
os.environ["GOOGLE_CLIENT_SECRET"] = "bench"

# pylint: disable=wrong-import-position
from sqlalchemy import event  # noqa: E402

from app import scheduler_app  # noqa: E402
from app.extensions import scheduler_db  # noqa: E402
from app.models import (  # noqa: E402
    Availability,
    Category,
    Group,
    GroupMember,
    GroupMemberCategory,
    GroupPermissionGrant,
    RoleEnum,
    UserAvailability,
)
from app.models.subgroup import SubGroup, SubGroupMember  # noqa: E402
from app.models.user import User  # noqa: E402
from app.permissions import PERM_VIEW_ALL  # noqa: E402

# Escala de "grupo realista grande": un curso universitario dividiéndose en
# equipos. Lo suficiente para que un N+1 se note y siga corriendo en segundos.
N_MEMBERS = 60
N_CATEGORIES = 10
N_SUBGROUPS = 6
N_OTHER_GROUPS = 11        # el usuario ve 12 grupos en groups.index
WEEKDAYS = 5
BLOCKS_PER_DAY = 12
MARKS_PER_MEMBER = 30


def seed():
    """Crea el dataset de prueba y devuelve (owner_id, group_id)."""
    users = [User(email=f"u{i}@test.local", name=f"Usuario {i}") for i in range(N_MEMBERS)]
    scheduler_db.session.add_all(users)
    scheduler_db.session.flush()
    owner = users[0]

    group = Group(name="Grupo grande", join_token="bench-token", owner_id=owner.id)
    scheduler_db.session.add(group)
    scheduler_db.session.flush()

    members = [
        GroupMember(
            group_id=group.id,
            user_id=user.id,
            role=RoleEnum.ADMIN if user.id == owner.id else RoleEnum.MEMBER,
        )
        for user in users
    ]
    scheduler_db.session.add_all(members)

    categories = [Category(group_id=group.id, name=f"Categoría {i}") for i in range(N_CATEGORIES)]
    scheduler_db.session.add_all(categories)
    scheduler_db.session.flush()

    # Cada miembro en 2 categorías: la vista de permisos cuenta miembros por
    # categoría y show.html pinta los nombres de cada categoría.
    for i, member in enumerate(members):
        for offset in (0, 1):
            scheduler_db.session.add(
                GroupMemberCategory(
                    group_member_id=member.id,
                    category_id=categories[(i + offset) % N_CATEGORIES].id,
                )
            )

    availabilities = [
        Availability(group_id=group.id, weekday=weekday, start_minutes=(8 + block) * 60)
        for weekday in range(WEEKDAYS)
        for block in range(BLOCKS_PER_DAY)
    ]
    scheduler_db.session.add_all(availabilities)
    scheduler_db.session.flush()

    for i, user in enumerate(users):
        for slot in range(MARKS_PER_MEMBER):
            availability = availabilities[(i * 7 + slot) % len(availabilities)]
            scheduler_db.session.add(
                UserAvailability(user_id=user.id, availability_id=availability.id)
            )

    subgroups = [
        SubGroup(parent_group_id=group.id, name=f"Subgrupo {i}") for i in range(N_SUBGROUPS)
    ]
    scheduler_db.session.add_all(subgroups)
    scheduler_db.session.flush()
    for i, user in enumerate(users):
        scheduler_db.session.add(
            SubGroupMember(subgroup_id=subgroups[i % N_SUBGROUPS].id, user_id=user.id)
        )

    # Concesiones de permisos: filas de la tabla en groups.permissions.
    for category in categories:
        scheduler_db.session.add(
            GroupPermissionGrant(
                group_id=group.id, category_id=category.id, permission=PERM_VIEW_ALL
            )
        )
    for member in members[1:21]:
        scheduler_db.session.add(
            GroupPermissionGrant(
                group_id=group.id, group_member_id=member.id, permission=PERM_VIEW_ALL
            )
        )

    # Grupos extra para que groups.index liste 12 tarjetas, cada una con sus
    # miembros y categorías.
    for i in range(N_OTHER_GROUPS):
        other = Group(name=f"Otro grupo {i}", join_token=f"bench-{i}", owner_id=owner.id)
        scheduler_db.session.add(other)
        scheduler_db.session.flush()
        scheduler_db.session.add_all(
            GroupMember(group_id=other.id, user_id=user.id, role=RoleEnum.MEMBER)
            for user in users[: 5 + i]
        )
        scheduler_db.session.add_all(
            Category(group_id=other.id, name=f"Cat {j}") for j in range(3)
        )

    scheduler_db.session.commit()
    return owner.id, group.id


class QueryCounter:
    """Cuenta sentencias SQL ejecutadas dentro del bloque."""

    def __init__(self, echo=False):
        self.echo = echo
        self.statements = []

    def __enter__(self):
        event.listen(scheduler_db.engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *_exc):
        event.remove(scheduler_db.engine, "before_cursor_execute", self._on_execute)
        return False

    def _on_execute(self, _conn, _cursor, statement, _params, _context, _executemany):
        self.statements.append(statement)
        if self.echo:
            print(statement.replace("\n", " ")[:200], file=sys.stderr)

    def __len__(self):
        return len(self.statements)


def measure(client, label, path, echo):
    # Identity map en frío: si los objetos del seed siguen en la sesión, un
    # lazy load no llega a la base y el N+1 no se ve. Una request real siempre
    # arranca con la sesión vacía.
    scheduler_db.session.expunge_all()
    with QueryCounter(echo=echo) as counter:
        response = client.get(path)
    status = response.status_code
    if status != 200:
        print(f"  ⚠️  {label} devolvió {status}", file=sys.stderr)
    return label, path, len(counter), status


def main():
    global N_MEMBERS  # pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.add_argument("--echo", action="store_true", help="volcar el SQL a stderr")
    parser.add_argument("--members", type=int, default=N_MEMBERS,
                        help="miembros del grupo grande (para verificar que el "
                             "conteo de queries no crece con N)")
    args = parser.parse_args()
    N_MEMBERS = args.members

    scheduler_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False, SQLALCHEMY_ECHO=args.echo)

    with scheduler_app.app_context():
        scheduler_db.create_all()
        owner_id, group_id = seed()

        client = scheduler_app.test_client()
        with client.session_transaction() as flask_session:
            flask_session["_user_id"] = str(owner_id)
            flask_session["_fresh"] = True

        views = [
            ("groups.index", "/groups/"),
            ("groups.show", f"/groups/{group_id}"),
            ("groups.permissions", f"/groups/{group_id}/permissions"),
            ("groups.members", f"/groups/{group_id}/members"),
            ("groups.export_members_csv", f"/groups/{group_id}/members/export.csv"),
            ("subgroups.index", f"/groups/{group_id}/subgroups"),
            ("subgroups.new", f"/groups/{group_id}/subgroups/new"),
        ]
        # Primer pase de calentamiento: descarta el trabajo puntual del arranque
        # (metadata, sesión) para que el conteo sea el de la vista, no el del boot.
        for _, path in views:
            client.get(path)

        results = [measure(client, label, path, args.echo) for label, path in views]

    print(f"\nDataset: {N_MEMBERS} miembros · {N_CATEGORIES} categorías · "
          f"{N_SUBGROUPS} subgrupos · {N_MEMBERS * MARKS_PER_MEMBER} marcas · "
          f"{N_OTHER_GROUPS + 1} grupos en index\n")
    print(f"{'Vista':<32}{'Ruta':<34}{'Queries':>8}")
    print("-" * 74)
    for label, path, count, status in results:
        suffix = "" if status == 200 else f" (HTTP {status})"
        print(f"{label:<32}{path:<34}{count:>8}{suffix}")
    print()

    os.unlink(_DB_PATH)


if __name__ == "__main__":
    main()
