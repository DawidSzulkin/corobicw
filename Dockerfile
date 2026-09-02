FROM python:3.11-slim

# Wymuszenie kodowania
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalacja zależności systemowych
RUN apt-get update && apt-get install -y --no-install-recommends gcc libsqlite3-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Katalogi dla wolumenów (aby nie uprawnienia nie kolidowały)
RUN mkdir -p /app/data /app/public/assets/thumbnails /app/config

CMD ["python", "-u", "src/main.py", "--city", "bielsko_biala"]
