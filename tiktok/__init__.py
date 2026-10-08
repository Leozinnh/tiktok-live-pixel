"""Camada de conexao com a LIVE.

`base.py`     — o contrato (`LiveAdapter`, `AdapterStatus`).
`adapter.py`  — a conexao real com o TikTok; traduz o Webcast para `LiveEvent`.
`simulado.py` — a fonte falsa do MODO TESTE.

O resto do jogo so conhece o contrato. Trocar de fonte nao muda nada abaixo
desta camada.
"""

from tiktok.base import AdapterStatus, LiveAdapter

__all__ = ["AdapterStatus", "LiveAdapter"]
