# -----------------------------------------------------------
# Stage 1 – build (compilation des dépendances + .mo)
# -----------------------------------------------------------
FROM python:3.12-slim AS builder
WORKDIR /app

# sys-deps pour mysqlclient + compilation .po/.mo
RUN apt-get update && apt-get install -y --no-install-recommends \
        gettext \
        gcc g++ build-essential \
        default-libmysqlclient-dev default-mysql-client \
        pkg-config libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --prefix=/install -r requirements.txt

COPY . .

# 🗣 Compile all .po files into .mo before we quit ce stage
RUN python manage.py compilemessages --settings=lyrics_slide_show.settings

# -----------------------------------------------------------
# Stage 2 – runtime (image slim ; pas de gettext)
# -----------------------------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# binaire mysql requis à l’exécution (libmysqlclient)
RUN apt-get update && apt-get install -y --no-install-recommends \
        default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# lib + code (inclut déjà les .mo compilés)
COPY --from=builder /install /usr/local
COPY --from=builder /app /app

# script helper
RUN chmod +x scripts/wait_for_db.sh

CMD ["gunicorn", "lyrics_slide_show.wsgi:application", "--bind", "0.0.0.0:8000"]
