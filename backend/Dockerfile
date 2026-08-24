# RepoRevive backend — production image.
# Uses Python 3.12-slim (code targets 3.11+). To enable the AI layer, also
# install requirements-ai.txt and set GEMINI_API_KEY at runtime.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install AI deps too so Gemini chat/narration/embeddings work in production.
# For a lean, deterministic-only image, remove requirements-ai.txt below.
COPY requirements.txt requirements-ai.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ai.txt

COPY app ./app

EXPOSE 8000

# Respect the platform-provided $PORT (Render/Railway/Fly), default to 8000.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
