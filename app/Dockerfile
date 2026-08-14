# =========================
# Base
# =========================
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Combine system package updates and cleaning
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip and install all requirements (ensure uvicorn is listed in requirements.txt)
RUN pip install --upgrade pip \
    && pip install -r requirements.txt


# =========================
# Development
# =========================
FROM base AS development

ENV ENVIRONMENT=development \
    API_PORT=8000

COPY . .

EXPOSE 8000

# Execute main.py directly for the development environment
CMD ["python", "main.py"]


# =========================
# Production
# =========================
FROM base AS production

ENV ENVIRONMENT=production \
    API_PORT=8000

COPY . .

# Setup production user security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Execute main.py directly for the production environment
CMD ["python", "main.py"]