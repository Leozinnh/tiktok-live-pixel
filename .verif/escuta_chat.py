"""Escuta o chat da live e imprime o texto CRU de cada comentario.

Por que existe: o `/pontos` nao respondeu no chat de verdade, e o caminho
inteiro ja foi conferido por dentro (o adapter le o campo certo, o parse nao
engole o comando, a resposta esta testada). Falta a unica ponta que nao da
para testar em casa: o que o TIKTOK entrega. Este script conecta na live do
config e imprime cada comentario como ele chegou — em `repr`, para qualquer
caractere invisivel (ou uma barra de outro alfabeto) aparecer.

Ele SO escuta: nao responde, nao escreve em banco, nao posta nada. A conexao
de leitura da webcast aceita varios clientes ao mesmo tempo, entao ele pode
rodar junto com o jogo ligado, sem conflito.

Uso:
    python -u .verif/escuta_chat.py [--config config.json]

A saida vai para o terminal (ou para onde o shell redirecionar). Ctrl+C sai.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent


def agora() -> str:
    return datetime.now().strftime("%H:%M:%S")


def carregar_username(caminho: str) -> str:
    with open(caminho, encoding="utf-8") as arquivo:
        cfg = json.load(arquivo)
    return str(cfg["tiktok"]["username"]).strip().lstrip("@")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()

    username = carregar_username(args.config)
    print(f"[{agora()}] escutando o chat de @{username}", flush=True)

    while True:
        client = TikTokLiveClient(unique_id=username)

        @client.on(ConnectEvent)
        async def _conectou(evento) -> None:
            print(f"[{agora()}] CONECTOU na live", flush=True)

        @client.on(DisconnectEvent)
        async def _caiu(evento) -> None:
            print(f"[{agora()}] DESCONECTOU: {evento!r}", flush=True)

        @client.on(CommentEvent)
        async def _comentou(evento) -> None:
            # `content` e o campo que o adapter le; `comment` e o irmao que ele
            # aceita de reserva. Os dois vao para o print: um deles pode vir
            # vazio, e e justamente isso que precisa ficar visivel.
            conteudo = getattr(evento, "content", None)
            irmao = getattr(evento, "comment", None)
            quem = getattr(getattr(evento, "user", None), "unique_id", "?")
            print(
                f"[{agora()}] COMENTARIO @{quem}: content={conteudo!r} comment={irmao!r}",
                flush=True,
            )

        try:
            await client.connect(
                fetch_gift_info=False,
                fetch_room_info=False,
                fetch_live_check=True,
            )
        except Exception as erro:
            print(
                f"[{agora()}] connect falhou: {erro!r} — tento de novo em 10s",
                flush=True,
            )
            await asyncio.sleep(10)
        else:
            print(f"[{agora()}] a conexao encerrou — tento de novo em 10s", flush=True)
            await asyncio.sleep(10)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("tchau", flush=True)
