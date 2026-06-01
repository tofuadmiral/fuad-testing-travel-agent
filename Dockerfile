FROM python:3.12-slim

# Claude Agent SDK calls the `claude` CLI as a subprocess, so we need Node + the CLI.
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . || true
COPY . .
RUN pip install --no-cache-dir -e .

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app
ENV HOME=/home/app
ENV PATH="/home/app/.local/bin:${PATH}"

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
