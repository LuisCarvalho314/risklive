FROM ghcr.io/astral-sh/uv:0.9.15 AS uv

# Source hashes match the pinned SECA-Light submodule commit.
FROM rust:1.92.0-bookworm@sha256:e90e846de4124376164ddfbaab4b0774c7bdeef5e738866295e5a90a34a307a2 AS seca-builder
WORKDIR /build/seca
COPY experimental/Cargo.toml ./Cargo.toml
COPY experimental/crates ./crates
COPY docker/seca/SOURCE.sha256 /tmp/SOURCE.sha256
RUN sha256sum --check /tmp/SOURCE.sha256
COPY docker/seca/Cargo.lock ./Cargo.lock
RUN cargo test --release --locked -p realtime-seca-core -p realtime-seca-cli --jobs 2 \
 && cargo build --release --locked -p realtime-seca-cli --jobs 2 \
 && install -m 0755 target/release/realtime-seca-cli /usr/local/bin/realtime-seca-cli

FROM python:3.11-slim

LABEL org.risklive.seca.source-revision="a03e2ba3385d328a10eacbf584c57cddc6f40a62" \
    org.risklive.seca.toolchain="1.92.0"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/London \
    RISKLIVE_SECA_CLI=/usr/local/bin/realtime-seca-cli \
    PYTHONPATH=/app/src \
    PATH="/app/.venv/bin:${PATH}" \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv
COPY --from=seca-builder /usr/local/bin/realtime-seca-cli /usr/local/bin/realtime-seca-cli

COPY pyproject.toml uv.lock ./
COPY README.md ./README.md
COPY src ./src
COPY config ./config
COPY prompts ./prompts

RUN uv sync --frozen --no-dev --no-editable

RUN groupadd -g 10001 risklive \
 && useradd -m -u 10001 -g 10001 risklive \
 && mkdir -p /app/results /app/logs /app/runtime \
 && chown -R risklive:risklive /app/results /app/logs /app/runtime

USER risklive

CMD ["gunicorn", "app.wsgi:app", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "0", "--access-logfile", "-", "--error-logfile", "-"]
