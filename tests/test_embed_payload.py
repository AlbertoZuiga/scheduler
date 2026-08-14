"""El JSON inline de groups.show solo lleva lo que el JS lee.

El payload crece O(miembros × slots), así que cada clave de más se paga en
cada page view. Este test congela el contrato: si alguien agrega una clave al
`embed_data` sin consumirla en el script de la vista, falla.

Para medir el peso real del HTML, ver `tests/bench_payload.py`.
"""

import json
import pathlib
import re

import flask
from test_query_counts import _seed_group  # noqa: F401

_GROUP_SHOW_JS = (
    pathlib.Path(__file__).parent.parent / "app" / "static" / "js" / "group_show.js"
).read_text()

EMBED_RE = re.compile(
    r'<script type="application/json" id="embed-data"[^>]*>(.*?)</script>', re.DOTALL
)

CLAVES_ESPERADAS = {
    "group_id",
    "can_manage",
    "can_view_availability",
    "members",
    "member_category_map",
    "user_subgroup_map",
    "user_gm_map",
    "availability",
    "responded_user_ids",
}


def test_el_embed_de_show_solo_trae_las_claves_que_usa_el_js(app, db_session):
    group_id, owner_id = _seed_group(db_session, 5, "embed")

    flask.g.pop("_login_user", None)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["_user_id"] = str(owner_id)
        flask_session["_fresh"] = True

    response = client.get(f"/groups/{group_id}")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    match = EMBED_RE.search(body)
    assert match, "groups.show ya no embebe el JSON con id=embed-data"
    payload = json.loads(match.group(1))

    assert set(payload) == CLAVES_ESPERADAS

    # Cada clave del payload tiene que aparecer leída en el script de la vista.
    # Se excluye el bloque embed-data para no confundir valores JSON con lecturas JS.
    # group_show.js es externo: la búsqueda abarca el HTML renderizado y el archivo estático.
    html_body = body[: match.start()] + body[match.end() :]
    js_body = html_body + _GROUP_SHOW_JS
    for clave in payload:
        assert f"__EMBED__.{clave}" in js_body, f"'{clave}' se embebe pero nadie lo lee"
