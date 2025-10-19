#!/bin/bash

# Scheduler Database Management Script
# Ayuda para gestionar la base de datos de forma fácil

set -e

CONTAINER_NAME="backend_container"

echo "🗄️  Scheduler - Gestión de Base de Datos"
echo "========================================"
echo ""

# Verificar que Docker está corriendo
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Error: Docker no está corriendo"
    exit 1
fi

# Verificar que el contenedor existe
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ Error: El contenedor ${CONTAINER_NAME} no existe"
    echo "   Ejecuta: docker compose up -d --build"
    exit 1
fi

# Verificar que el contenedor está corriendo
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "⚠️  El contenedor no está corriendo. Iniciando..."
    docker compose up -d
    echo "⏳ Esperando a que el contenedor esté listo..."
    sleep 5
fi

# Función para mostrar el menú
show_menu() {
    echo "Selecciona una opción:"
    echo ""
    echo "  1) 🏗️  Setup - Configuración inicial (crear BD + tablas + datos)"
    echo "  2) 🔨 Create - Solo crear tablas (sin datos)"
    echo "  3) 🌱 Seed - Solo poblar con datos de prueba"
    echo "  4) 🔄 Reset - Eliminar todo y recrear con datos"
    echo "  5) 🗑️  Drop - Eliminar todas las tablas"
    echo "  6) 📊 Status - Ver estado de la base de datos"
    echo "  7) 🚪 Exit - Salir"
    echo ""
    read -p "Opción: " choice
    echo ""
}

# Función para ejecutar comandos en el contenedor
run_db_command() {
    docker exec -it ${CONTAINER_NAME} python -m app.db.$1
}

# Función para mostrar el estado
show_status() {
    echo "📊 Estado de la Base de Datos:"
    echo "========================================"
    docker exec -it ${CONTAINER_NAME} python -c "
from app import scheduler_app
from app.extensions import scheduler_db
from app.models import User, Group, GroupMember

with scheduler_app.app_context():
    try:
        users = User.query.count()
        groups = Group.query.count()
        members = GroupMember.query.count()
        
        print(f'✅ Conexión exitosa')
        print(f'')
        print(f'👥 Usuarios: {users}')
        print(f'📁 Grupos: {groups}')
        print(f'🤝 Membresías: {members}')
    except Exception as e:
        print(f'❌ Error: {str(e)}')
        print(f'   La base de datos probablemente no está inicializada.')
        print(f'   Ejecuta la opción 1 (Setup) para configurarla.')
"
}

# Loop principal
while true; do
    show_menu
    
    case $choice in
        1)
            echo "🏗️  Ejecutando Setup Completo..."
            run_db_command "setup"
            echo "✅ Setup completado!"
            ;;
        2)
            echo "🔨 Creando tablas..."
            run_db_command "migrate"
            echo "✅ Tablas creadas!"
            ;;
        3)
            echo "🌱 Poblando base de datos..."
            run_db_command "seed"
            echo "✅ Datos creados!"
            ;;
        4)
            echo "⚠️  ADVERTENCIA: Esto eliminará TODOS los datos existentes"
            read -p "¿Estás seguro? (escribe 'si' para confirmar): " confirm
            if [ "$confirm" = "si" ] || [ "$confirm" = "SI" ]; then
                echo "🔄 Reseteando base de datos..."
                run_db_command "reset"
                echo "🌱 Poblando con datos de prueba..."
                run_db_command "seed"
                echo "✅ Base de datos reseteada!"
            else
                echo "❌ Operación cancelada"
            fi
            ;;
        5)
            echo "⚠️  ADVERTENCIA: Esto eliminará TODAS las tablas y datos"
            read -p "¿Estás seguro? (escribe 'si' para confirmar): " confirm
            if [ "$confirm" = "si" ] || [ "$confirm" = "SI" ]; then
                echo "🗑️  Eliminando tablas..."
                run_db_command "drop"
                echo "✅ Tablas eliminadas!"
            else
                echo "❌ Operación cancelada"
            fi
            ;;
        6)
            show_status
            ;;
        7)
            echo "👋 ¡Hasta luego!"
            exit 0
            ;;
        *)
            echo "❌ Opción inválida. Por favor selecciona 1-7."
            ;;
    esac
    
    echo ""
    read -p "Presiona Enter para continuar..."
    echo ""
    echo ""
done
