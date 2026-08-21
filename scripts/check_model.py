#!/usr/bin/env python3
"""Verifica contra la API que el modelo configurado existe y responde.

Sirve para no descubrir en la primera petición real que el identificador del
modelo estaba mal escrito o que la cuenta no tiene acceso a ese nivel. Los IDs de
modelo cambian con cada generación, y confiar en lo que dice un blog es una forma
barata de romper producción.

Uso:
    python scripts/check_model.py                  # verifica el de .env
    python scripts/check_model.py --list           # lista los disponibles
    python scripts/check_model.py --probe gpt-5.6-luna gpt-5.6-terra
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402


def _client():
    from openai import OpenAI

    settings = get_settings()
    if not settings.openai_api_key:
        print("ERROR: falta OPENAI_API_KEY. Ponla en .env antes de continuar.")
        raise SystemExit(2)
    return OpenAI(api_key=settings.openai_api_key, timeout=45.0), settings


def list_models(prefix: str | None = None) -> None:
    client, _ = _client()
    ids = sorted(m.id for m in client.models.list().data)
    if prefix:
        ids = [i for i in ids if i.startswith(prefix)]

    print(f"{len(ids)} modelos disponibles para esta cuenta:\n")
    for model_id in ids:
        print(f"  {model_id}")


def probe(model_id: str) -> bool:
    """Hace una llamada mínima real: existir no siempre implica tener acceso."""
    client, _ = _client()
    try:
        response = client.responses.create(
            model=model_id,
            input="Responde solo con la palabra: listo",
            store=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  [FALLA] {model_id}: {type(exc).__name__}: {str(exc)[:140]}")
        return False

    usage = response.usage
    tokens = getattr(usage, "total_tokens", 0) if usage else 0
    texto = (response.output_text or "").strip()[:40]
    print(f"  [OK]    {model_id}: responde «{texto}» ({tokens} tokens)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="Lista los modelos.")
    parser.add_argument("--prefix", help="Filtra la lista por prefijo, p. ej. 'gpt-5'.")
    parser.add_argument("--probe", nargs="*", help="Prueba estos modelos con una llamada.")
    args = parser.parse_args()

    if args.list:
        list_models(args.prefix)
        return 0

    targets = args.probe if args.probe else [get_settings().openai_model]
    print("Probando modelos con una llamada real:\n")
    resultados = {model_id: probe(model_id) for model_id in targets}

    fallidos = [m for m, ok in resultados.items() if not ok]
    print()
    if fallidos:
        print(f"No disponibles: {', '.join(fallidos)}")
        return 1
    print("Todos los modelos probados están disponibles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
