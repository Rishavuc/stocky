FROM node:22-alpine AS frontend
WORKDIR /ui
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
FROM python:3.12-slim AS pythonbase
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && rm -rf /var/lib/apt/lists/*
FROM pythonbase AS trainer
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend OMP_NUM_THREADS=2 LOKY_MAX_CPU_COUNT=2
COPY backend/ backend/
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 && pip install --no-cache-dir -r backend/requirements-training.txt
COPY data/ data/
COPY scripts/ scripts/
RUN DATABASE_URL=sqlite:////app/build_models.db python -m app.research
FROM pythonbase
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend APP_HOST=0.0.0.0
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY data/ data/
COPY scripts/ scripts/
COPY --from=trainer /app/models models/
COPY --from=frontend /ui/dist frontend/dist
RUN useradd --create-home eye && mkdir -p runtime && chown -R eye:eye /app
USER eye
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["python", "backend/run.py"]
