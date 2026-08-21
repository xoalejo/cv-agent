"""Punto de entrada para el runtime de Python de Vercel.

Vercel busca un objeto ASGI llamado `app` en este módulo y lo sirve como
función. Toda la aplicación es la misma que corre en local o en un contenedor:
este archivo no añade lógica, solo la expone donde la plataforma la espera.

El enrutado de todas las rutas hacia aquí se declara en `vercel.json`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# En el empaquetado de Vercel este archivo vive en `api/`, y `src/` queda en la
# raíz del proyecto. Sin esta línea el import fallaría en la plataforma aunque
# funcione en local.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.interfaces.http.app import app  # noqa: E402

__all__ = ["app"]
