# Reglas del repositorio

Flask + SQLAlchemy + Alembic. Tests con pytest, JS estático con ESLint, Python con Ruff.

## Idioma

Todo en español: commits, ramas, PRs, comentarios, docstrings. El historial anterior
mezcla inglés; desde acá no.

## Antes de pedir review — los tres comandos

```bash
ruff format --check . && ruff check .
pytest -q --cov=app --cov-fail-under=54
npm run lint:js
```

Los tres bloquean el merge en CI. `--cov-fail-under` **sube, nunca baja**: si un cambio lo
rompe, se agregan tests, no se edita el número.

`pylint --rcfile=.pylintrc --disable=C,R0801 app config.py run.py tests` corre en CI sin
bloquear. Reporta olores de diseño; leerlo, no ignorarlo.

## Commits

Conventional Commits: `tipo(ámbito): descripción`. Imperativo, ≤72 caracteres el asunto,
sin punto final.

- Tipos: `feat` `fix` `refactor` `perf` `test` `docs` `build` `chore` `ci`
- Ámbitos reales: `group` `subgroup` `availability` `auth` `authz` `db` `js` `deps` `ci` `test`
- Cuerpo solo cuando el *por qué* no se deduce del diff. Ahí va el porqué, no el qué.

## Ramas

`tipo/descripcion-en-kebab-case`, mismos tipos que los commits
(`refactor/extrae-group-service`, `fix/email-visibility`).

Nunca commitear sobre `main`; entra solo por PR. Nunca `git push --force`.

## PRs

Título = el commit principal. Cuerpo con **qué cambia**, **por qué** y **cómo verificarlo**.
Un PR = un cambio: los reformateos mecánicos y los renombres masivos van en PR propio.
No mergear con CI en rojo — la protección de `main` lo impide, no intentar rodearla.

## Arquitectura — no revertir estas decisiones

- **La lógica de dominio vive en `app/services/`, no en `app/routes/`.** Las rutas validan
  permisos, llaman al servicio y arman la respuesta. Nada de queries en un route handler.
  Los servicios **no commitean**: la transacción la maneja quien llama.
- **Nada de JS inline en templates.** Va en `app/static/js/`, cubierto por ESLint. Los datos
  que el JS necesita viajan por el bloque `<script type="application/json" id="embed-data">`.
- **El embed no lleva identidades ajenas** a quien no tiene el permiso correspondiente.
- `scheduler_app` se construye vía el `__getattr__` (PEP 562) de `app/__init__.py`. No
  reintroducir el factory en el cuerpo del módulo: importar cualquier submódulo levantaría
  la app entera como efecto de import.
- El esquema lo maneja Alembic. No hay runner de migraciones a mano.

## Código

Lo mínimo que resuelve el problema. Sin abstracciones, helpers, tipos ni validaciones que
nadie pidió; tres líneas repetidas son mejores que una abstracción prematura.

Cambiar solo lo pedido: no limpiar el código de alrededor en el mismo PR.

Los comentarios explican **por qué**, no qué hace la línea de abajo. No citar IDs de
auditoría (`BE-007`, `DOC-002`) en el código: se limpiaron a propósito, el comentario debe
sostenerse solo.

## Tests

- Todo `fix` necesita un test que falle sin el arreglo. Escribirlo primero, verlo fallar.
- `pytest.ini` tiene `filterwarnings = error`: un warning nuevo rompe el build. Arreglar la
  causa, no agregar un filtro.
- Los tests van en `tests/test_*.py`. Tocar `conftest.py` solo si el fixture es genuinamente
  compartido.
- Nombres de test en español y descriptivos del comportamiento, no del método
  (`test_miembro_sin_permiso_no_ve_chips_de_otros`).

## Prohibido

- Commitear `.env` o `client_secret.json` (gitleaks bloquea, pero no depender de eso).
- Agregar dependencias sin pinnear en `requirements.txt`.
- Bajar `--cov-fail-under`.
- Agregar `# pylint: disable`, `# noqa` o `// eslint-disable` sin un comentario que
  justifique por qué la regla no aplica ahí.
- Ampliar la lista `ignore` de `[tool.ruff.lint]` para hacer pasar un cambio.

## Skills

- `pr-nueva` — flujo completo rama → commits → PR.
- `revisar-cambios` — checklist antes de abrir el PR.
