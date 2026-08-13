"""Medición del peso del HTML de las vistas calientes (PERF-003).

No es un test: mide cuántos bytes pesa el HTML servido y cuánto de eso es el
JSON inline embebido, con el mismo dataset que `bench_queries.py`. Se corre a
mano antes y después de recortar el payload.

    python tests/bench_payload.py
    python tests/bench_payload.py --members 200
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# pylint: disable=wrong-import-position
import bench_queries as bench  # noqa: E402  (setea el entorno y la BD temporal)

from app import scheduler_app  # noqa: E402
from app.extensions import scheduler_db  # noqa: E402

EMBED_RE = re.compile(
    r'<script type="application/json" id="embed-data"[^>]*>(.*?)</script>', re.DOTALL
)


def kib(n):
    return f"{n / 1024:.1f} KiB"


def report(client, label, path):
    response = client.get(path)
    body = response.get_data(as_text=True)
    total = len(body.encode("utf-8"))
    match = EMBED_RE.search(body)
    embed_raw = match.group(1) if match else ""
    embed_bytes = len(embed_raw.encode("utf-8"))

    print(f"\n{label}  {path}  HTTP {response.status_code}")
    print(f"  HTML total : {kib(total):>10}")
    if not embed_raw:
        print("  JSON inline:          —")
        return
    share = 100 * embed_bytes / total
    print(f"  JSON inline: {kib(embed_bytes):>10}  ({share:.0f}% del HTML)")
    payload = json.loads(embed_raw)
    rows = sorted(
        ((k, len(json.dumps(v, separators=(",", ":")).encode("utf-8")))
         for k, v in payload.items()),
        key=lambda item: -item[1],
    )
    for key, size in rows:
        print(f"      {key:<22}{kib(size):>10}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--members", type=int, default=bench.N_MEMBERS)
    args = parser.parse_args()
    bench.N_MEMBERS = args.members

    scheduler_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    try:
        with scheduler_app.app_context():
            scheduler_db.create_all()
            owner_id, group_id = bench.seed()

            client = scheduler_app.test_client()
            with client.session_transaction() as flask_session:
                flask_session["_user_id"] = str(owner_id)
                flask_session["_fresh"] = True

            print(f"\nDataset: {args.members} miembros · {bench.N_CATEGORIES} categorías · "
                  f"{bench.N_SUBGROUPS} subgrupos · "
                  f"{args.members * bench.MARKS_PER_MEMBER} marcas")
            report(client, "groups.show", f"/groups/{group_id}")
            report(client, "groups.availability", f"/groups/{group_id}/availability")
            print()
    finally:
        os.unlink(bench._DB_PATH)  # pylint: disable=protected-access


if __name__ == "__main__":
    main()
