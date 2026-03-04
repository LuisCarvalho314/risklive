FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PATH="/root/.local/bin:/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock ./
COPY README.md ./README.md
COPY src ./src
COPY config ./config
COPY prompts ./prompts

RUN uv sync --frozen --no-dev

RUN useradd -m -u 10001 risklive \
 && mkdir -p /app/results /app/logs /app/runtime \
 && chown -R risklive:risklive /app/results /app/logs /app/runtime

USER risklive

EXPOSE 5001

CMD ["python", "-m", "app.server"]