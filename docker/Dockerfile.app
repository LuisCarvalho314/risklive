FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY config ./config
COPY prompts ./prompts

RUN mkdir -p /app/results /app/logs /app/runtime \
 && useradd -m -u 10001 risklive \
 && chown -R risklive:risklive /app

USER risklive

EXPOSE 5001

CMD ["python", "-m", "app.server"]
