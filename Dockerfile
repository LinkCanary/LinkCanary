FROM python:3.11-slim

LABEL maintainer="LinkCanary"
LABEL description="CI/CD-native link checker for sitemaps"
LABEL version="0.3"

# Install system dependencies for lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install LinkCanary
COPY . /linkcanary
WORKDIR /linkcanary
RUN pip install --no-cache-dir -e .

# Copy entrypoint script
COPY .github/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create output directory for artifacts
RUN mkdir -p /output

ENTRYPOINT ["/entrypoint.sh"]
