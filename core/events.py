from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Tipos de evento que o nucleo entende.

    Herda de str para que EventType.GIFT == "gift", o que mantem
    comparacoes e serializacao simples.
    """

    COMMENT = "comment"
    GIFT = "gift"
    LIKE = "like"
    FOLLOW = "follow"
    SHARE = "share"
    SYSTEM = "system"


@dataclass(slots=True)
class LiveEvent:
    """Formato interno da aplicacao.

    O adapter converte o evento externo para este formato. Nada fora do
    adapter le o campo `raw`, o que impede o formato do TikTok de vazar
    para o resto do sistema. Trocar o TikTok por outra fonte (YouTube,
    Twitch, o painel de teste) nao muda nada abaixo desta camada.
    """

    type: EventType
    username: str = ""
    display_name: str = ""
    text: str = ""
    gift_name: str = ""
    gift_id: str | None = None
    quantity: int = 1
    like_delta: int = 0
    like_total: int = 0
    raw: Any = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def actor(self) -> str:
        """Nome de exibicao para a tela. Nunca retorna a string 'None'."""
        return self.display_name or self.username or "desconhecido"

    def handle(self) -> str:
        """Identificador estavel e minusculo do autor.

        E a chave de identidade do usuario no banco e a semente da cor
        automatica. Cai para o display_name quando o unique_id nao veio,
        para que um espectador sem handle ainda tenha identidade propria.
        """
        return (self.username or self.display_name or "").strip().lower()
