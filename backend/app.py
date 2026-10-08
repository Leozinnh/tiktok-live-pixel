"""O servidor: a tela do OBS, o WebSocket e o painel.

Este e o unico modulo do projeto que fica exposto na rede local, e o desenho
dele e governado por duas regras de seguranca:

1. **O cliente NUNCA pinta.** O WebSocket so ESCUTA, e a unica coisa que ele
   aceita de volta e `ping`. Pintura nasce de evento do TikTok ou do painel
   (spec §12). Sem isso, qualquer um que descobrisse o `localhost` do
   streamer pintaria de graca — e a economia do jogo (rosa -> pixel) viraria
   enfeite.

2. **Nada fora das pastas de tela e servido, e origem nenhuma e liberada.**
   A raiz do projeto tem `config.json` (que aponta para a LIVE) e o banco da
   comunidade. Por isso NAO existe middleware de CORS: o painel do OBS e
   mesma-origem, entao a defesa de verdade e a AUSENCIA do cabecalho, que
   impede uma pagina qualquer que o streamer abra de chamar esta API.

As duas paginas (tela e painel) sao servidas com substituto quando o arquivo
ainda nao existe. E o que permite construir o servidor antes do frontend e
depois so soltar o HTML no lugar, sem tocar em rota nenhuma.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.control import montar_controle

logger = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
PASTA_UI = RAIZ / "ui"
PASTA_CONTROLE = RAIZ / "control"

TITULO_PADRAO = "PIXEL WORLD"


def criar_app(estado) -> FastAPI:
    """Monta o servidor inteiro em cima de um `EstadoJogo`."""

    @asynccontextmanager
    async def ciclo(_app: FastAPI):
        # O mesmo `abrir`/`fechar` que os testes chamam a mao. O servidor e
        # so mais um cliente do estado — nao ha caminho de inicializacao
        # exclusivo de producao, que e onde os bugs de boot costumam morar.
        await estado.abrir()
        try:
            yield
        finally:
            await estado.fechar()

    app = FastAPI(
        title=_titulo(estado),
        lifespan=ciclo,
        # Sem /docs, /redoc e /openapi.json: sao tres superficies a mais
        # numa maquina que fica aberta durante a LIVE, e o painel nao usa.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    montar_controle(app, estado)
    _montar_websocket(app, estado)
    _montar_paginas(app, estado)
    return app


def _titulo(estado) -> str:
    return str((estado.cfg.get("app") or {}).get("titulo") or TITULO_PADRAO)


# --------------------------------------------------------------------------
# WebSocket
# --------------------------------------------------------------------------


def _montar_websocket(app: FastAPI, estado) -> None:
    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()

        try:
            # O `hello` vai ANTES de registrar no hub: quem conecta precisa
            # receber o canvas inteiro primeiro. Registrado antes, um pixel
            # pintado no meio do envio chegaria fora de ordem, e a tela
            # aplicaria uma pintura sobre um canvas que ela ainda nao tem.
            await websocket.send_json(estado.hello())
        except Exception:
            logger.debug("Cliente caiu antes do hello", exc_info=True)
            return

        estado.hub.registrar(websocket)

        try:
            while True:
                texto = await websocket.receive_text()
                if texto.strip().lower() == "ping":
                    await websocket.send_json({"type": "pong"})
                # Qualquer outra coisa e ignorada de proposito: o cliente
                # nao tem nada a dizer ao jogo.
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("WebSocket encerrado por erro", exc_info=True)
        finally:
            estado.hub.desregistrar(websocket)


# --------------------------------------------------------------------------
# Paginas
# --------------------------------------------------------------------------


def _montar_paginas(app: FastAPI, estado) -> None:
    @app.get("/", response_class=HTMLResponse)
    async def tela() -> HTMLResponse:
        return _pagina(PASTA_UI / "index.html", _titulo(estado))

    @app.get("/control", response_class=HTMLResponse)
    async def painel() -> HTMLResponse:
        return _pagina(PASTA_CONTROLE / "index.html", _titulo(estado))

    # So monta o que existe. `check_dir=False` NAO resolve: ele adia a
    # checagem para a PRIMEIRA requisicao, e ai `StaticFiles` levanta
    # `RuntimeError` em vez de responder 404 — um erro de servidor no meio
    # da LIVE por causa de uma pasta que ainda nao foi criada.
    #
    # Sem a pasta, a resposta certa e 404 mesmo. Uma rota que nao existe da
    # exatamente isso.
    if PASTA_UI.is_dir():
        app.mount("/ui", StaticFiles(directory=PASTA_UI), name="ui")

    if PASTA_CONTROLE.is_dir():
        app.mount("/control", StaticFiles(directory=PASTA_CONTROLE), name="painel")


def _pagina(caminho: Path, titulo: str) -> HTMLResponse:
    if caminho.is_file():
        try:
            return HTMLResponse(caminho.read_text(encoding="utf-8"))
        except OSError:
            logger.exception("Nao consegui ler %s", caminho)

    return HTMLResponse(_esqueleto(titulo))


def _esqueleto(titulo: str) -> str:
    """O que aparece antes de o frontend existir.

    Diz o nome do jogo e o que esta faltando. Uma pagina em branco faria o
    streamer achar que o servidor nao subiu.
    """
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<style>
  html, body {{ height: 100%; margin: 0; }}
  body {{
    display: grid; place-content: center; gap: 12px;
    background: #05060a; color: #d7e3ff; text-align: center;
    font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
  }}
  h1 {{ margin: 0; letter-spacing: .32em; font-size: 2rem; color: #38f5ff; }}
  p {{ margin: 0; color: #6b7ba6; letter-spacing: .08em; }}
</style>
</head>
<body>
<h1>{titulo}</h1>
<p>servidor no ar — a tela ainda nao foi construida</p>
</body>
</html>
"""
