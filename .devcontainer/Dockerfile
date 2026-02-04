FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ENV PYTHONUNBUFFERED=1

# Install Node.js 24 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y nodejs

# Install MySQL client libraries and build tools needed for mysqlclient package
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy wait-for-it and start scripts for WAITFOR environment variable support
COPY .docker /.docker
RUN chmod +x /.docker/wait-for-it.sh /.docker/start

# Note: Python dependencies will be installed after container creation via postCreateCommand
# because requirements.txt contains "-e ." which requires the project code to be mounted
