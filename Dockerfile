# The urban app in a container: the API and the built frontend on one port,
# 8080, as a non-root user. See docs/deploy-digitalhub.md.
#
#   podman build -t bologna-civic-dt .
#   podman run --rm -p 8080:8080 -e CIVIC_ENGAGEMENT_SITE=piazza_xx_settembre bologna-civic-dt
#
# The core comes from GitHub, at the commit the pack pins (pyproject.toml,
# frontend/package.json).

# --- the frontend ------------------------------------------------------------------
FROM docker.io/library/node:24-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- the backend's environment ------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS backend
# git: the core is a git dependency.
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY bologna_civic_dt/ bologna_civic_dt/
RUN uv sync --frozen --no-dev --no-editable

# --- the app ------------------------------------------------------------------------
FROM docker.io/library/python:3.12-slim-bookworm
WORKDIR /app
COPY --from=backend /app/.venv .venv
COPY --from=frontend /app/frontend/dist frontend/dist
# The sites' baselines, terrain and preset scenarios (.dockerignore leaves
# out the ingestion's rasters and the local sessions).
COPY data/ data/
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    CIVIC_ENGAGEMENT_FRONTEND=/app/frontend/dist \
    CIVIC_ENGAGEMENT_STATE=/tmp/civic-engagement
# Any non-root user: nothing is written outside /tmp.
USER 1000:1000
EXPOSE 8080
CMD ["python", "-m", "civic_engagement.serve", "bologna_civic_dt.main:app"]
