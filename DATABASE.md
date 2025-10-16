# 🗄️ Gestión de Base de Datos - Scheduler

## Solución Rápida al Error

Si ves el error `relation "user" does not exist`, significa que las tablas no están creadas. **Solución:**

```bash
# Opción 1: Usar el script de gestión (Recomendado)
./db-manager.sh
# Luego selecciona opción 1 (Setup)

# Opción 2: Comandos directos
docker exec -it backend_container python -m app.db.setup
```

## Scripts Disponibles

### 📜 Script Interactivo: `db-manager.sh`

```bash
./db-manager.sh
```

Este script interactivo te permite gestionar la base de datos fácilmente:

1. **Setup** - Configuración inicial completa (crear BD + tablas + datos)
2. **Create** - Solo crear tablas (sin datos)
3. **Seed** - Solo poblar con datos de prueba
4. **Reset** - Eliminar todo y recrear con datos
5. **Drop** - Eliminar todas las tablas
6. **Status** - Ver estado actual de la BD

### 🔧 Comandos Directos

Si prefieres ejecutar comandos directamente:

```bash
# Configuración completa (recomendado para primera vez)
docker exec -it backend_container python -m app.db.setup

# Solo crear tablas
docker exec -it backend_container python -m app.db.migrate

# Solo poblar datos
docker exec -it backend_container python -m app.db.seed

# Resetear (eliminar y recrear)
docker exec -it backend_container python -m app.db.reset

# Eliminar todas las tablas
docker exec -it backend_container python -m app.db.drop

# Crear base de datos (solo necesario si no existe)
docker exec -it backend_container python -m app.db.create
```

## 🚀 Flujo de Trabajo Típico

### Primera vez (setup inicial)

```bash
# 1. Levantar contenedores
docker compose up -d --build

# 2. Inicializar base de datos
docker exec -it backend_container python -m app.db.setup

# 3. Verificar que funciona
curl http://localhost:5050
```

### Desarrollo normal

```bash
# Levantar aplicación
docker compose up -d

# Si necesitas datos de prueba frescos
docker exec -it backend_container python -m app.db.reset
docker exec -it backend_container python -m app.db.seed
```

### Limpiar y empezar de cero

```bash
# Detener todo y eliminar volúmenes
docker compose down -v

# Reconstruir e inicializar
docker compose up -d --build
docker exec -it backend_container python -m app.db.setup
```

## 📊 Verificar Estado

```bash
# Ver logs del backend
docker compose logs -f backend

# Ver logs de la base de datos
docker compose logs -f db

# Conectar a PostgreSQL directamente
docker exec -it postgres_container psql -U postgres -d scheduler

# Verificar datos en Python
docker exec -it backend_container python -c "
from app import scheduler_app
from app.models import User
from app.extensions import scheduler_db

with scheduler_app.app_context():
    print(f'Total usuarios: {User.query.count()}')
"
```

## 🐛 Solución de Problemas

### Error: "relation does not exist"

**Causa:** Las tablas no están creadas.

**Solución:**

```bash
docker exec -it backend_container python -m app.db.setup
```

### Error: "connection refused"

**Causa:** PostgreSQL no está listo o las credenciales son incorrectas.

**Solución:**

```bash
# Verificar que los contenedores estén corriendo
docker compose ps

# Reiniciar servicios
docker compose restart

# Ver logs para más detalles
docker compose logs db
```

### Error: "table already exists"

**Causa:** Intentaste crear tablas que ya existen.

**Solución:**

```bash
# Si quieres empezar de cero
docker exec -it backend_container python -m app.db.reset
docker exec -it backend_container python -m app.db.seed

# O eliminar todo
docker compose down -v
docker compose up -d --build
docker exec -it backend_container python -m app.db.setup
```

### Los datos no se guardan entre reinicios

**Causa:** Los volúmenes de Docker no están configurados correctamente.

**Verificación:**

```bash
# Ver volúmenes
docker volume ls

# El volumen de postgres debe existir
docker volume inspect scheduler_postgres_data
```

## 📁 Estructura de Scripts

```
app/db/
├── __init__.py
├── create.py    # Crear base de datos (PostgreSQL o MySQL)
├── migrate.py   # Crear/actualizar tablas (SQLAlchemy)
├── seed.py      # Poblar con datos de prueba
├── setup.py     # Ejecuta create + migrate + seed
├── reset.py     # Drop + Create tablas
└── drop.py      # Eliminar todas las tablas
```

## 🔐 Configuración de Base de Datos

### Docker (PostgreSQL)

En `docker-compose.yml`:

```yaml
DATABASE_URI: postgresql://postgres:postgres@db:5432/scheduler
```

### Local (MySQL o PostgreSQL)

En `.env`:

```bash
# PostgreSQL
DATABASE_URI=postgresql://usuario:password@localhost:5432/scheduler_db

# MySQL
DB_NAME=scheduler_db
DB_USER=root
DB_PASSWORD=tu_password
DB_HOST=localhost
```

## 💡 Tips

1. **Usa el script interactivo** (`./db-manager.sh`) para operaciones comunes
2. **Siempre ejecuta `setup`** en la primera inicialización
3. **Usa `reset + seed`** cuando necesites datos frescos durante desarrollo
4. **Haz backup** antes de ejecutar operaciones destructivas en producción
5. **Los datos de `seed.py`** son solo para desarrollo/testing

## 📚 Datos de Prueba

El script `seed.py` crea:

- ✅ 6 usuarios de ejemplo (Ana, Bruno, Carla, David, Elena, Felipe)
- ✅ 2 grupos de ejemplo
- ✅ Membresías y roles asignados
- ✅ Categorías de ejemplo
- ✅ Disponibilidad horaria de muestra

## 🚨 Importante

- ⚠️ **NUNCA** ejecutes `reset` o `drop` en producción sin backup
- ⚠️ Los scripts están optimizados para **desarrollo local**
- ⚠️ En producción, usa migraciones apropiadas (Alembic)
- ⚠️ Las credenciales en `docker-compose.yml` son para desarrollo

## 🔗 Enlaces Útiles

- [Documentación SQLAlchemy](https://docs.sqlalchemy.org/)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- [Docker Compose Docs](https://docs.docker.com/compose/)
