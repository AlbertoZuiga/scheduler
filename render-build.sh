pip install --upgrade pip
pip install -r requirements.txt

python -m app.db.migrate

echo "Build completado"