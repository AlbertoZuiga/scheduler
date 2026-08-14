## Qué cambia

<!-- Suficiente para revisar sin abrir el diff. Bullets o tabla. -->

## Por qué

<!-- El problema real, con la evidencia que lo justifica: números, output de una
herramienta, el comportamiento roto. Si esta sección es genérica, el PR no está listo. -->

## Cómo verificarlo

```bash
ruff format --check . && ruff check .
pytest -q --cov=app --cov-fail-under=54
npm run lint:js
```

<!-- Y lo específico de este cambio: qué correr, qué se espera ver. -->

## Queda fuera a propósito

<!-- Borrar si no aplica. Si algo del alcance no entró, decir qué y por qué. -->

---

- [ ] Los tres gates pasan localmente
- [ ] Si es un `fix`: hay un test que falla sin el arreglo
- [ ] Un PR = un cambio (los reformateos mecánicos van aparte)
- [ ] Toda supresión nueva (`# noqa`, `# pylint: disable`, `// eslint-disable`) lleva su justificación
