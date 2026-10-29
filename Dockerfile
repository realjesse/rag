FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app \
        --no-create-home --shell /usr/sbin/nologin app

USER app

EXPOSE 8000

CMD ["/app/.venv/bin/fastapi", "run", "src/backend/main.py", "--port", "8000"]