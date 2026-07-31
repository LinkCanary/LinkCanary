# Stage 1: Build the Go crawl-engine binary
FROM golang:1.23-alpine AS go-builder

WORKDIR /build
COPY crawl-engine/ .
RUN CGO_ENABLED=0 go build -o crawl-engine -ldflags="-s -w" .

# Stage 2: Python runtime with Go binary
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

# Copy the Go crawl-engine binary from the builder stage
COPY --from=go-builder /build/crawl-engine /usr/local/bin/linkcanary-crawl-engine
RUN chmod +x /usr/local/bin/linkcanary-crawl-engine

# Copy entrypoint script
COPY .github/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create output directory for artifacts
RUN mkdir -p /output

ENTRYPOINT ["/entrypoint.sh"]
