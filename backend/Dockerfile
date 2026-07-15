FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt \
    && pip install --no-cache-dir gunicorn

COPY backend /app/backend
COPY ml /app/ml

RUN set -eux; \
    if [ -d /app/ml/serving_packages ]; then \
      for package in /app/ml/serving_packages/*.tar.gz; do \
        [ -f "$package" ] || continue; \
        tmp_dir="$(mktemp -d)"; \
        tar -xzf "$package" -C "$tmp_dir"; \
        package_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"; \
        mkdir -p /app/ml/models /app/ml/configs /app/ml/data/processed /app/ml/serving_packages/extracted; \
        if [ -d "$package_dir/models" ]; then cp -a "$package_dir/models/." /app/ml/models/; fi; \
        if [ -d "$package_dir/configs" ]; then cp -a "$package_dir/configs/." /app/ml/configs/; fi; \
        if [ -d "$package_dir/metadata" ]; then cp -a "$package_dir/metadata/"*.metrics.json /app/ml/models/ 2>/dev/null || true; fi; \
        if [ -d "$package_dir/metadata" ]; then cp -a "$package_dir/metadata/"*_summary.json /app/ml/data/processed/ 2>/dev/null || true; fi; \
        if [ -d "$package_dir/predictions" ]; then cp -a "$package_dir/predictions/"*.csv /app/ml/data/processed/ 2>/dev/null || true; fi; \
        cp -a "$package_dir" /app/ml/serving_packages/extracted/; \
        rm -rf "$tmp_dir"; \
      done; \
    fi

WORKDIR /app/backend

EXPOSE 5050
