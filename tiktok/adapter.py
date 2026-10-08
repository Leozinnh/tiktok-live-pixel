"""Conexao com a LIVE do TikTok.

Portado do projeto `tiktok_live_interactive_game`, que ja rodava em LIVE de
verdade. As armadilhas documentadas aqui foram todas descobertas na pratica —
cada uma delas derrubou uma transmissao antes de virar comentario.

A biblioteca `TikTokLive` e engenharia reversa do Webcast interno. Nao e API
oficial, nao tem contrato e quebra sem aviso. Por isso a traducao dos eventos
para o formato interno esta em funcoes PURAS, separadas da rede: quando o
formato mudar, o conserto e local e testavel em milissegundos.

Tres armadilhas vivem neste arquivo:

1. **O cliente nao e reutilizavel.** Depois que ele cai, criar outro em cima
   do mesmo objeto nao funciona. Cada tentativa monta um cliente NOVO.
2. **`close()` levanta `RuntimeError`.** Ver `_descartar`.
3. **Streak de presente.** Ver `evento_de_presente`.
"""

import asyncio
import logging
import random
import threading
from typing import Any

from core.event_queue import EventQueue
from core.events import EventType, LiveEvent
from tiktok.base import AdapterStatus

logger = logging.getLogger(__name__)

BACKOFF_INICIAL = 5.0
BACKOFF_MAX = 60.0
DORMIR_OFFLINE = 30.0
DORMIR_BLOQUEADO = 60.0

# A biblioteca so e necessaria quando existe uma LIVE para conectar. Importar
# aqui dentro do try permite que todo o resto — a traducao dos eventos, o modo
# teste, a suite inteira — rode numa maquina onde ela nem esta instalada.
try:  # pragma: no cover - depende do ambiente
    from TikTokLive import TikTokLiveClient
    from TikTokLive.client.errors import (
        UserNotFoundError,
        UserOfflineError,
        WebcastBlockedError,
    )
    from TikTokLive.events import (
        CommentEvent,
        ConnectEvent,
        DisconnectEvent,
        FollowEvent,
        GiftEvent,
        JoinEvent,
        LikeEvent,
        ShareEvent,
    )

    TIKTOKLIVE_DISPONIVEL = True
    TIKTOKLIVE_ERRO = ""
except ImportError as erro:  # pragma: no cover - depende do ambiente
    # O motivo fica guardado. "Nao instalada" e apenas UMA das causas
    # possiveis: um submodulo que mudou de lugar entre versoes derruba o bloco
    # inteiro e produziria a mesma mensagem para uma biblioteca instalada e
    # funcional — foi o que aconteceu quando as excecoes sairam de
    # `TikTokLive.events.exceptions` para `TikTokLive.client.errors`.
    TIKTOKLIVE_DISPONIVEL = False
    TIKTOKLIVE_ERRO = str(erro)
    TikTokLiveClient = None  # type: ignore[assignment,misc]

    class UserNotFoundError(Exception):  # type: ignore[no-redef]
        """Placeholder: nunca levantada quando a biblioteca falta."""

    class UserOfflineError(Exception):  # type: ignore[no-redef]
        """Placeholder: nunca levantada quando a biblioteca falta."""

    WebcastBlockedError = None  # type: ignore[assignment,misc]


# --------------------------------------------------------------------------
# Traducao — funcoes puras
# --------------------------------------------------------------------------


def _user_id(user: Any) -> str:
    """O `unique_id` e o handle; `display_id` e o fallback historico."""
    if user is None:
        return ""
    return str(getattr(user, "unique_id", None) or getattr(user, "display_id", None) or "")


def _display_name(user: Any) -> str:
    """O apelido bonito. Cai para o handle, nunca para a string 'None'."""
    if user is None:
        return ""
    return str(getattr(user, "nickname", None) or _user_id(user) or "")


