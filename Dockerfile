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

EXPOSE 5000

CMD ["python", "run.py"]