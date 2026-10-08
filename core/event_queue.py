import logging
import queue

from core.events import LiveEvent

logger = logging.getLogger(__name__)


class EventQueue:
    """Fila thread-safe entre o adapter e o loop do jogo.

    O adapter escreve de outra thread (ele tem o proprio loop asyncio); o
    servidor consome no loop do uvicorn. Nenhum estado de jogo e
    compartilhado entre as duas threads.
    """

    def __init__(self, maxsize: int = 5000):
        self._queue: queue.Queue[LiveEvent] = queue.Queue(maxsize=maxsize)
        self._dropped = 0
        self._accepted = 0

    def put(self, event: LiveEvent) -> None:
        """Enfileira sem nunca bloquear a thread do adapter."""
        try:
            self._queue.put_nowait(event)
            self._accepted += 1
            return
        except queue.Full:
            pass

        # Fila cheia: descarta o MAIS ANTIGO. Num jogo ao vivo o evento
        # recente vale mais que o antigo.
        try:
            self._queue.get_nowait()
            self._queue.put_nowait(event)
            self._accepted += 1
        except queue.Empty:
            pass
        except queue.Full:
            pass
        self._dropped += 1

    def get_nowait(self) -> LiveEvent | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def drain(self, limit: int) -> list[LiveEvent]:
        """Retira ate `limit` eventos, do mais antigo para o mais novo."""
        lote: list[LiveEvent] = []
        for _ in range(max(0, limit)):
            evento = self.get_nowait()
            if evento is None:
                break
            lote.append(evento)
        return lote

    def size(self) -> int:
        return self._queue.qsize()

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def accepted(self) -> int:
        return self._accepted
