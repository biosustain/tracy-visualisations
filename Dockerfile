FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY README.md pyproject.toml ./
COPY src ./src

RUN apt-get update \
    && apt-get upgrade -y \
    # procps provides `ps`, which Nextflow requires to collect task metrics.
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade pip \
    && python -m pip install .

WORKDIR /work

CMD ["tracy-vis", "--help"]
