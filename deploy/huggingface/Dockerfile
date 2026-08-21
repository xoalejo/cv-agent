# Imagen para Hugging Face Spaces.
#
# Difiere de la del repositorio en dos cosas impuestas por la plataforma:
#   - Escucha en el puerto 7860, que es el que declara el Space.
#   - El usuario sin privilegios usa UID 1000, que es el que Spaces asigna al
#     proceso; con otro UID el contenedor no puede escribir en su propio HOME.
#
# El resto de decisiones se mantienen: build en dos etapas, base slim y proceso
# sin privilegios.

FROM python:3.12-slim AS builder

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 1000 appuser

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    HOME=/home/appuser

COPY --from=builder /opt/venv /opt/venv

# Solo el código de la aplicación. Ni pruebas, ni evals, ni documentos fuente.
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 7860

CMD ["uvicorn", "src.interfaces.http.app:app", "--host", "0.0.0.0", "--port", "7860"]
