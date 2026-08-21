# Build en dos etapas: las herramientas de compilación no llegan a la imagen
# final, que queda con lo mínimo para ejecutar el servicio.
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM python:3.12-slim AS runtime

# Usuario sin privilegios: si alguien logra ejecutar código en el contenedor, no
# lo hace como root.
RUN groupadd --system --gid 1001 appuser && \
    useradd --system --uid 1001 --gid appuser --create-home appuser

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

COPY --from=builder /opt/venv /opt/venv

# Solo el código de la aplicación. Ni pruebas, ni evals, ni los PDFs del CV
# (que además están fuera del control de versiones).
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8080

# Sonda de salud del propio contenedor, sin depender de curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "src.interfaces.http.app:app", "--host", "0.0.0.0", "--port", "8080"]
