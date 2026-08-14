# Cómo contribuir

Las mismas convenciones que siguen los agentes están en [`CLAUDE.md`](CLAUDE.md), que Claude
Code carga solo en cada sesión. Este documento es la versión para personas: si hay
discrepancia, gana `CLAUDE.md` y hay que corregir este archivo.

## Entorno

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
npm ci
```

Las variables de entorno (`.env`) y el levantamiento de la base están documentados en el
[README](README.md). El esquema lo maneja Alembic vía `python -m app.db.migrate`; no hay
runner de migraciones a mano.

## El ciclo

1. Rama desde `main` actualizado: `tipo/descripcion-en-kebab-case`.
2. Commits en Conventional Commits, en español, uno por idea revisable.
3. Los tres gates en verde.
4. PR con el template. CI verde. Merge.

`main` no acepta commits directos y no se puede mergear con CI en rojo.

## Los tres gates

```bash
ruff format --check . && ruff check .   # formato y lint de Python
pytest -q --cov=app --cov-fail-under=54 # tests y piso de cobertura
npm run lint:js                         # ESLint sobre app/static/js/
```

Los tres son *required status checks* en `main`. Además corre `gitleaks` sobre los commits
del PR y `pip-audit` sobre `requirements.txt`, ambos bloqueantes.

`pylint` corre sin bloquear (`--disable=C,R0801`): reporta olores de diseño, no defectos.
Vale la pena leerlo, pero no frena el merge.

### El piso de cobertura

`--cov-fail-under=54` es la cobertura medida cuando se instauró el gate. **Sube, nunca
baja.** Si un cambio lo rompe, se agregan tests; editar el número para que pase es la única
forma garantizada de que el gate deje de servir.

## Convenciones

**Idioma**: todo en español — commits, ramas, PRs, comentarios, docstrings.

**Commits**: `tipo(ámbito): descripción` en imperativo, ≤72 caracteres, sin punto final.

- Tipos: `feat` `fix` `refactor` `perf` `test` `docs` `build` `chore` `ci`
- Ámbitos: `group` `subgroup` `availability` `auth` `authz` `db` `js` `deps` `ci` `test`
- El cuerpo, cuando existe, explica el **porqué**. El qué ya está en el diff.

**Un PR = un cambio.** Los reformateos mecánicos, los renombres masivos y los autofix de
linter van en PR propio: mezclados con lógica hacen el diff irrevisable.

## Arquitectura — decisiones que no se revierten

- La lógica de dominio vive en `app/services/`, no en `app/routes/`. Las rutas validan
  permisos, llaman al servicio y arman la respuesta. Los servicios no commitean: la
  transacción la maneja quien llama.
- Nada de JS inline en templates. Va en `app/static/js/`, donde ESLint lo cubre. Los datos
  viajan por el bloque `<script type="application/json" id="embed-data">`.
- El embed no lleva identidades ajenas a quien no tiene el permiso correspondiente.
- `scheduler_app` se construye vía el `__getattr__` (PEP 562) de `app/__init__.py`, para que
  importar un submódulo no levante la app entera como efecto de import.

## Tests

Todo `fix` necesita un test que falle sin el arreglo — escribirlo primero y verlo fallar.
`pytest.ini` usa `filterwarnings = error` a propósito: un warning nuevo rompe el build y se
arregla la causa, no se agrega un filtro.

## Prohibido

- Commitear `.env` o `client_secret.json`.
- Agregar dependencias sin pinnear en `requirements.txt`.
- Bajar `--cov-fail-under`.
- Un `# noqa`, `# pylint: disable` o `// eslint-disable` sin comentario que justifique por
  qué la regla no aplica ahí.
- Ampliar la lista `ignore` de `[tool.ruff.lint]` para hacer pasar un cambio.
