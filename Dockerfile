# MongoMind — imagen de la app web (FastAPI).
#
# La app se conecta a:
#   - MongoDB Atlas (cloud) vía MONGODB_URI  (no hay Mongo local en el contenedor)
#   - Ollama en el HOST vía OLLAMA_HOST=http://host.docker.internal:11434
# Ambos se inyectan en tiempo de ejecución (docker-compose.yml / .env), no se hornean.

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

WORKDIR /app

# Dependencias primero para aprovechar la cache de capas.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código y recursos que la app necesita en runtime.
COPY src/ ./src/
COPY data/ ./data/
COPY images/ ./images/

EXPOSE 8000

# app.py lee APP_HOST/APP_PORT del entorno y arranca uvicorn.
CMD ["python", "src/web/app.py"]
