#!/usr/bin/env python3
"""Publica el servicio en un Space de Hugging Face.

El Space es solo el entorno de ejecución: se le suben el código de la aplicación,
sus dependencias y un Dockerfile ajustado a la plataforma. La documentación de
arquitectura y las decisiones viven en GitHub, que es el repositorio de
referencia.

Por qué un directorio de despliegue aparte en lugar de publicar el repo tal cual:
Spaces exige que `README.md` lleve una cabecera YAML con la configuración del
Space, y añadirla al README del proyecto ensuciaría el documento que lee quien
revisa el trabajo.

Los secretos (`OPENAI_API_KEY`, `AGENT_API_KEY`) NO se suben: se definen en la
configuración del Space y llegan al contenedor como variables de entorno.

Uso:
    export HF_TOKEN=hf_...
    python deploy/huggingface/sync.py --space xoalejo/cv-agent
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
AQUI = Path(__file__).resolve().parent

#: Lo que sube al Space. Todo lo demás se queda fuera a propósito.
ARCHIVOS: list[tuple[Path, str]] = [
    (AQUI / "Dockerfile", "Dockerfile"),
    (AQUI / "README.md", "README.md"),
    (RAIZ / "requirements.txt", "requirements.txt"),
]


def archivos_de_codigo() -> list[tuple[Path, str]]:
    """Todos los módulos bajo `src/`, conservando la jerarquía."""
    return [
        (ruta, str(ruta.relative_to(RAIZ)))
        for ruta in sorted((RAIZ / "src").rglob("*.py"))
        if "__pycache__" not in ruta.parts
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", required=True, help="Destino, p. ej. usuario/cv-agent")
    parser.add_argument("--private", action="store_true", help="Crea el Space privado.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Muestra qué subiría, sin subirlo."
    )
    args = parser.parse_args()

    subidas = ARCHIVOS + archivos_de_codigo()

    faltantes = [str(o) for o, _ in subidas if not o.exists()]
    if faltantes:
        print("Faltan archivos:", ", ".join(faltantes))
        return 1

    print(f"Archivos a publicar en {args.space}: {len(subidas)}")
    for _, destino in subidas:
        print(f"  {destino}")

    if args.dry_run:
        print("\n(dry-run: no se subió nada)")
        return 0

    token = os.getenv("HF_TOKEN")
    if not token:
        print("\nFalta HF_TOKEN. Genera uno con permiso de escritura en")
        print("https://huggingface.co/settings/tokens y expórtalo:")
        print("    export HF_TOKEN=hf_...")
        return 2

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(
        repo_id=args.space,
        repo_type="space",
        space_sdk="docker",
        private=args.private,
        exist_ok=True,
    )

    for origen, destino in subidas:
        api.upload_file(
            path_or_fileobj=str(origen),
            path_in_repo=destino,
            repo_id=args.space,
            repo_type="space",
        )

    usuario, nombre = args.space.split("/")
    print(f"\nPublicado: https://huggingface.co/spaces/{args.space}")
    print(f"Endpoint:  https://{usuario}-{nombre}.hf.space/responses")
    print("\nDefine los secretos del Space antes de probarlo:")
    print(f"  https://huggingface.co/spaces/{args.space}/settings")
    print("  OPENAI_API_KEY y AGENT_API_KEY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
