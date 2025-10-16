# 📅 Scheduler

> **Una aplicación web moderna para coordinar disponibilidad horaria en grupos**

Scheduler es una aplicación Flask full-stack diseñada para simplificar la coordinación de horarios entre múltiples personas. Con autenticación segura mediante Google OAuth 2.0, permite crear grupos, gestionar miembros con diferentes roles de acceso, y encontrar los mejores momentos para reunirse basándose en la disponibilidad individual de cada participante.

### ✨ ¿Por qué usar Scheduler?

- 🎯 **Fácil de usar**: Interfaz intuitiva para crear grupos y marcar disponibilidad
- 🔐 **Seguro**: Sistema robusto de autenticación y control de acceso basado en roles
- 🚀 **Listo para producción**: Completamente dockerizado con PostgreSQL
- 🎨 **Responsive**: Diseño adaptable a cualquier dispositivo
- 👥 **Colaborativo**: Gestión de grupos con roles (Owner, Admin, Member)

---

## 📋 Índice

- [Características](#-características)
- [Inicio Rápido](#-inicio-rápido)
- [Requisitos](#-requisitos)
- [Instalación y Configuración](#️-instalación-y-configuración)
  - [1. Clonar el Repositorio](#1-clonar-el-repositorio)
  - [2. Configurar Google OAuth](#2-configurar-google-oauth)
  - [3. Variables de Entorno](#3-variables-de-entorno)
- [Ejecución con Docker (Recomendado)](#-ejecución-con-docker-recomendado)
  - [Iniciar la Aplicación](#iniciar-la-aplicación)
  - [Verificar el Estado](#verificar-el-estado)
  - [Acceder a la Aplicación](#acceder-a-la-aplicación)
  - [Comandos Útiles](#comandos-útiles)
  - [Detener la Aplicación](#detener-la-aplicación)
- [Ejecución Local (Sin Docker)](#-ejecución-local-sin-docker)
- [Ejemplo de Uso](#-ejemplo-de-uso)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Base de Datos](#️-base-de-datos)
- [Seguridad y Control de Acceso](#-seguridad-y-control-de-acceso)
- [Solución de Problemas](#-solución-de-problemas)
- [Próximos Pasos](#-próximos-pasos)
- [Contribuciones](#-contribuciones)
- [Licencia](#-licencia)
- [Contacto](#-contacto)

## 🚀 Características

- ✅ **Autenticación segura** con Google OAuth 2.0
- ✅ **Gestión completa de grupos** y miembros con invitaciones
- ✅ **Sistema de disponibilidad horaria** flexible y visual
- ✅ **Control de acceso basado en roles** (Owner, Admin, Member)
- ✅ **Prevención de IDOR** y escalación de privilegios
- ✅ **Totalmente dockerizado** con PostgreSQL
- ✅ **Interfaz web responsiva** y moderna
- ✅ **Categorías personalizables** para miembros de grupos

---

## ⚡ Inicio Rápido

¿Quieres ver la aplicación funcionando en menos de 5 minutos?

```bash
# 1. Clona el repositorio
git clone https://github.com/AlbertoZuiga/scheduler.git
cd scheduler

# 2. Crea tu archivo .env con tus credenciales de Google
cat > .env << EOL
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret
SECRET_KEY=mi-clave-super-secreta
URL=http://localhost:5050
EOL

# 3. Inicia con Docker
docker compose up -d --build

# 4. Inicializa la base de datos (opcional: con datos de prueba)
docker exec -it backend_container python -m app.db.setup
docker exec -it backend_container python -m app.db.seed
```

🎉 **¡Listo!** Abre tu navegador en [http://localhost:5050](http://localhost:5050)

> **Nota**: Primero necesitas configurar las credenciales OAuth de Google (ver [Configurar Google OAuth](#2-configurar-google-oauth))

---

## 📦 Requisitos

### Para ejecutar con Docker (Recomendado):

- **Docker Desktop** (macOS/Windows) o **Docker Engine + Docker Compose** (Linux)
- **Git**
- Credenciales de **Google OAuth 2.0**

### Para ejecutar localmente (Sin Docker):

- **Python 3.11+**
- **PostgreSQL** (recomendado) o **MySQL**
- **Git**
- Credenciales de **Google OAuth 2.0**

---

## 🛠️ Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone https://github.com/AlbertoZuiga/scheduler.git
cd scheduler
```

### 2. Configurar Google OAuth

Para habilitar la autenticación con Google, necesitas crear credenciales OAuth 2.0:

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Navega a **APIs & Services → Credentials**
4. Click en **"+ CREATE CREDENTIALS"** → **"OAuth 2.0 Client ID"**
5. Selecciona **"Web application"**
6. Configura:
   - **Name:** Scheduler (o el nombre que prefieras)
   - **Authorized redirect URIs:**
     ```
     http://localhost:5050/auth/google/callback
     http://127.0.0.1:5000/auth/google/callback
     ```
7. Guarda el **Client ID** y **Client Secret**

### 3. Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

```bash
# ========================================
# Google OAuth (OBLIGATORIO)
# ========================================
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret

# ========================================
# Seguridad (OBLIGATORIO para producción)
# ========================================
SECRET_KEY=tu-clave-secreta-super-segura-y-aleatoria

# ========================================
# URL de la aplicación (OBLIGATORIO)
# ========================================
URL=http://localhost:5050

# ========================================
# Base de datos (OPCIONAL - solo para ejecución local sin Docker)
# ========================================
DB_NAME=scheduler_db
DB_USER=root
DB_PASSWORD=tu_password
DB_HOST=localhost

# ========================================
# Configuración adicional (OPCIONAL)
# ========================================
# Modo debug (valores: True, False, 1, 0, t, f)
DEBUG=True

# Host y puerto del servidor (por defecto: 0.0.0.0:5000)
HOST=0.0.0.0
PORT=5000

# URI completa de la base de datos (anula las variables DB_*)
# DATABASE_URI=postgresql://usuario:password@host:5432/database
# DATABASE_URI=mysql+pymysql://usuario:password@host:3306/database
```

#### 📝 Notas Importantes:

**Variables Obligatorias:**

- ✅ `GOOGLE_CLIENT_ID`: Tu Client ID de Google OAuth
- ✅ `GOOGLE_CLIENT_SECRET`: Tu Client Secret de Google OAuth
- ✅ `SECRET_KEY`: Clave para firmar sesiones (en producción, usa una clave fuerte y aleatoria)
- ✅ `URL`: URL base de tu aplicación

**Variables Opcionales:**

- `DEBUG`: Activa modo debug (solo para desarrollo, **NO usar en producción**)
- `DB_*`: Solo necesarias para ejecución local sin Docker
- `DATABASE_URI`: Sobrescribe la configuración de base de datos (útil para servicios como Render)
- `HOST` y `PORT`: Configuración del servidor Flask

**⚠️ Seguridad:**

- El archivo `.env` está en `.gitignore` y **NO se subirá a Git**
- **NUNCA** compartas tu `GOOGLE_CLIENT_SECRET` o `SECRET_KEY`
- Para generar un `SECRET_KEY` seguro, usa:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

---

## 🐳 Ejecución con Docker (Recomendado)

Docker Compose orquesta automáticamente dos servicios:

- **🐘 PostgreSQL**: Base de datos en el puerto `5432` (interno)
- **🐍 Backend Flask**: Aplicación web en el puerto `5050` (accesible desde el navegador)

### Iniciar la Aplicación

```bash
# Construir e iniciar todos los servicios en segundo plano
docker compose up -d --build

# O sin el flag -d para ver logs en tiempo real
docker compose up --build
```

#### Primera vez: Inicializar la base de datos

```bash
# Crear las tablas de la base de datos
docker exec -it backend_container python -m app.db.setup

# (Opcional) Poblar con datos de prueba
docker exec -it backend_container python -m app.db.seed
```

### Verificar el Estado

```bash
# Ver el estado de los contenedores
docker compose ps

# Ver logs del backend en tiempo real
docker compose logs -f backend

# Ver logs de la base de datos
docker compose logs -f db

# Ver todos los logs
docker compose logs -f
```

### Acceder a la Aplicación

Abre tu navegador en: **[http://localhost:5050](http://localhost:5050)**

### Comandos Útiles

```bash
# Reiniciar un servicio específico
docker compose restart backend
docker compose restart db

# Acceder a la shell del contenedor backend
docker exec -it backend_container /bin/bash

# Acceder a PostgreSQL directamente
docker exec -it postgres_container psql -U postgres -d scheduler

# Ver el uso de recursos
docker stats

# Reconstruir solo si hay cambios
docker compose up -d

# Forzar reconstrucción completa
docker compose up -d --build --force-recreate
```

### Gestión de Base de Datos

```bash
# Usar el script interactivo (Recomendado) 🎯
./db-manager.sh

# O comandos directos:

# Configuración inicial completa (primera vez)
docker exec -it backend_container python -m app.db.setup

# Resetear la base de datos (elimina todos los datos)
docker exec -it backend_container python -m app.db.reset

# Poblar con datos de prueba
docker exec -it backend_container python -m app.db.seed

# Crear tablas
docker exec -it backend_container python -m app.db.migrate

# Eliminar tablas
docker exec -it backend_container python -m app.db.drop
```

> 📚 **Documentación completa**: Ver [DATABASE.md](DATABASE.md) para guía detallada de gestión de base de datos y solución de problemas.

### Detener la Aplicación

```bash
# Detener servicios (mantiene los datos en volúmenes)
docker compose down

# Detener y eliminar volúmenes (⚠️ BORRA LA BASE DE DATOS)
docker compose down -v

# Detener y eliminar todo (contenedores, redes, volúmenes, imágenes)
docker compose down -v --rmi all
```

---

## 💻 Ejecución Local (Sin Docker)

Si prefieres ejecutar la aplicación sin Docker:

### 1. Instalar Dependencias

```bash
# Crear entorno virtual (recomendado)
python -m venv venv

# Activar entorno virtual
# En macOS/Linux:
source venv/bin/activate
# En Windows:
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar Base de Datos

Asegúrate de tener **PostgreSQL** o **MySQL** instalado y crea la base de datos:

**PostgreSQL:**

```sql
CREATE DATABASE scheduler_db;
```

**MySQL:**

```sql
CREATE DATABASE scheduler_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Configurar Variables de Entorno

Asegúrate de tener el archivo `.env` configurado con las variables de base de datos:

```bash
DB_NAME=scheduler_db
DB_USER=root
DB_PASSWORD=tu_password
DB_HOST=localhost
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret
SECRET_KEY=tu-clave-secreta
URL=http://localhost:5000
```

### 4. Inicializar Base de Datos

```bash
# Crear las tablas
python -m app.db.setup

# (Opcional) Poblar con datos de prueba
python -m app.db.seed
```

### 5. Ejecutar la Aplicación

```bash
# Modo desarrollo
python run.py

# O con Flask CLI
flask --app run.py run --debug

# Especificar host y puerto
python run.py
# O con variables de entorno:
# HOST=0.0.0.0 PORT=8000 python run.py
```

La aplicación estará disponible en: **[http://localhost:5000](http://localhost:5000)** (o el puerto que hayas configurado)

---

## 🎯 Ejemplo de Uso

### Caso de uso: Coordinar reuniones de equipo

1. **Iniciar sesión con Google**

   - Accede a la aplicación
   - Haz clic en "Iniciar sesión con Google"
   - Autoriza la aplicación

2. **Crear un grupo**

   ```
   Nombre: "Equipo de Desarrollo"
   Descripción: "Coordinación de reuniones semanales"
   ```

   - Ve a la página principal
   - Haz clic en "Crear Grupo"
   - Completa el formulario y envía

3. **Invitar miembros**

   - Abre el grupo recién creado
   - Copia el **código de invitación** (token)
   - Comparte el código con tu equipo
   - Los miembros pueden unirse usando el código

4. **Configurar categorías** (opcional)

   - Ve a "Gestionar Categorías"
   - Crea categorías como: "Frontend", "Backend", "QA"
   - Asigna categorías a cada miembro del equipo

5. **Agregar disponibilidad**

   - Cada miembro accede a "Mi Disponibilidad"
   - Selecciona días y horas disponibles:
     - Lunes: 9:00 AM - 12:00 PM
     - Miércoles: 2:00 PM - 5:00 PM
     - Viernes: 10:00 AM - 1:00 PM
   - Guarda la disponibilidad

6. **Encontrar horarios comunes**
   - El owner/admin puede ver la disponibilidad consolidada
   - La aplicación muestra automáticamente los slots donde todos están disponibles
   - Selecciona el mejor horario para la reunión

### Gestión de roles

- **Owner**: Puede eliminar el grupo, cambiar roles, gestionar miembros
- **Admin**: Puede agregar/remover miembros, gestionar disponibilidad
- **Member**: Puede ver el grupo y gestionar su propia disponibilidad

---

## 📁 Estructura del Proyecto

```
scheduler/
├── app/
│   ├── __init__.py              # Factory de la aplicación Flask
│   ├── authz.py                 # Control de acceso y autorización
│   ├── extensions.py            # Extensiones Flask (SQLAlchemy, LoginManager)
│   │
│   ├── db/                      # Scripts de gestión de base de datos
│   │   ├── __init__.py
│   │   ├── create.py            # Crear tablas
│   │   ├── drop.py              # Eliminar tablas
│   │   ├── migrate.py           # Migraciones (futuro)
│   │   ├── reset.py             # Resetear BD (drop + create)
│   │   ├── seed.py              # Datos de prueba
│   │   └── setup.py             # Configuración inicial completa
│   │
│   ├── models/                  # Modelos SQLAlchemy (ORM)
│   │   ├── __init__.py
│   │   ├── user.py              # Usuario autenticado
│   │   ├── group.py             # Grupo de coordinación
│   │   ├── group_member.py      # Relación usuario-grupo (con rol)
│   │   ├── category.py          # Categorías de miembros
│   │   ├── group_member_category.py  # Relación miembro-categoría
│   │   ├── availability.py      # Slots de disponibilidad del grupo
│   │   └── user_availability.py # Disponibilidad individual
│   │
│   ├── routes/                  # Blueprints de rutas (controladores)
│   │   ├── __init__.py
│   │   ├── auth_routes.py       # Autenticación OAuth (/auth/*)
│   │   ├── group_routes.py      # Gestión de grupos (/group/*)
│   │   ├── category_routes.py   # Gestión de categorías (/group/*/categories/*)
│   │   └── main_routes.py       # Rutas principales (/, /dashboard)
│   │
│   ├── static/                  # Archivos estáticos (CSS, JS, imágenes)
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   │
│   └── templates/               # Plantillas Jinja2 (vistas)
│       ├── base.html            # Plantilla base
│       ├── main/
│       │   └── index.html       # Página principal
│       ├── groups/
│       │   ├── index.html       # Lista de grupos
│       │   ├── create.html      # Crear grupo
│       │   ├── show.html        # Detalle del grupo
│       │   ├── members.html     # Gestión de miembros
│       │   ├── categories.html  # Gestión de categorías
│       │   ├── member_categories.html  # Asignar categorías
│       │   └── availability.html # Gestión de disponibilidad
│       └── partials/
│           ├── navbar.html      # Barra de navegación
│           ├── footer.html      # Pie de página
│           └── flash.html       # Mensajes flash
│
├── config.py                    # Configuración de la aplicación
├── run.py                       # Punto de entrada de la aplicación
├── requirements.txt             # Dependencias Python
│
├── Dockerfile                   # Imagen Docker del backend
├── docker-compose.yml           # Orquestación de servicios (backend + PostgreSQL)
├── render-build.sh              # Script de build para Render.com
├── render.yaml                  # Configuración para despliegue en Render
│
├── .env                         # Variables de entorno (⚠️ NO versionar)
├── .gitignore                   # Archivos ignorados por Git
├── client_secret.json           # Credenciales OAuth (⚠️ NO versionar)
└── README.md                    # 📖 Este archivo
```

### Componentes Clave

| Componente          | Descripción                                              |
| ------------------- | -------------------------------------------------------- |
| `app/__init__.py`   | Factory pattern para crear la aplicación Flask           |
| `app/authz.py`      | Decoradores y funciones de autorización                  |
| `app/extensions.py` | Inicialización de extensiones (SQLAlchemy, LoginManager) |
| `app/models/`       | Modelos de datos (ORM)                                   |
| `app/routes/`       | Controladores (blueprints)                               |
| `app/db/`           | Scripts CLI para gestión de BD                           |
| `config.py`         | Configuración centralizada                               |
| `run.py`            | Inicialización del servidor                              |

---

## 🗄️ Base de Datos

### Modelos y Relaciones

```
User (Usuarios)
  ↓ 1:N
GroupMember (Membresía con rol)
  ↓ N:1
Group (Grupos)
  ↓ 1:N
Availability (Slots disponibles)
  ↓ N:M
UserAvailability (Disponibilidad individual)
  ↓ N:1
User (Usuarios)

Category (Categorías)
  ↓ N:M
GroupMemberCategory
  ↓ N:1
GroupMember
```

#### Modelos Principales

| Modelo                  | Descripción                            | Campos Clave                                        |
| ----------------------- | -------------------------------------- | --------------------------------------------------- |
| **User**                | Usuarios autenticados con Google OAuth | `google_id`, `email`, `name`, `picture`             |
| **Group**               | Grupos de coordinación                 | `name`, `description`, `join_token`, `owner_id`     |
| **GroupMember**         | Relación usuario-grupo con rol         | `user_id`, `group_id`, `role` (Owner/Admin/Member)  |
| **Category**            | Categorías para clasificar miembros    | `name`, `group_id`                                  |
| **GroupMemberCategory** | Categorías asignadas a miembros        | `group_member_id`, `category_id`                    |
| **Availability**        | Slots de disponibilidad del grupo      | `group_id`, `day_of_week`, `start_time`, `end_time` |
| **UserAvailability**    | Disponibilidad individual              | `user_id`, `availability_id`, `is_available`        |

### Configuración de Conexión

La aplicación soporta tanto **PostgreSQL** (recomendado) como **MySQL**:

**Con Docker (PostgreSQL - configurado automáticamente):**

```env
DATABASE_URI=postgresql://postgres:postgres@db:5432/scheduler
```

**Ejecución Local con PostgreSQL:**

```env
DB_HOST=localhost
DB_USER=postgres
DB_PASSWORD=tu_password
DB_NAME=scheduler_db
```

**Ejecución Local con MySQL:**

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=tu_password
DB_NAME=scheduler_db
```

La aplicación detecta automáticamente qué motor usar según el `DATABASE_URI` o construye uno a partir de las variables `DB_*`.

### Scripts de Base de Datos

```bash
# Configuración completa (create + seed si es necesario)
python -m app.db.setup

# Crear tablas solamente
python -m app.db.create

# Eliminar todas las tablas
python -m app.db.drop

# Resetear (drop + create)
python -m app.db.reset

# Poblar con datos de prueba
python -m app.db.seed

# Migraciones (en desarrollo)
python -m app.db.migrate
```

---

## 🔒 Seguridad y Control de Acceso

La aplicación implementa múltiples capas de seguridad para proteger los datos y prevenir accesos no autorizados.

### Sistema de Roles

| Rol           | Permisos                                                                                                                                                              | Casos de uso      |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- |
| **Owner** 👑  | • Control total del grupo<br>• Eliminar el grupo<br>• Cambiar roles de miembros<br>• Gestionar miembros<br>• Gestionar categorías<br>• Ver y editar disponibilidad    | Creador del grupo |
| **Admin** 🛡️  | • Gestionar miembros (agregar/remover)<br>• Gestionar categorías<br>• Ver y editar disponibilidad<br>• **NO puede** eliminar el grupo<br>• **NO puede** cambiar roles | Coordinadores     |
| **Member** 👤 | • Ver información del grupo<br>• Ver miembros<br>• Gestionar su propia disponibilidad<br>• Acceso de solo lectura a categorías                                        | Participantes     |

### Funciones de Autorización (`app/authz.py`)

La aplicación usa decoradores para proteger rutas sensibles:

```python
@require_group_member(group_id)
# Asegura que el usuario pertenece al grupo

@require_group_admin_or_owner(group_id)
# Requiere rol de Admin o Owner

@require_group_owner(group_id)
# Restricción exclusiva para el Owner

safe_remove_member(group_id, user_id)
# Aplica políticas al expulsar miembros
```

### Rutas Protegidas

Todas las rutas sensibles bajo `/group/<id>/` requieren:

1. ✅ **Autenticación** (`@login_required`)
2. ✅ **Validación de pertenencia** al grupo
3. ✅ **Verificación de permisos** según el rol

### Vulnerabilidades Mitigadas

| Vulnerabilidad                              | Mitigación                                                               | Estado      |
| ------------------------------------------- | ------------------------------------------------------------------------ | ----------- |
| **IDOR** (Insecure Direct Object Reference) | Validación de pertenencia al grupo en cada request                       | ✅ Mitigado |
| **Escalación de privilegios**               | Verificación de roles antes de acciones sensibles                        | ✅ Mitigado |
| **Expulsión arbitraria de miembros**        | Políticas: Owner no puede ser expulsado, Admin no puede expulsar a Owner | ✅ Mitigado |
| **Cambio no autorizado de roles**           | Solo Owner puede modificar roles                                         | ✅ Mitigado |
| **Eliminación no autorizada de grupo**      | Solo Owner puede eliminar grupos                                         | ✅ Mitigado |
| **Acceso a disponibilidad sin membresía**   | Bloqueado con `@require_group_member`                                    | ✅ Mitigado |

### Ejemplos de Protección

**❌ Sin protección (vulnerable):**

```python
@app.route('/group/<int:group_id>')
def show_group(group_id):
    group = Group.query.get_or_404(group_id)
    return render_template('show.html', group=group)
```

→ Cualquier usuario autenticado podría acceder a cualquier grupo

**✅ Con protección (seguro):**

```python
@app.route('/group/<int:group_id>')
@login_required
@require_group_member
def show_group(group_id):
    group = Group.query.get_or_404(group_id)
    return render_template('show.html', group=group)
```

→ Solo miembros del grupo pueden acceder

### Mejores Prácticas Implementadas

- 🔐 **Autenticación OAuth 2.0** con Google (no almacenamos contraseñas)
- 🔑 **Tokens de sesión** firmados con `SECRET_KEY`
- 🚪 **Tokens de invitación únicos** para unirse a grupos
- 🕒 **Sesiones persistentes** con expiración (30 días)
- 🛡️ **Validación en backend** (no confiamos en el frontend)
- 📝 **Logs de acceso** (en desarrollo)

---

## 🔧 Solución de Problemas

### ❌ Error: "relation does not exist" (Base de Datos)

**Síntoma:** Al ejecutar la aplicación o seed, aparece el error:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "user" does not exist
```

**Causa:** Las tablas de la base de datos no han sido creadas.

**Solución:**

```bash
# Opción 1: Script interactivo (más fácil)
./db-manager.sh
# Luego selecciona opción 1 (Setup)

# Opción 2: Comando directo
docker exec -it backend_container python -m app.db.setup
```

> 📚 Ver [DATABASE.md](DATABASE.md) para más detalles sobre gestión de base de datos.

---

### ❌ Error 400: redirect_uri_mismatch (Google OAuth)

**Síntoma:** Al intentar iniciar sesión con Google, aparece un error de URI de redirección no válida.

**Causa:** La URI de redirección no coincide con la configurada en Google Cloud Console.

**Solución:**

1. Ve a [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Edita tu OAuth 2.0 Client ID
3. Asegúrate de tener estas URIs en **Authorized redirect URIs**:
   ```
   http://localhost:5050/auth/google/callback
   http://127.0.0.1:5000/auth/google/callback
   ```
4. Verifica que en tu `.env` tengas:
   ```bash
   URL=http://localhost:5050
   ```
5. Reinicia el contenedor:
   ```bash
   docker compose restart backend
   ```

---

### 🐳 El contenedor no inicia

**Síntoma:** `docker compose up` falla o el contenedor se detiene inmediatamente.

**Diagnóstico:**

```bash
# Ver logs detallados
docker compose logs backend

# Verificar estado de todos los servicios
docker compose ps
```

**Soluciones comunes:**

1. **Puerto ya en uso:**

   ```bash
   # Verificar qué proceso usa el puerto 5050
   lsof -i :5050

   # Cambiar el puerto en docker-compose.yml
   ports:
     - "8080:5000"  # Usa 8080 en lugar de 5050
   ```

2. **Variables de entorno faltantes:**

   ```bash
   # Verificar que .env existe y tiene todas las variables obligatorias
   cat .env

   # Reconstruir con variables actualizadas
   docker compose down
   docker compose up --build
   ```

3. **Problemas de construcción:**
   ```bash
   # Limpiar y reconstruir desde cero
   docker compose down -v
   docker system prune -f
   docker compose build --no-cache
   docker compose up
   ```

---

### 🗄️ Error de conexión a base de datos

**Síntoma:** `could not connect to server` o `connection refused`

**Diagnóstico:**

```bash
# Verificar estado del contenedor de PostgreSQL
docker compose ps db

# Ver logs de la base de datos
docker compose logs db
```

**Soluciones:**

1. **PostgreSQL no está listo:**

   ```bash
   # El healthcheck debe mostrar "healthy"
   docker compose ps

   # Espera unos segundos y vuelve a intentar
   docker compose restart backend
   ```

2. **Credenciales incorrectas:**

   ```bash
   # Verifica las credenciales en docker-compose.yml
   # Backend debe usar:
   DATABASE_URI: postgresql://postgres:postgres@db:5432/scheduler
   ```

3. **Base de datos no inicializada:**
   ```bash
   # Inicializar tablas
   docker exec -it backend_container python -m app.db.setup
   ```

---

### 🔑 Variables de entorno no se cargan

**Síntoma:** La aplicación no encuentra `GOOGLE_CLIENT_ID` u otras variables.

**Soluciones:**

1. **Verificar que `.env` existe:**

   ```bash
   ls -la .env
   cat .env
   ```

2. **Formato correcto:**

   ```bash
   # ✅ Correcto
   GOOGLE_CLIENT_ID=123456.apps.googleusercontent.com

   # ❌ Incorrecto (espacios extras)
   GOOGLE_CLIENT_ID = 123456.apps.googleusercontent.com
   ```

3. **Reiniciar después de cambios:**

   ```bash
   docker compose down
   docker compose up -d
   ```

4. **Variables en docker-compose.yml:**
   ```yaml
   environment:
     GOOGLE_CLIENT_ID: "${GOOGLE_CLIENT_ID}" # Lee desde .env
   ```

---

### 🚫 Error 403: Forbidden al acceder a un grupo

**Síntoma:** No puedes acceder a un grupo existente.

**Causas y soluciones:**

1. **No eres miembro del grupo:**

   - Solicita al owner/admin que te comparta el código de invitación
   - Únete usando el token en `/join/<token>`

2. **Sesión expirada:**

   ```bash
   # Cierra sesión y vuelve a autenticarte
   # La sesión dura 30 días por defecto
   ```

3. **Rol insuficiente:**
   - Verifica tu rol en "Miembros del Grupo"
   - Solo Owner/Admin pueden realizar ciertas acciones

---

### 🐛 La aplicación se comporta de forma extraña después de cambios en el código

**Solución:**

```bash
# Reconstruir sin caché
docker compose build --no-cache

# O reiniciar completamente
docker compose down -v
docker compose up --build

# Reinicializar base de datos si es necesario
docker exec -it backend_container python -m app.db.reset
docker exec -it backend_container python -m app.db.seed
```

---

### 📝 Ver logs en tiempo real

```bash
# Todos los servicios
docker compose logs -f

# Solo backend
docker compose logs -f backend

# Solo base de datos
docker compose logs -f db

# Con marcas de tiempo
docker compose logs -f --timestamps
```

---

### 🔍 Acceder a la base de datos directamente

```bash
# Conectar a PostgreSQL
docker exec -it postgres_container psql -U postgres -d scheduler

# Comandos útiles en psql:
\dt              # Listar tablas
\d+ users        # Describir tabla users
SELECT * FROM users LIMIT 5;
\q               # Salir
```

---

### 💾 Backup y Restore de la Base de Datos

**Backup:**

```bash
# Exportar base de datos
docker exec postgres_container pg_dump -U postgres scheduler > backup.sql
```

**Restore:**

```bash
# Importar base de datos
cat backup.sql | docker exec -i postgres_container psql -U postgres -d scheduler
```

---

## 🚧 Próximos Pasos

### 🔒 Mejoras de Seguridad

- [ ] **Protección CSRF** con `Flask-WTF` en formularios
- [ ] **Auditoría de acciones críticas** (tabla de logs de eventos)
- [ ] **Rotación automática** del `join_token` después de X días
- [ ] **Rate limiting** en endpoints de autenticación (prevenir brute force)
- [ ] **Validación de entrada** más estricta con `marshmallow` o `pydantic`
- [ ] **Encriptación de datos sensibles** en base de datos
- [ ] **Autenticación de dos factores** (2FA)

### ✨ Nuevas Funcionalidades

- [ ] **Sistema de notificaciones** (email/push cuando se actualiza disponibilidad)
- [ ] **Exportar disponibilidad** a Google Calendar / iCal
- [ ] **API REST pública** para integraciones de terceros
- [ ] **Dashboard de analytics** (estadísticas de uso del grupo)
- [ ] **Modo "recurring"** para disponibilidad semanal recurrente
- [ ] **Comentarios** en slots de disponibilidad
- [ ] **Votación** para seleccionar el mejor horario
- [ ] **Integración con Slack/Discord** para notificaciones
- [ ] **Búsqueda avanzada** de grupos públicos
- [ ] **Plantillas de grupos** (predefinidas por tipo de actividad)

### 🧪 Testing y Calidad

- [ ] **Tests unitarios** con `pytest` (modelos, funciones de autorización)
- [ ] **Tests de integración** (flujos completos de usuario)
- [ ] **Tests end-to-end** con `Selenium` o `Playwright`
- [ ] **Cobertura de código** >80% con `coverage.py`
- [ ] **Linting** con `pylint` / `flake8`
- [ ] **Type hints** completos con `mypy`
- [ ] **Pre-commit hooks** para validación automática

### 🚀 DevOps y Despliegue

- [ ] **CI/CD con GitHub Actions** (tests automáticos en PRs)
- [ ] **Despliegue a producción** en Render / Railway / Fly.io
- [ ] **Monitoring** con Sentry / Datadog
- [ ] **Logging centralizado** con ELK Stack o CloudWatch
- [ ] **Métricas de rendimiento** con Prometheus + Grafana
- [ ] **CDN** para archivos estáticos
- [ ] **SSL/TLS** automático con Let's Encrypt
- [ ] **Backups automáticos** de base de datos

### � Frontend y UX

- [ ] **Diseño responsive mejorado** (mobile-first)
- [ ] **Modo oscuro** / claro
- [ ] **Internacionalización (i18n)** (español, inglés, etc.)
- [ ] **PWA** (Progressive Web App) para instalación en móvil
- [ ] **Drag & drop** para gestionar disponibilidad
- [ ] **Visualización de calendario** más intuitiva
- [ ] **Onboarding** para nuevos usuarios
- [ ] **Tutorial interactivo**

### 🗄️ Base de Datos y Performance

- [ ] **Migraciones con Alembic** (en lugar de scripts manuales)
- [ ] **Caché con Redis** para consultas frecuentes
- [ ] **Índices optimizados** en queries lentas
- [ ] **Paginación** en listas de grupos/miembros
- [ ] **Soft deletes** (no eliminar datos, marcar como deleted)
- [ ] **Histórico de cambios** (versioning de disponibilidad)

---

## 👥 Contribuciones

¡Las contribuciones son bienvenidas! 🎉 Si deseas mejorar el proyecto:

### Cómo Contribuir

1. **Fork** el repositorio
2. **Crea una rama** para tu feature:
   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. **Realiza tus cambios** siguiendo las convenciones del proyecto
4. **Commit** tus cambios con mensajes descriptivos:
   ```bash
   git commit -m 'feat: Add amazing feature'
   ```
5. **Push** a tu rama:
   ```bash
   git push origin feature/AmazingFeature
   ```
6. **Abre un Pull Request** describiendo tus cambios

### Convenciones de Commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nueva funcionalidad
- `fix:` Corrección de bugs
- `docs:` Cambios en documentación
- `style:` Formato de código (sin cambios funcionales)
- `refactor:` Refactorización de código
- `test:` Agregar o corregir tests
- `chore:` Mantenimiento general

### Guías de Estilo

- **Python**: Seguir [PEP 8](https://pep8.org/)
- **Docstrings**: Usar formato Google Style
- **Type hints**: Usar en funciones públicas
- **Tests**: Escribir tests para nuevas features

### Reportar Bugs

Si encuentras un bug:

1. Verifica que no exista ya un issue similar
2. Crea un nuevo issue con:
   - Descripción clara del problema
   - Pasos para reproducir
   - Comportamiento esperado vs real
   - Screenshots si es relevante
   - Información de entorno (OS, versión de Docker, etc.)

---

## � Licencia

Este proyecto es de código abierto bajo la licencia **MIT**. Consulta el archivo [LICENSE](LICENSE) para más detalles.

---

## �📧 Contacto

**Alberto Zúñiga**

- 📧 Email: azuiga@miuandes.cl
- 💼 GitHub: [@AlbertoZuiga](https://github.com/AlbertoZuiga)
- 🔗 Repositorio: [github.com/AlbertoZuiga/scheduler](https://github.com/AlbertoZuiga/scheduler)
