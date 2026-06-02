FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.6.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen

COPY . /app

EXPOSE 8000 8001
