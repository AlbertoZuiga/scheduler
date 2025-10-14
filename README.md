# Scheduler

Aplicación Flask para gestión de grupos y disponibilidad horaria.

## Seguridad y Control de Acceso

Se han implementado los siguientes controles de seguridad para prevenir acceso no autorizado (IDOR) y escalación de privilegios:

- Autenticación obligatoria (`@login_required`) en todas las rutas sensibles bajo `/group`.
- Helper centralizado en `app/authz.py` con funciones:
  - `require_group_member(group_id)` asegura pertenencia.
  - `require_group_admin_or_owner(group_id)` para acciones administrativas.
  - `require_group_owner(group_id)` restringe operaciones críticas (eliminar grupo, cambiar roles) al propietario.
  - `safe_remove_member(group_id, user_id)` aplica políticas al expulsar miembros (no eliminar owner, admins entre sí sin ser owner, etc.).
- Validación de pertenencia ahora presente en rutas:
  - `show`, `members`, `availability`, `delete`, `leave`, `remove`, `update_role`.
- Eliminado acceso potencial a información de disponibilidad de otros usuarios cuando no se poseen permisos.

### Riesgos Mitigados

1. Acceso directo a `/group/<id>` sin pertenencia (IDOR) -> Ahora retorna 403.
2. Expulsión arbitraria de miembros por cualquier usuario -> Restringido a owner o admin con reglas.
3. Cambio de roles por usuarios no propietarios -> Solo owner puede modificar roles.
4. Eliminación de grupo por no propietario -> Solo owner.
5. Visualización de disponibilidad agregada sin ser miembro -> Bloqueado.

### Próximos Pasos Recomendados

- Implementar protección CSRF (por ejemplo con `Flask-WTF` o `itsdangerous` tokens manuales) en formularios POST.
- Registrar auditoría de acciones críticas (cambios de rol, expulsiones, borrados) en tabla de logs.
- Rotación configurable del `join_token` y endpoint para regenerarlo.
- Limitar longitud y validar contenido de inputs (`group_name`).

## Ejecución Local

Instalar dependencias y ejecutar:

```bash
pip install -r requirements.txt
flask --app run.py run --debug
```
