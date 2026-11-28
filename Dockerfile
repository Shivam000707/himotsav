# Backend for the public demo (Railway, Render, anything that runs Docker).
# The frontend is hosted separately (Vercel) and calls this API.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

COPY app/backend/requirements.txt app/backend/requirements.txt
RUN pip install -r app/backend/requirements.txt

COPY app/backend app/backend
# What the demo needs at runtime: the 7 synthetic papers and the saved AI replies for them.
COPY data/synthetic/images data/synthetic/images
COPY data/synthetic/ramesh.json data/synthetic/labels.json data/synthetic/personas.json data/synthetic/
COPY data/demo_cache data/demo_cache

# Safe defaults for a public site: no live NVIDIA calls, no uploads, Ramesh ji loaded at every start.
# Override any of these in the host's variables. Do NOT put NVIDIA_API_KEY on a public site.
ENV PUBLIC_DEMO=1 \
    AUTO_SEED_DEMO=cached \
    DEMO_TODAY=2026-10-14

RUN useradd --create-home app && chown -R app:app /srv
USER app

WORKDIR /srv/app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
