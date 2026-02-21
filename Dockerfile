FROM python:3.11-slim

LABEL maintainer="LinkCanary"
LABEL description="CI/CD-native link checker for sitemaps"
LABEL version="0.3"

# Install system dependencies for lxml + export formats + webhooks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    curl \
    # For PDF export (weasyprint)
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Copy and install LinkCanary with export dependencies
COPY . /linkcanary
WORKDIR /linkcanary
RUN pip install --no-cache-dir -e ".[export]"

# Copy entrypoint script
COPY .github/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create output directory for artifacts
RUN mkdir -p /output

ENTRYPOINT ["/entrypoint.sh"]
