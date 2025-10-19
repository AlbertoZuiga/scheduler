FROM python:3.12

WORKDIR /proyect

RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
COPY tailwind.config.js ./

RUN npm ci

COPY ./ ./

RUN npm run build:css \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["python", "run.py"]