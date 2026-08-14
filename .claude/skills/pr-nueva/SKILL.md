---
name: pr-nueva
description: Flujo completo para entregar un cambio en este repo — crear la rama, agrupar los commits, correr los gates y abrir el PR con el formato que el proyecto espera. Usar cuando el trabajo esté listo para entrar a main, o cuando el usuario pida "abre el PR", "sube esto", "crea la rama".
---

# Abrir un PR en scheduler

## 1. Rama

Nunca commitear sobre `main`. Desde `main` actualizado:

```bash
git checkout main && git pull
git checkout -b tipo/descripcion-en-kebab-case
```

`tipo` es el mismo del commit: `feat` `fix` `refactor` `perf` `test` `docs` `build` `chore` `ci`.

## 2. Agrupar los commits

Un commit = una idea que se puede revisar sola. En particular:

- Un cambio mecánico (reformateo, renombre masivo, autofix de linter) va **siempre en su
  propio commit**, nunca mezclado con lógica. Si no, el diff es irrevisable.
- Un hallazgo colateral (un bug que el linter destapó, un test muerto) va en su propio
  commit con su propia explicación.

Formato: `tipo(ámbito): descripción` en imperativo, ≤72 caracteres, sin punto final.
Cuerpo solo cuando el *por qué* no se deduce del diff — y entonces el cuerpo es el porqué,
no un resumen del qué.

## 3. Gates

Los tres tienen que pasar antes de push. Son los mismos que corren en CI:

```bash
ruff format --check . && ruff check .
pytest -q --cov=app --cov-fail-under=54
npm run lint:js
```

Si `ruff check` falla, `ruff check --fix .` y `ruff format .` arreglan casi todo. Lo que
queda (líneas largas dentro de strings, docstrings y comentarios) se corta a mano
**conservando el texto exacto** — son mensajes que ve el usuario.

Si el piso de cobertura falla: agregar tests. No editar el número.

## 4. Abrir el PR

```bash
git push -u origin <rama>
gh pr create --base main --title "<el commit principal>" --body "..."
```

El cuerpo lleva tres secciones, en este orden:

- **Qué cambia** — la lista de cambios, en bullets o tabla. Suficiente para revisar sin
  abrir el diff.
- **Por qué** — el problema real que se resuelve, con la evidencia que lo justifica
  (números, output de una herramienta, el comportamiento roto). Esta sección es la que
  vale; si es genérica, el PR no está listo.
- **Cómo verificarlo** — los comandos exactos y qué se espera de ellos.

Si algo del alcance quedó fuera a propósito, decirlo explícitamente en una sección aparte
con el motivo. No dejarlo implícito.

## 5. Esperar CI

```bash
gh pr checks <n> --watch --interval 15
```

Los tres jobs (`test`, `lint-js`, `security`) son required: con uno en rojo, GitHub bloquea
el merge. No intentar rodearlo.

## 6. Mergear

```bash
gh pr merge <n> --merge --delete-branch
```

Solo con los tres checks en verde y las conversaciones resueltas.
