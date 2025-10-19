#!/bin/bash

if ! command -v node &> /dev/null; then
    echo "Node.js no encontrado, instalando..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
fi

npm ci
npm run build:css

pip install --upgrade pip
pip install -r requirements.txt

python -m app.db.migrate

echo "Build completado"