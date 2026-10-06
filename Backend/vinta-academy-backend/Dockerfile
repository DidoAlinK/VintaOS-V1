FROM python:3.12-slim

WORKDIR /app

# System dependencies for PyMySQL/cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Flask-Migrate needs to find the app factory; Flask only auto-discovers
# app.py / wsgi.py.
ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

RUN chmod +x start.sh

EXPOSE 5000

# start.sh runs `flask db upgrade` before gunicorn, so migrations are applied
# on every deploy without needing shell access to the server.
CMD ["./start.sh"]
