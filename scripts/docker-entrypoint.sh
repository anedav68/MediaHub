#!/bin/sh
# MediaHub container entrypoint.
#
# When DATA_DIR points to a persistent disk that's separate from the
# image's bundled /app/data (the standard Render setup is DATA_DIR=
# /var/mediahub), make sure the runtime sub-dirs exist and seed the
# disk from the image's bundled data on first boot. Then hand off to
# gunicorn.
#
# Kept here (not in render.yaml's dockerCommand) because Render's
# dockerCommand is passed as a single argv to the container's exec
# form, which the shell then can't parse — see the May 2026 deploy
# log where "sh: 1: mkdir -p ... timeout 300: not found".
set -e

: "${PORT:=5000}"

if [ -n "$DATA_DIR" ] && [ "$DATA_DIR" != "/app/data" ]; then
  mkdir -p "$DATA_DIR" \
           "${RUNS_DIR:-$DATA_DIR/runs_v4}" \
           "${UPLOADS_DIR:-$DATA_DIR/uploads_v4}"
  # -n = don't overwrite existing files (idempotent on every boot).
  cp -rn /app/data/. "$DATA_DIR/" 2>/dev/null || true
fi

# Gunicorn — Phase 1.5 hardened for Render starter (512 MB RAM).
#
# IMPORTANT: keep this exec line in sync with the comments below and
# the Procfile. A merge from main in May 2026 silently dropped
# --worker-tmp-dir/--access-log* and bumped max-requests 200→800; the
# result was the "Worker was sent SIGTERM! / container restarts ~40
# minutes later" pattern the user reported. The flags ARE the fix —
# don't strip them again.
#
# Why these flags:
#   --workers 1         Single worker on 512 MB. Multi-worker on the
#                       starter plan OOM-kills almost immediately.
#   --threads 4         gthread workers share memory across threads,
#                       so 4 concurrent requests share one process.
#   --timeout 300       Pipeline runs can take 60s+; cap at 5 min so a
#                       wedged request doesn't hold a thread forever.
#   --graceful-timeout 30  Give in-flight requests 30s to finish before
#                       SIGKILL. Matches Render's own SIGTERM→SIGKILL
#                       grace window; longer values just delay the
#                       restart without saving requests.
#   --max-requests 200 --max-requests-jitter 50
#                       Recycle each worker after ~200-250 requests.
#                       Mitigates slow memory creep (Playwright /
#                       Pillow / SQLite buffer pool) so RSS doesn't
#                       cross Render's plan ceiling and trigger a
#                       container-level SIGTERM.
#   --worker-tmp-dir /dev/shm
#                       Render's disk I/O is slow; keep the worker
#                       heartbeat file in tmpfs to avoid spurious
#                       worker timeouts when the disk is busy
#                       (Playwright temp files, pack writes, etc.).
#   --access-logfile -  Log requests to stdout so Render captures them.
#                       Without this, request traffic is invisible and
#                       you can't correlate restarts with actual load.
#   --access-logformat ...
#                       Include request time so a single hung route
#                       shows up in logs.
exec gunicorn mediahub.web:app \
  --bind "0.0.0.0:${PORT}" \
  --workers 1 \
  --threads 4 \
  --timeout 300 \
  --graceful-timeout 30 \
  --max-requests 200 \
  --max-requests-jitter 50 \
  --worker-tmp-dir /dev/shm \
  --access-logfile - \
  --access-logformat '%(h)s "%(r)s" %(s)s %(b)s %(M)sms "%(f)s"'
