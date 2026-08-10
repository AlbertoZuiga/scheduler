FROM python:3.12.11-slim

WORKDIR /proyect

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    libpq-dev \
    gcc \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./

RUN npm ci

COPY ./ ./

RUN npm run build:css \
    && pip install --no-cache-dir -r requirements.txt

# Sin --bind: gunicorn escucha en 0.0.0.0:$PORT cuando PORT está en el entorno
# (lo que inyecta Render), y en 127.0.0.1:8000 cuando no, inalcanzable desde
# fuera del contenedor. Este ENV cubre ese caso.
ENV PORT=5000

EXPOSE 5000

# Las migraciones van antes de servir: `run.py` ya no hace create_all(), así que
# sin esto el contenedor arranca contra una base sin esquema.
CMD ["sh", "-c", "python -m app.db.migrate && exec gunicorn --workers 1 --threads 4 --access-logfile - run:scheduler_app"]