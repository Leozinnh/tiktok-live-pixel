"""Olha o telao: le o que o jogo transmite para a tela, sem interferir.

Conecta no WebSocket do hub como qualquer outro cliente (a cena do OBS faz
exatamente o mesmo) e imprime o que passa — MENOS os quadros do canvas, que
sao 20 por segundo e afogariam o resto. Quem usa isto ve o telao pelos olhos
do backend: se o aviso saiu do jogo, aparece aqui; se nao aparece aqui, o
problema e ANTES da tela — e o oposto tambem vale.

Uso:  python -u .verif/olha_telao.py
"""
import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets  # noqa: E402

ENDERECO = "ws://127.0.0.1:8000/ws"
IGNORAR = {"canvas", "pong", "ranking", "stats"}


def linha(pacote: dict) -> str:
    agora = time.strftime("%H:%M:%S")
    tipo = pacote.get("type", "?")
    if tipo == "pixel_painted":
        return f"[{agora}] pixel_painted {pacote.get('x')},{pacote.get('y')} {pacote.get('color')}"
    partes = [f"[{agora}] {tipo}"]
    if pacote.get("kind"):
        partes.append(str(pacote["kind"]))
    if pacote.get("text"):
        partes.append(str(pacote["text"]))
    if tipo == "hello":
        partes.append(f"(tela {pacote.get('canvas', {}).get('cols')}x{pacote.get('canvas', {}).get('rows')})")
    return " | ".join(partes)


async def main() -> None:
    while True:
        try:
            async with websockets.connect(ENDERECO, max_size=2**22) as ws:
                print(f"[telao] conectado em {ENDERECO}", flush=True)
                async for bruto in ws:
                    pacote = json.loads(bruto)
                    if pacote.get("type") in IGNORAR:
                        continue
                    print(linha(pacote), flush=True)
        except Exception as erro:
            print(f"[telao] caiu ({erro}); tentando de novo...", flush=True)
            await asyncio.sleep(2)


asyncio.run(main())
