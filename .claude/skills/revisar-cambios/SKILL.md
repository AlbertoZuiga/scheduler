---
name: revisar-cambios
description: Checklist de revisión propia del diff antes de abrir un PR en scheduler — arquitectura, tests, comentarios y las trampas conocidas del repo. Usar antes de pedir review, o cuando el usuario pida "revisa esto", "revisa el diff", "está listo para PR".
---

# Revisar el diff antes del PR

Correr `git diff main...HEAD` y pasar el diff por esto. Cada punto que falle se arregla
antes de abrir el PR, no después.

## Arquitectura

- [ ] **¿Hay queries en `app/routes/`?** La lógica de dominio va en `app/services/`. El
      route handler valida permisos, llama al servicio y arma la respuesta. El repo lleva
      más de diez commits sacando queries de las rutas; no reintroducirlas.
- [ ] **¿El servicio commitea?** No debe. La transacción la maneja quien llama.
- [ ] **¿Hay `<script>` con lógica dentro de un template?** Va a `app/static/js/`, donde
      ESLint lo cubre. Los datos viajan por el bloque `embed-data`.
- [ ] **¿El embed filtra identidades?** Nombres, emails o `user_id` de terceros no viajan al
      navegador de quien no tiene el permiso correspondiente. Hay tests dedicados a esto
      (`test_email_visibility.py`, `test_availability_view_permission.py`); si el cambio
      toca el payload, revisarlos.
- [ ] **¿El cambio toca permisos?** `app/permissions.py` define los niveles. Un permiso
      nuevo necesita test de que el nivel inferior **no** lo obtiene.

## Alcance

- [ ] ¿El diff hace solo lo que se pidió? Limpiezas de alrededor, renombres oportunistas y
      "ya que estaba" se sacan a otro PR.
- [ ] ¿Hay abstracciones, helpers o capas que nadie pidió? Tres líneas repetidas son mejores
      que una abstracción prematura.
- [ ] ¿Hay un cambio mecánico mezclado con lógica en el mismo commit? Separarlos.

## Tests

- [ ] ¿Es un `fix`? Entonces hay un test que **falla sin el arreglo**. Verificarlo de verdad:
      revertir el fix, ver el test en rojo, restaurar.
- [ ] ¿El test asegura el comportamiento o solo que no explota? Una aserción sobre el estado
      final vale; un `status_code == 200` solo, casi nunca.
- [ ] ¿Se agregó un filtro a `filterwarnings`? `pytest.ini` usa `error` a propósito. Arreglar
      la causa del warning.
- [ ] ¿Dos tests comparten nombre en el mismo archivo? El segundo oculta al primero y el
      primero deja de correr en silencio. `ruff check` lo detecta como `F811`.

## Comentarios y nombres

- [ ] ¿Los comentarios explican **por qué**, o narran lo que la línea de abajo ya dice?
- [ ] ¿Sobrevivió alguna cita a un ID de auditoría (`BE-007`, `DOC-002`, `FE-007`)? Se
      limpiaron a propósito: el comentario debe sostenerse sin el ticket.
- [ ] ¿Los nombres de test describen el comportamiento y están en español?

## Supresiones

- [ ] ¿Hay un `# noqa`, `# pylint: disable` o `// eslint-disable` nuevo? Cada uno necesita un
      comentario que explique por qué la regla no aplica ahí. Sin justificación, se arregla
      el código en vez de callar la herramienta.
- [ ] ¿Creció la lista `ignore` de `[tool.ruff.lint]` en `pyproject.toml`? Eso es cambiar la
      regla para que pase el cambio. Justificarlo en el PR o revertirlo.

## Gates

- [ ] `ruff format --check . && ruff check .`
- [ ] `pytest -q --cov=app --cov-fail-under=54`
- [ ] `npm run lint:js`
- [ ] ¿Bajó el piso de cobertura? No se edita: se agregan tests.