def evento_de_comentario(obj: Any) -> LiveEvent:
    """Comentario do chat.

    A v3 da biblioteca renomeou o campo para `content`; salas antigas ainda
    mandam `comment`. Ler os dois e o que faz a mesma versao do jogo funcionar
    nas duas.
    """
    user = getattr(obj, "user", None)
    return LiveEvent(
        type=EventType.COMMENT,
        username=_user_id(user),
        display_name=_display_name(user),
        text=str(getattr(obj, "content", None) or getattr(obj, "comment", None) or ""),
        raw=obj,
    )


def evento_de_presente(obj: Any) -> LiveEvent | None:
    """Presente, ja consolidado. Devolve `None` para o que nao conta.

    **O caso do streak.** Quando alguem segura o botao e manda 40 rosas, a
    biblioteca emite um evento por rosa, todos com `streaking=True`, e so o
    ULTIMO chega com `streaking=False` e `repeat_count=40`.

    Sem descartar os intermediarios, um streak de 40 rosas viraria 200 pixels
    em vez de 40 — cinco vezes a economia do jogo. Por isso o filtro nao e
    uma otimizacao: e a regra.

    Um presente nao-streakable tambem chega com `streaking=False` e
    `repeat_count=1`, e passa por aqui normalmente.
    """
    if getattr(obj, "gift", None) is None:
        # Presente que a biblioteca nao conseguiu resolver (sem `fetch_gift_info`).
        return None

    if getattr(obj, "streaking", False):
        return None

    user = getattr(obj, "user", None)
    gift = obj.gift

    return LiveEvent(
        type=EventType.GIFT,
        username=_user_id(user),
        display_name=_display_name(user),
        gift_name=str(getattr(gift, "name", None) or getattr(obj, "gift_name", None) or ""),
        gift_id=str(getattr(gift, "id", None) or getattr(obj, "gift_id", None) or "") or None,
        quantity=max(1, int(getattr(obj, "repeat_count", None) or 1)),
        raw=obj,
    )


def evento_de_like(obj: Any, total_anterior: int = 0) -> LiveEvent | None:
    """Curtida, com o total da sala como fonte da verdade.

    `total` e o acumulado da sala e so cresce. `count` e o incremento daquele
    evento. Depois de ~10 a 20 curtidas seguidas da mesma pessoa o TikTok
    PARA DE MANDAR O AUTOR, entao `user` pode vir `None` — o evento continua
    valido e nao pode ser descartado por isso.

    Um `total` menor que o anterior e ruido de rede, nao uma retratacao: o
    jogador nao pode "descurtir" pixels.
    """
    total = int(getattr(obj, "total", 0) or 0)
    delta = max(0, int(getattr(obj, "count", 0) or 0))

    if total < total_anterior:
        # O evento esta fora de ordem (chegou atrasado) ou o contador da sala
        # reiniciou. Nos dois casos o total nao merece confianca — e se o
        # total nao merece, o incremento dele tambem nao: contar os dois
        # creditaria de novo curtidas que ja entraram na conta.
        total = total_anterior
        delta = 0

    if total == 0 and delta == 0:
        return None

    user = getattr(obj, "user", None)
    return LiveEvent(
        type=EventType.LIKE,
        username=_user_id(user),
        display_name=_display_name(user),
        like_delta=delta,
        like_total=total,
        raw=obj,
    )


def evento_de_presenca(obj: Any, tipo: EventType) -> LiveEvent:
    """Seguidor novo, compartilhamento ou chegada: mesmo formato, so o tipo."""
    user = getattr(obj, "user", None)
    return LiveEvent(
        type=tipo,
        username=_user_id(user),
        display_name=_display_name(user),
        raw=obj,
    )


# --------------------------------------------------------------------------
# O adapter
# --------------------------------------------------------------------------


