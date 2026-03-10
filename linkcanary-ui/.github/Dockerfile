# Dockerfile for LinkCanary GitHub Action
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /linkcanary

# Copy entire repository
COPY . .

# Install the package
RUN pip install --upgrade pip && \
    pip install -e .

# Copy entrypoint script
COPY .github/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]