"""O estado do jogo: a raiz de composicao.

Todas as pecas ja existiam separadas — canvas, inventario, banco, ranking,
servico de pintura, pipeline, hub, fonte de eventos. Este modulo monta umas
nas outras e e o unico lugar que sabe a ordem.

Ele existe por dois motivos:

1. **`criar_app` precisa de UMA coisa para receber.** Passar oito objetos
   para o servidor espalharia o conhecimento da montagem por dentro das
   rotas, e trocar qualquer peca viraria uma cacada.
2. **Os testes precisam de um ponto de entrada.** `abrir()` e `fechar()` dao
   ao teste o mesmo ciclo de vida que o servidor tem, sem abrir socket.

O consumo da fila fica aqui, em `processar_pendentes()`, e nao dentro do laco
de background: assim o laco e uma linha e o teste chama exatamente o mesmo
codigo, de forma deterministica, sem `sleep`.
"""

import asyncio
import logging
from collections import deque
from pathlib import Path

from backend.database import Database
from backend.hub import WebSocketHub
from core.event_queue import EventQueue
from core.ratelimit import RateLimiter
from game.canvas import CanvasModel
from game.colors import cores_do_config, lista_da_paleta
from game.events import SchedulerEventos
from game.inventory import Inventario
from game.painting import ServicoPintura
from game.pipeline import Pipeline
from game.ranking import Ranking
from tiktok.adapter import TikTokLiveAdapter
from tiktok.simulado import SimuladorLive

logger = logging.getLogger(__name__)

TAMANHO_DO_RANKING = 5
EVENTOS_POR_FRAME_PADRAO = 400
TAMANHO_DO_FEED_PADRAO = 6