class TikTokLiveAdapter:
    """Conecta na LIVE e traduz o que chega para a `EventQueue`.

    Roda numa thread propria com loop asyncio proprio, porque a biblioteca
    assume que controla o loop. A fila e o unico ponto de contato com o
    servidor: nenhum estado de jogo atravessa essa fronteira.
    """

    def __init__(self, queue: EventQueue, config: dict):
        cfg = (config or {}).get("tiktok") or {}
        self.queue = queue
        self.username = str(cfg.get("username") or "").strip().lstrip("@")
        self.reconnect_seconds = float(cfg.get("reconnect_seconds") or BACKOFF_INICIAL)
        self.reconnect_max_seconds = float(cfg.get("reconnect_max_seconds") or BACKOFF_MAX)
        self.fetch_gift_info = bool(cfg.get("fetch_gift_info", True))

        self._status = AdapterStatus()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._like_total = 0

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    @property
    def status(self) -> AdapterStatus:
        return self._status

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        if not TIKTOKLIVE_DISPONIVEL:
            self._status = AdapterStatus(
                connected=False,
                detail=f"biblioteca TikTokLive indisponivel: {TIKTOKLIVE_ERRO}",
            )
            # Sem o motivo real, a mensagem manda reinstalar uma biblioteca que
            # ja esta instalada e o `pip install` nunca resolve nada.
            logger.error(
                "TikTokLive indisponivel (%s). `pip install -r requirements.txt` "
                "so resolve se ela estiver mesmo ausente; se `pip show TikTokLive` "
                "mostrar a versao instalada, o import no topo de tiktok/adapter.py "
                "e que esta desatualizado. Ou use o modo teste.",
                TIKTOKLIVE_ERRO,
            )
            return

        self._stop.clear()
        self._thread = threading.Thread(
            target=self._rodar, name="tiktok-live", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Idempotente e imediato. O `start` de novo sempre funciona depois."""
        self._stop.set()
        self._status = AdapterStatus(connected=False, detail="encerrado")

    def _rodar(self) -> None:
        try:
            asyncio.run(self._viver())
        except Exception:
            # A thread inteira morreu: sem este log a LIVE ficaria muda e o
            # unico sintoma seria "nao acontece nada".
            logger.exception("A thread do TikTok terminou com erro")
            self._status = AdapterStatus(connected=False, detail="falhou")

    async def _viver(self) -> None:
        """Tenta conectar para sempre, com backoff, ate alguem mandar parar."""
        backoff = self.reconnect_seconds

        while not self._stop.is_set():
            client = None
            try:
                # Cliente NOVO a cada tentativa: depois que um cai, ele nao
                # volta a funcionar.
                client = TikTokLiveClient(unique_id=self.username)
                self._registrar_handlers(client)

                await client.connect(
                    fetch_gift_info=self.fetch_gift_info,
                    fetch_room_info=False,
                    fetch_live_check=True,
                )
                backoff = self.reconnect_seconds

            except UserNotFoundError:
                # O @ esta errado. Reconectar nao conserta um nome errado, e
                # insistir so gasta os servidores de assinatura de terceiros.
                logger.error("Nao existe usuario @%s no TikTok", self.username)
                self._status = AdapterStatus(connected=False, detail="usuario nao existe")
                return

            except UserOfflineError:
                logger.info("A LIVE de @%s esta offline", self.username)
                self._status = AdapterStatus(connected=False, detail="offline")
                await self._descartar(client)
                await self._dormir(DORMIR_OFFLINE)
                continue

            except asyncio.CancelledError:
                break

            except Exception as erro:
                bloqueado = WebcastBlockedError is not None and isinstance(
                    erro, WebcastBlockedError
                )
                if bloqueado:
                    logger.warning("O Webcast bloqueou a conexao; esperando mais")
                    self._status = AdapterStatus(connected=False, detail="bloqueado")
                    await self._descartar(client)
                    await self._dormir(DORMIR_BLOQUEADO)
                    continue

                logger.warning("Falha na conexao: %s", erro)
                self._status = AdapterStatus(
                    connected=False,
                    detail=f"erro: {type(erro).__name__}",
                    reconnects=self._status.reconnects + 1,
                )
                await self._descartar(client)
                await self._dormir(self._espera(backoff, self._status.reconnects))
                backoff = min(self.reconnect_max_seconds, backoff * 2)
                continue

            # So chega aqui quando a conexao CAIU (o `connect` so retorna
            # quando o websocket fecha). Nao e erro, mas tambem nao e sucesso.
            await self._descartar(client)
            if self._stop.is_set():
                break

            backoff = min(self.reconnect_max_seconds, backoff * 2)
            self._status = AdapterStatus(
                connected=False,
                detail="caiu, reconectando",
                reconnects=self._status.reconnects + 1,
            )
            await self._dormir(self._espera(backoff, self._status.reconnects))

        self._status = AdapterStatus(
            connected=False, detail="encerrado", reconnects=self._status.reconnects
        )

    async def _descartar(self, client: Any) -> None:
        """NAO usamos `close_client=True` nem `client.close()`: os dois chamam
        `_clean_tasks()`, que faz `self._asyncio_loop.run_until_complete(...)`.
        Como `_asyncio_loop` devolve o loop JA EM EXECUCAO quando existe um,
        isso levanta `RuntimeError: This event loop is already running` — e a
        excecao sobe de dentro de um `finally`, derrubando a thread inteira.

        `disconnect()` sozinho desliga o websocket sem passar por ali."""
        if client is None:
            return
        try:
            await client.disconnect()
        except Exception:
            logger.debug("Falha ao desconectar o cliente", exc_info=True)

    def _espera(self, backoff: float, tentativa: int) -> float:
        """Backoff com jitter.

        Sem o jitter, todo mundo que caiu junto volta no mesmo instante e
        derruba a conexao de novo — o mesmo efeito de manada que derrubou.
        """
        return backoff * (0.5 + random.random())

    async def _dormir(self, segundos: float) -> None:
        """Dorme em fatias para que `stop()` responda na hora."""
        fatia = 0.25
        restante = max(0.0, segundos)
        while restante > 0 and not self._stop.is_set():
            await asyncio.sleep(min(fatia, restante))
            restante -= fatia

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _registrar_handlers(self, client: Any) -> None:
        @client.on(ConnectEvent)
        async def _conectou(evento: Any) -> None:
            self._status = AdapterStatus(
                connected=True,
                detail=f"ao vivo: @{self.username}",
                reconnects=self._status.reconnects,
            )
            logger.info("Conectado a LIVE de @%s", self.username)
            self.queue.put(LiveEvent(type=EventType.SYSTEM, text="connected"))

        @client.on(DisconnectEvent)
        async def _desconectou(evento: Any) -> None:
            self._status = AdapterStatus(
                connected=False,
                detail="caiu, reconectando",
                reconnects=self._status.reconnects,
            )
            self.queue.put(LiveEvent(type=EventType.SYSTEM, text="disconnected"))

        @client.on(CommentEvent)
        async def _comentou(evento: Any) -> None:
            self.queue.put(evento_de_comentario(evento))

        @client.on(GiftEvent)
        async def _presenteou(evento: Any) -> None:
            traduzido = evento_de_presente(evento)
            if traduzido is not None:
                self.queue.put(traduzido)

        @client.on(LikeEvent)
        async def _curtiu(evento: Any) -> None:
            traduzido = evento_de_like(evento, self._like_total)
            if traduzido is None:
                return
            self._like_total = traduzido.like_total
            self.queue.put(traduzido)

        @client.on(FollowEvent)
        async def _seguiu(evento: Any) -> None:
            self.queue.put(evento_de_presenca(evento, EventType.FOLLOW))

        @client.on(ShareEvent)
        async def _compartilhou(evento: Any) -> None:
            self.queue.put(evento_de_presenca(evento, EventType.SHARE))

        @client.on(JoinEvent)
        async def _entrou(evento: Any) -> None:
            self.queue.put(evento_de_presenca(evento, EventType.JOIN))
