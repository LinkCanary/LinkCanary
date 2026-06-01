# Production image for the LinkCanary UI (API + Celery worker share this image).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --upgrade pip && pip install -e ".[prod]"

EXPOSE 3000

# Default: run the API. The worker service overrides this command in compose.
CMD ["uvicorn", "linkcanary_ui.main:app", "--host", "0.0.0.0", "--port", "3000"]
