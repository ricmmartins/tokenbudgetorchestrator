FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir . \
    && adduser --disabled-password --gecos "" appuser

USER appuser

EXPOSE 8000

CMD ["uvicorn", "engine.main:app", "--host", "0.0.0.0", "--port", "8000"]
