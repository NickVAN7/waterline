# One image for the api, worker, and migrate services (build-plan.md, "Docker Compose").
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv

# The virtualenv lives outside /app, so Compose can mount the source over /app without hiding
# it. No bytecode files: they would land in the mounted source, owned by root.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

# Not root (TD-11): a user with the host's user and group IDs (`wl` passes them as HOST_UID and
# HOST_GID), so anything written into the mounted source is the developer's, not root's.
# `--non-unique`: the host's IDs may match one the image already has.
ARG HOST_UID=1000
ARG HOST_GID=1000
RUN groupadd --non-unique --gid "$HOST_GID" app \
    && useradd --non-unique --create-home --uid "$HOST_UID" --gid "$HOST_GID" app
USER app

EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
