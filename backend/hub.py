"""O hub de WebSocket: agrupa o que sai para a tela.

O jogo roda a 20 quadros por segundo. Uma LIVE cheia manda muito mais evento
do que isso. Mandar um pacote por evento seria uma chamada de `send` por
evento por espectador: a banda nao aguenta, e o navegador passa mais tempo
decodificando JSON do que desenhando.

A regra tem duas metades, e a diferenca entre elas e o desenho inteiro:

- **Evento** (`pixel_painted`, `feed`, `toast`, `inventario`) ACUMULA num
  lote. Cada um e um fato que aconteceu e que a tela precisa mostrar; nenhum
  pode sumir. Mas todos cabem num pacote so, uma vez por quadro.
- **Estado** (`ranking`, `stats`) SUBSTITUI o anterior do mesmo tipo. Nao
  interessa o ranking de tres quadros atras; interessa o de agora. Mandar os
  tres seria mandar dois numeros que ja nasceram velhos.

`publicar` e SINCRONO de proposito. Ele e chamado no caminho quente do jogo —
uma vez por pixel pintado — e nao pode suspender nem fazer I/O. Ele so pega
um lock por microssegundos e guarda. Quem envia e o laco do hub.
"""

import asyncio
import logging
import threading
from collections import deque
from typing import Any, Iterable

logger = logging.getLogger(__name__)

# Os tipos que SUBSTITUEM. Um tipo novo que nao esteja aqui acumula — que e
# o padrao seguro: perder um evento e pior que mandar dois.
TIPOS_DE_ESTADO = frozenset({"ranking", "stats", "estado", "canvas"})

INTERVALO_PADRAO = 0.05
TIMEOUT_ENVIO_PADRAO = 2.0
MAX_LOTE_PADRAO = 2000

TIPO_DO_LOTE = "pixels"


class WebSocketHub:
    """Distribui mensagens para todos os espectadores conectados."""

    def __init__(
        self,
        intervalo: float = INTERVALO_PADRAO,
        timeout_envio: float = TIMEOUT_ENVIO_PADRAO,
        max_lote: int = MAX_LOTE_PADRAO,
        tipos_de_estado: Iterable[str] = TIPOS_DE_ESTADO,
    ):
        self.intervalo = max(0.001, float(intervalo))
        self.timeout_envio = max(0.05, float(timeout_envio))
        self.max_lote = max(1, int(max_lote))
        self.tipos_de_estado = frozenset(tipos_de_estado)

        self._clientes: set[Any] = set()
        self._estado: dict[str, dict] = {}
        # `deque` com `maxlen` descarta o mais antigo em O(1) quando enche.
        # Numa lista, apara a cada publicacao seria O(n) por evento.
        self._lote: deque[dict] = deque(maxlen=self.max_lote)

        self._lock = threading.Lock()
        self._tarefa: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------

    def publicar(self, msg: dict) -> None:
        """Guarda uma mensagem para o proximo quadro. Nunca bloqueia."""
        if not isinstance(msg, dict):
            return

        tipo = msg.get("type")

        if tipo == "toast":
            # O toast vive na cena do OBS, que fica fora do alcance de quem
            # esta ao vivo. Espelhar aqui e o que permite depurar "o jogo
            # avisou?" pelo terminal — e e o unico registro que sobra quando
            # a tela esta fechada. So o toast: o resto e volume.
            logger.info(
                "Toast na tela (%s): %s",
                msg.get("kind") or "info",
                msg.get("text") or "",
            )

        with self._lock:
            if tipo in self.tipos_de_estado:
                # Substitui: so o ultimo estado de cada tipo importa.
                self._estado[str(tipo)] = msg
            else:
                self._lote.append(msg)

    def publicar_varias(self, msgs: Iterable[dict]) -> None:
        """Atalho para o que o pipeline devolve, que e uma lista."""
        for msg in msgs:
            self.publicar(msg)

    # ------------------------------------------------------------------
    # Clientes
    # ------------------------------------------------------------------

    def registrar(self, ws: Any) -> None:
        self._clientes.add(ws)

    def desregistrar(self, ws: Any) -> None:
        self._clientes.discard(ws)

    def contar(self) -> int:
        return len(self._clientes)

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def iniciar(self) -> None:
        if self._tarefa is not None and not self._tarefa.done():
            return
        self._tarefa = asyncio.create_task(self._laco(), name="hub-websocket")

    async def parar(self) -> None:
        """Para o laco e DESPEJA o que sobrou.

        Sem o despejo final, os ultimos pixels pintados antes de desligar
        ficariam no buffer e nunca chegariam a tela — justamente os que a
        pessoa que mandou a rosa esta esperando ver.
        """
        tarefa, self._tarefa = self._tarefa, None

        if tarefa is not None and not tarefa.done():
            tarefa.cancel()
            try:
                await tarefa
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug("O laco do hub terminou com erro", exc_info=True)

        await self.despejar()

    async def _laco(self) -> None:
        while True:
            await asyncio.sleep(self.intervalo)
            try:
                await self.despejar()
            except asyncio.CancelledError:
                raise
            except Exception:
                # O laco NUNCA pode morrer: se ele morre, a tela congela e o
                # unico sintoma e "o jogo parou de responder".
                logger.exception("Falha ao despejar o lote")

    # ------------------------------------------------------------------
    # Saida
    # ------------------------------------------------------------------

    async def despejar(self) -> None:
        """Envia agora o que estiver acumulado. Idempotente."""
        with self._lock:
            lote = list(self._lote)
            self._lote.clear()
            estado = list(self._estado.values())
            self._estado.clear()

        if not self._clientes:
            return

        pacotes: list[dict] = []
        if lote:
            # O lote sai ANTES do estado: a tela aplica os pixels novos e so
            # depois repinta o ranking. Na ordem inversa, o ranking mostraria
            # uma posicao que os pixels ainda nao tinham produzido.
            pacotes.append({"type": TIPO_DO_LOTE, "items": lote})
        pacotes.extend(estado)

        if not pacotes:
            return

        await self._enviar(pacotes)

    async def _enviar(self, pacotes: list[dict]) -> None:
        """Manda para todo mundo, e derruba so quem nao conseguiu receber.

        Um celular que perdeu o sinal no meio da LIVE nao pode levar a sala
        junto: a falha de um cliente e isolada, e ele sai da lista em vez de
        derrubar o quadro.
        """
        mortos: list[Any] = []

        for ws in list(self._clientes):
            try:
                for pacote in pacotes:
                    await asyncio.wait_for(
                        ws.send_json(pacote), timeout=self.timeout_envio
                    )
            except asyncio.CancelledError:
                raise
            except Exception as erro:
                logger.debug("Removendo cliente que nao recebeu: %s", erro)
                mortos.append(ws)

        for ws in mortos:
            self.desregistrar(ws)

        if mortos:
            logger.info("%d cliente(s) removido(s) por falha de envio", len(mortos))
