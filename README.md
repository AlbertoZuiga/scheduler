# Scheduler

Aplicación Flask para gestión de grupos y disponibilidad horaria con autenticación OAuth 2.0 de Google.

## 📋 Índice

- [Características](#-características)
- [Requisitos](#-requisitos)
- [Instalación y Configuración](#-instalación-y-configuración)
  - [1. Clonar el Repositorio](#1-clonar-el-repositorio)
  - [2. Configurar Google OAuth](#2-configurar-google-oauth)
  - [3. Variables de Entorno](#3-variables-de-entorno)
- [Ejecución con Docker (Recomendado)](#-ejecución-con-docker-recomendado)
  - [Iniciar la Aplicación](#iniciar-la-aplicación)
  - [Verificar el Estado](#verificar-el-estado)
  - [Acceder a la Aplicación](#acceder-a-la-aplicación)
  - [Detener la Aplicación](#detener-la-aplicación)
- [Ejecución Local (Sin Docker)](#-ejecución-local-sin-docker)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Base de Datos](#-base-de-datos)
- [Seguridad y Control de Acceso](#-seguridad-y-control-de-acceso)
- [Solución de Problemas](#-solución-de-problemas)
- [Próximos Pasos](#-próximos-pasos)

## 🚀 Características

- ✅ Autenticación con Google OAuth 2.0
- ✅ Gestión de grupos y miembros
- ✅ Sistema de disponibilidad horaria
- ✅ Control de acceso basado en roles (Owner, Admin, Member)
- ✅ Prevención de IDOR y escalación de privilegios
- ✅ Dockerizado con PostgreSQL
- ✅ Interface web responsiva

## 📦 Requisitos

### Para ejecutar con Docker:

- Docker Desktop (macOS/Windows) o Docker Engine + Docker Compose (Linux)
- Git

### Para ejecutar localmente:

- Python 3.11+
- PostgreSQL o MySQL
- Git

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
# Base de datos (para ejecución local sin Docker)
DB_NAME=scheduler_db
DB_USER=root
DB_PASSWORD=tu_password
DB_HOST=localhost

# Google OAuth (OBLIGATORIO)
GOOGLE_CLIENT_ID=tu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=tu-client-secret

# URL de la aplicación
URL=http://localhost:5050

# Seguridad
SECRET_KEY=tu-clave-secreta-super-segura

# Modo debug (opcional)
DEBUG=True
```

**⚠️ Importante:**

- Reemplaza `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` con tus credenciales de Google
- Para producción, cambia `SECRET_KEY` por una clave segura
- El archivo `.env` está en `.gitignore` y no se subirá a Git

## 🐳 Ejecución con Docker (Recomendado)

Docker Compose orquesta dos servicios:

- **PostgreSQL**: Base de datos en el puerto 5432 (interno)
- **Backend Flask**: Aplicación web en el puerto 5050

### Iniciar la Aplicación

```bash
# Construir e iniciar todos los servicios
docker compose up --build -d

# O sin el flag -d para ver logs en tiempo real
docker compose up --build
```

### Verificar el Estado

```bash
# Ver el estado de los contenedores
docker compose ps

# Ver logs del backend
docker compose logs -f backend

# Ver logs de la base de datos
docker compose logs -f db

# Ver todos los logs
docker compose logs -f
```

### Acceder a la Aplicación

Abre tu navegador en: **http://localhost:5050**

### Detener la Aplicación

```bash
# Detener servicios (mantiene los datos)
docker compose down

# Detener y eliminar volúmenes (borra la base de datos)
docker compose down -v
```

## 💻 Ejecución Local (Sin Docker)

Si prefieres ejecutar la aplicación sin Docker:

### 1. Instalar Dependencias

```bash
# Crear entorno virtual (opcional pero recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar Base de Datos

Asegúrate de tener PostgreSQL o MySQL instalado y crea la base de datos:

```sql
-- PostgreSQL
CREATE DATABASE scheduler_db;

-- MySQL
CREATE DATABASE scheduler_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Configurar Variables de Entorno

Asegúrate de tener el archivo `.env` configurado (ver sección anterior).

### 4. Inicializar Base de Datos

```bash
# Ejecutar migraciones
python -m app.db.setup
```

### 5. Ejecutar la Aplicación

```bash
# Modo desarrollo
python run.py

# O con Flask CLI
flask --app run.py run --debug
```

La aplicación estará disponible en: **http://localhost:5000**

## 📁 Estructura del Proyecto

```
scheduler/
├── app/
│   ├── __init__.py              # Factory de la aplicación Flask
│   ├── authz.py                 # Control de acceso y autorización
│   ├── extensions.py            # Extensiones Flask (SQLAlchemy, LoginManager)
│   ├── db/                      # Scripts de base de datos
│   │   ├── create.py
│   │   ├── migrate.py
│   │   ├── seed.py
│   │   └── setup.py
│   ├── models/                  # Modelos SQLAlchemy
│   │   ├── user.py
│   │   ├── group.py
│   │   ├── group_member.py
│   │   ├── availability.py
│   │   └── user_availability.py
│   ├── routes/                  # Blueprints de rutas
│   │   ├── auth_routes.py       # Autenticación OAuth
│   │   ├── group_routes.py      # Gestión de grupos
│   │   └── main_routes.py       # Rutas principales
│   ├── static/                  # Archivos estáticos (CSS, JS, imágenes)
│   └── templates/               # Plantillas Jinja2
├── config.py                    # Configuración de la aplicación
├── run.py                       # Punto de entrada de la aplicación
├── requirements.txt             # Dependencias Python
├── Dockerfile                   # Imagen Docker del backend
├── docker-compose.yml           # Orquestación de servicios
├── .env                         # Variables de entorno (NO versionar)
├── client_secret.json           # Credenciales OAuth (NO versionar)
└── README.md                    # Este archivo
```

## 🗄️ Base de Datos

### Modelos Principales

- **User**: Usuarios autenticados con Google OAuth
- **Group**: Grupos creados por usuarios
- **GroupMember**: Relación usuarios-grupos con roles (Owner, Admin, Member)
- **Availability**: Slots de disponibilidad horaria
- **UserAvailability**: Disponibilidad individual de usuarios

### Configuración de Conexión

La aplicación soporta tanto PostgreSQL como MySQL:

**Con Docker (PostgreSQL):**

```
DATABASE_URI=postgresql://postgres:postgres@db:5432/scheduler
```

**Local (MySQL):**

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=tu_password
DB_NAME=scheduler_db
```

La aplicación detecta automáticamente qué variable usar según el entorno.

## 🔒 Seguridad y Control de Acceso

Se han implementado controles de seguridad para prevenir acceso no autorizado (IDOR) y escalación de privilegios:

### Sistema de Roles

- **Owner (Propietario)**: Control total del grupo, puede eliminar el grupo y cambiar roles
- **Admin (Administrador)**: Puede gestionar miembros pero no eliminar el grupo ni cambiar roles
- **Member (Miembro)**: Acceso de lectura y puede gestionar su propia disponibilidad

### Funciones de Autorización (`app/authz.py`)

- `require_group_member(group_id)`: Asegura que el usuario pertenece al grupo
- `require_group_admin_or_owner(group_id)`: Para acciones administrativas
- `require_group_owner(group_id)`: Restringe operaciones críticas al propietario
- `safe_remove_member(group_id, user_id)`: Aplica políticas al expulsar miembros

### Rutas Protegidas

Todas las rutas sensibles bajo `/group/` requieren:

- Autenticación (`@login_required`)
- Validación de pertenencia al grupo
- Verificación de permisos según el rol

### Riesgos Mitigados

1. ✅ Acceso directo a `/group/<id>` sin pertenencia (IDOR) → Retorna 403
2. ✅ Expulsión arbitraria de miembros → Restringido a owner/admin con reglas
3. ✅ Cambio de roles por no propietarios → Solo owner puede modificar roles
4. ✅ Eliminación de grupo por no propietario → Solo owner
5. ✅ Visualización de disponibilidad sin ser miembro → Bloqueado

## 🔧 Solución de Problemas

### Error 400: redirect_uri_mismatch (Google OAuth)

**Problema:** La URI de redirección no coincide con la configurada en Google Cloud Console.

**Solución:**

1. Verifica que en Google Cloud Console tengas configurado: `http://localhost:5050/auth/google/callback`
2. Asegúrate de que la variable `URL` en `docker-compose.yml` sea: `http://localhost:5050`
3. Reinicia el contenedor: `docker compose restart backend`

### El contenedor no inicia

```bash
# Ver logs detallados
docker compose logs backend

# Verificar que PostgreSQL esté saludable
docker compose ps

# Reiniciar todos los servicios
docker compose down
docker compose up --build
```

### Error de conexión a base de datos

Verifica que el servicio `db` esté corriendo:

```bash
docker compose ps db
```

El healthcheck debe mostrar "healthy". Si no, revisa los logs:

```bash
docker compose logs db
```

### Variables de entorno no se cargan

Asegúrate de que:

1. El archivo `.env` esté en la raíz del proyecto
2. Las variables estén en formato `KEY=value` sin espacios extras
3. Reiniciaste el contenedor después de modificar `.env`

## 🚧 Próximos Pasos

### Mejoras de Seguridad

- [ ] Implementar protección CSRF con `Flask-WTF`
- [ ] Registrar auditoría de acciones críticas en tabla de logs
- [ ] Rotación configurable del `join_token`
- [ ] Rate limiting en endpoints de autenticación

### Funcionalidades

- [ ] Sistema de notificaciones
- [ ] Exportar disponibilidad a Google Calendar
- [ ] API REST para integraciones
- [ ] Tests unitarios y de integración

### DevOps

- [ ] CI/CD con GitHub Actions
- [ ] Despliegue a producción (Render, Railway, etc.)
- [ ] Monitoring y logging centralizado

---

## 📝 Licencia

Este proyecto es de código abierto. Consulta el archivo LICENSE para más detalles.

## 👥 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📧 Contacto

Alberto Zúñiga - azuiga@miuandes.cl

Repositorio: [https://github.com/AlbertoZuiga/scheduler](https://github.com/AlbertoZuiga/scheduler)
