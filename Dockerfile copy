FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ Ajout des paquets nécessaires à mysqlclient
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    libssl-dev \
    default-mysql-client \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN chmod +x scripts/wait_for_db.sh

CMD ["gunicorn", "lyrics_slide_show.wsgi:application", "--bind", "0.0.0.0:8000"]
