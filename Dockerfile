# syntax=docker/dockerfile:1.6
#
# CPU image for the building floor estimation pipeline.
# Build: docker build -t bfe:latest .
#
# For CUDA inference, base the image on nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
# instead and install Python 3.11 via apt; dependencies are otherwise identical.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BFE_LOG_LEVEL=INFO

# System libraries required by opencv-python-headless, geopandas/shapely/pyproj
# (GDAL/GEOS/PROJ are pulled in as wheels, but a few shared libraries help).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgl1 \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first to maximise layer cache reuse.
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --upgrade pip \
    && pip install .

# Standard mount points: users bind-mount their own data/models/outputs.
RUN mkdir -p /app/data /app/models /app/outputs /app/configs
VOLUME ["/app/data", "/app/models", "/app/outputs"]

# Non-root by default.
RUN useradd -u 1000 -m bfe
USER bfe

ENTRYPOINT ["bfe"]
CMD ["--help"]
