"""O contrato da fonte de eventos.

Tudo o que o jogo sabe sobre "de onde vem um evento" cabe aqui: um `start`,
um `stop`, um status para o HUD e uma `EventQueue` para onde escrever.

Essa e a fronteira que torna o MODO TESTE possivel. `TikTokLiveAdapter` e
`SimuladorLive` implementam o mesmo protocolo, e nada abaixo desta camada
sabe qual dos dois esta do outro lado. Se um dia entrar YouTube ou Twitch,
entra por aqui e mais nada muda.

O protocolo e `runtime_checkable` para que o painel de controle possa
perguntar `isinstance(fonte, LiveAdapter)` sem importar as duas classes.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class AdapterStatus:
    """Estado da conexao, exibido no HUD.

    `reconnects` existe porque a diferenca entre "caiu agora" e "caiu dezoito
    vezes na ultima hora" e a diferenca entre um detalhe e um problema.
    """

    connected: bool = False
    detail: str = "desconectado"
    reconnects: int = 0


@runtime_checkable
class LiveAdapter(Protocol):
    """Fonte de eventos. Implementado por TikTokLiveAdapter e SimuladorLive."""

    def start(self) -> None: ...

    def stop(self) -> None: ...

    @property
    def status(self) -> AdapterStatus: ...
