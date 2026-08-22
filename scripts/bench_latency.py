#!/usr/bin/env python3
"""Mide la latencia percibida del agente bajo distintas configuraciones.

La métrica que importa en una conversación no es el tiempo total sino el
**tiempo hasta el primer texto** (TTFT): es lo que separa una respuesta que se
siente inmediata de una que parece colgada. El resto llega mientras se lee.

Se mide contra la API directamente, sin pasar por el servicio, para aislar el
efecto de cada variable y no mezclarlo con el arranque en frío del hosting.

Uso:
    python scripts/bench_latency.py
    python scripts/bench_latency.py --repeticiones 3
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.application.prompt import build_instructions  # noqa: E402
from src.application.tool_registry import TOOL_DEFINITIONS  # noqa: E402
from src.config import get_settings  # noqa: E402
from src.infrastructure.profile_data import PROFILE  # noqa: E402

PREGUNTAS = [
    "¿Cuántos años de experiencia tiene?",
    "¿En qué empresas ha trabajado con RAG?",
    "Cuéntame de su experiencia en Arbomex",
]


def medir(cliente, *, modelo, instrucciones, pregunta, tools, effort):
    """Devuelve (ttft, total, hubo_llamada_a_herramienta, caracteres)."""
    inicio = time.perf_counter()
    ttft = None
    texto = []
    tool_call = False

    stream = cliente.responses.create(
        model=modelo,
        instructions=instrucciones,
        input=[{"role": "user", "content": [{"type": "input_text", "text": pregunta}]}],
        tools=tools,
        store=False,
        reasoning={"effort": effort},
        stream=True,
    )
    for evento in stream:
        tipo = getattr(evento, "type", "")
        if tipo == "response.output_text.delta":
            if ttft is None:
                ttft = time.perf_counter() - inicio
            texto.append(getattr(evento, "delta", ""))
        elif tipo == "response.output_item.added":
            item = getattr(evento, "item", None)
            if getattr(item, "type", "") == "function_call":
                tool_call = True

    return ttft, time.perf_counter() - inicio, tool_call, len("".join(texto))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeticiones", type=int, default=2)
    args = parser.parse_args()

    from openai import OpenAI

    settings = get_settings()
    cliente = OpenAI(api_key=settings.openai_api_key, timeout=90.0)
    modelo = settings.openai_model
    instrucciones = build_instructions(PROFILE)

    escenarios = [
        ("herramientas + effort=low", TOOL_DEFINITIONS, "low"),
        ("herramientas + effort=minimal", TOOL_DEFINITIONS, "minimal"),
        ("sin herramientas + effort=low", [], "low"),
        ("sin herramientas + effort=minimal", [], "minimal"),
    ]

    print(f"Modelo: {modelo} | prompt: ~{len(instrucciones) // 4:,} tokens")
    print(f"{len(PREGUNTAS)} preguntas x {args.repeticiones} repeticiones\n")
    print(f"{'escenario':<34} {'TTFT p50':>9} {'TTFT max':>9} {'total p50':>10} {'tools':>6}")
    print("-" * 74)

    for nombre, tools, effort in escenarios:
        ttfts, totales, llamadas = [], [], 0
        for pregunta in PREGUNTAS:
            for _ in range(args.repeticiones):
                try:
                    ttft, total, tool_call, _ = medir(
                        cliente,
                        modelo=modelo,
                        instrucciones=instrucciones,
                        pregunta=pregunta,
                        tools=tools,
                        effort=effort,
                    )
                except Exception as exc:  # noqa: BLE001
                    print(f"{nombre:<34} error: {type(exc).__name__}: {str(exc)[:60]}")
                    break
                if ttft is not None:
                    ttfts.append(ttft)
                totales.append(total)
                llamadas += int(tool_call)

        if not ttfts:
            continue
        print(
            f"{nombre:<34} {statistics.median(ttfts):>8.2f}s {max(ttfts):>8.2f}s "
            f"{statistics.median(totales):>9.2f}s {llamadas:>5}"
        )

    print()
    print("TTFT = tiempo hasta el primer fragmento de texto, que es lo que se percibe.")
    print("tools = cuántas veces el modelo pidió una herramienta (fuerza otra vuelta).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
