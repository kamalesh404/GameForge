FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml setup.py README.md ./
COPY src ./src

RUN pip install --upgrade pip && pip install .

FROM base AS test

COPY tests ./tests
RUN pip install pytest pytest-cov && python -m pytest

FROM base AS runtime

EXPOSE 7777/tcp
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import socket;s=socket.socket();s.settimeout(2);s.connect(('localhost',7777));s.close()" || exit 1

CMD ["python", "-c", "from src.network.server import GameServer; s = GameServer(port=7777); s.start(); import time; time.sleep(3600)"]
