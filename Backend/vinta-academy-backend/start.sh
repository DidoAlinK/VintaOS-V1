#!/usr/bin/env bash
#
# Production entry point for the Vinta School OS backend.
#
# Replaces `python run.py`, which starts Flask's *development* server
# (single-threaded, not for real traffic, and binds to 127.0.0.1 so the host
# cannot reach it).
#
set -e

# Flask-Migrate's CLI needs to know how to build the app. Flask only
# auto-discovers app.py / wsgi.py, and ours is run.py.
export FLASK_APP=run.py
export FLASK_ENV="${FLASK_ENV:-production}"

echo "==> Applying database migrations"
flask db upgrade

echo "==> Starting gunicorn on port ${PORT:-5000}"

# --workers 1 is deliberate, NOT a placeholder.
#
# app/tasks/scheduler.py starts an APScheduler BackgroundScheduler inside each
# process. With 2+ workers every worker runs its own copy of every cron job, so
# nightly billing and notification jobs would fire 2x, 3x, ... Concurrency is
# handled with threads instead.
exec gunicorn \
  --workers 1 \
  --threads 4 \
  --timeout 120 \
  --bind "0.0.0.0:${PORT:-5000}" \
  --access-logfile - \
  --error-logfile - \
  run:app