class EstadoJogo:
    """Monta o jogo inteiro e cuida do ciclo de vida dele."""

    def __init__(
        self,
        cfg: dict,
        db_path: str | Path | None = None,
        modo_teste: bool = False,
        seed: int | None = None,
        fonte=None,
    ):
        self.cfg = cfg
        self.modo_teste = modo_teste

        canvas_cfg = cfg.get("canvas") or {}
        app_cfg = cfg.get("app") or {}
        limites = cfg.get("limits") or {}
        tiktok_cfg = cfg.get("tiktok") or {}

        self.canvas = CanvasModel(
            int(canvas_cfg.get("cols") or 26), int(canvas_cfg.get("rows") or 51)
        )
        self.inventario = Inventario()

        caminho = db_path or app_cfg.get("db_path") or "pixelworld.db"
        self.db = Database(caminho)

        self.paleta, self.especiais = cores_do_config(cfg)
        self.lista_paleta = lista_da_paleta(self.paleta)
        self.ranking = Ranking(paleta=self.lista_paleta, tamanho=TAMANHO_DO_RANKING)

        self.limiter = RateLimiter()
        self.servico = ServicoPintura(
            self.canvas,
            self.inventario,
            self.db,
            limiter=self.limiter,
            cooldown=float(tiktok_cfg.get("cooldown_pintura") or 0.0),
        )

        self.fila = EventQueue(int(limites.get("queue_max_size") or 5000))

        # O agendador dos eventos automaticos (ARCO-IRIS, TURBO). Ele
        # publica direto no hub; o pipeline pergunta a ele pelo multiplicador
        # a cada evento, entao a regra do bonus mora num lugar so.
        self.scheduler = SchedulerEventos(cfg, publicar=self._publicar_do_hub, seed=seed)

        self.pipeline = Pipeline(
            cfg,
            servico=self.servico,
            inventario=self.inventario,
            db=self.db,
            ranking=self.ranking,
            multiplicador_fn=self.multiplicador,
        )

        self.intervalo_quadro = max(0.005, float((cfg.get("server") or {}).get("frame_ms") or 50) / 1000.0)
        self.hub = WebSocketHub(intervalo=self.intervalo_quadro)

        self.fonte = fonte or self._criar_fonte(seed)

        self.eventos_por_frame = max(
            1, int(app_cfg.get("events_per_frame") or EVENTOS_POR_FRAME_PADRAO)
        )
        self.feed: deque[dict] = deque(
            maxlen=max(1, int(app_cfg.get("feed_size") or TAMANHO_DO_FEED_PADRAO))
        )

        self._tarefa: asyncio.Task | None = None
        self._aberto = False

    def _criar_fonte(self, seed: int | None):
        if self.modo_teste:
            return SimuladorLive(self.fila, self.cfg, seed=seed)
        return TikTokLiveAdapter(self.fila, self.cfg)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    @property
    def aberto(self) -> bool:
        return self._aberto

    async def abrir(self) -> None:
        """Abre o banco, aquece a memoria e comeca a consumir a fila. Idempotente."""
        if self._aberto:
            return

        self._aberto = True
        await self.db.abrir()

        # O canvas e a UNICA coisa que nao pode se perder num reinicio. O
        # ranking volta junto para que a tela nao comece do zero enquanto o
        # desenho ja esta la.
        self.canvas.carregar(await self.db.carregar_canvas())
        self.ranking.carregar(await self.db.top_pintores(500))

        self.fonte.start()
        await self.hub.iniciar()

        self._tarefa = asyncio.create_task(self._laco(), name="jogo")
        logger.info(
            "PIXEL WORLD no ar — %dx%d, %d celulas pintadas, fonte: %s",
            self.canvas.cols,
            self.canvas.rows,
            self.canvas.preenchidas(),
            self.fonte.status.detail,
        )

    async def fechar(self) -> None:
        if not self._aberto:
            return

        self._aberto = False

        tarefa, self._tarefa = self._tarefa, None
        if tarefa is not None and not tarefa.done():
            tarefa.cancel()
            try:
                await tarefa
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug("O laco do jogo terminou com erro", exc_info=True)

        self.fonte.stop()
        await self.hub.parar()
        await self.db.fechar()

    async def _laco(self) -> None:
        while True:
            await asyncio.sleep(self.intervalo_quadro)
            try:
                self.scheduler.tick()
                await self.processar_pendentes()
            except asyncio.CancelledError:
                raise
            except Exception:
                # O laco nunca pode morrer: se ele morre, o jogo para de
                # responder e o unico sintoma e o silencio.
                logger.exception("Falha ao processar o quadro")

    # ------------------------------------------------------------------
    # O quadro
    # ------------------------------------------------------------------

    async def processar_pendentes(self) -> int:
        """Consome a fila e publica o resultado. Devolve quantos eventos saiu.

        O limite por quadro e o que impede que uma rajada de 2000 eventos
        trave o servidor por segundos: sobra para o quadro seguinte.
        """
        eventos = self.fila.drain(self.eventos_por_frame)
        if not eventos:
            return 0

        pintou = False

        for evento in eventos:
            mensagens = await self.pipeline.processar(evento)
            for mensagem in mensagens:
                if mensagem.get("type") == "feed":
                    self.feed.appendleft(mensagem)
                elif mensagem.get("type") == "pixel_painted":
                    pintou = True
                self.hub.publicar(mensagem)

        if pintou:
            # `ranking` e `stats` SUBSTITUEM no hub: publicar varias vezes no
            # mesmo quadro custa uma mensagem so, a ultima.
            self.publicar_estado()

        return len(eventos)

    def publicar_estado(self) -> None:
        """Manda o ranking e as estatisticas atuais para a tela."""
        self.hub.publicar({"type": "ranking", "top": self.ranking.top_para_dict()})
        self.hub.publicar({"type": "stats", **self.stats()})

    def _publicar_do_hub(self, mensagem: dict) -> None:
        """O agendador publica pelo hub como qualquer outra peca do jogo."""
        self.hub.publicar(mensagem)

    def multiplicador(self) -> float:
        """O bonus de pixels do evento ao vivo em curso, se houver."""
        if self.scheduler is None:
            return 1.0
        try:
            return float(self.scheduler.multiplicador_pixels())
        except Exception:
            logger.debug("Falha ao ler o multiplicador do evento", exc_info=True)
            return 1.0

    # ------------------------------------------------------------------
    # Leituras
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        """As estatisticas do HUD, na forma do spec §12."""
        return {
            "filled": self.canvas.preenchidas(),
            "total": self.canvas.total,
            "users": self.ranking.total(),
            "colors": len({c.color for c in self.canvas.celulas_pintadas()}),
        }

    def hello(self) -> dict:
        """O primeiro pacote de quem acabou de conectar."""
        return {
            "type": "hello",
            "canvas": self.canvas.para_dict(),
            "stats": self.stats(),
            "ranking": self.ranking.top_para_dict(),
            "feed": list(self.feed),
            # O evento em curso vai JUNTO. Quem conecta no meio de um evento
            # nao recebe o `event_start` que ja passou, e sem isto o telao
            # ficaria mudo enquanto o multiplicador esta valendo — a pagina do
            # OBS recarrega sozinha quando a cena fica ativa, entao acontece.
            "event": self.scheduler.estado() if self.scheduler else None,
        }

    def snapshot(self) -> dict:
        """O que o painel de controle mostra."""
        return {
            "canvas": {
                "cols": self.canvas.cols,
                "rows": self.canvas.rows,
                "total": self.canvas.total,
                "filled": self.canvas.preenchidas(),
                "percent": self.canvas.percentual(),
            },
            "users": self.ranking.total(),
            "colors": len({c.color for c in self.canvas.celulas_pintadas()}),
            "ranking": self.ranking.top_para_dict(),
            "feed": list(self.feed),
            "fonte": {
                "connected": self.fonte.status.connected,
                "detail": self.fonte.status.detail,
                "reconnects": self.fonte.status.reconnects,
            },
            "modo_teste": self.modo_teste,
            "event": self.scheduler.estado() if self.scheduler else None,
            "fila": self.fila.size(),
        }
