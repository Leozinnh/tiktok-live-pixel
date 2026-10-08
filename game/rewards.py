"""Quanto cada interacao da audiencia vale em pixels.

Esta e a economia do jogo, e ela precisa ser previsivel: a pessoa manda uma
rosa, ve "+1 PIXEL" na tela, e entende a regra sem ninguem explicar. Se o mesmo
presente valesse 1 hoje e 3 amanha, a unica leitura possivel seria "esse jogo e
aleatorio", e ninguem manda a segunda rosa.

Tudo aqui e funcao pura ou quase: dado um evento, quantos pixels. Quem gasta,
guarda e pinta e o pipeline.

Os dois limites existem por causa da TELA, nao do dinheiro:

- `max_multiplicador` — um streak de 500 rosas nao pode virar 500 pixels de uma
  vez. O presente vale o que vale; o streak tem teto.
- `max_pixels` nas curtidas — uma like-bomb nao pode pintar o canvas inteiro e
  apagar o que a sala passou a hora construindo.

Curiosidade que vira bug se alguem "otimizar": `pixels_do_evento` recusa
qualquer evento sem autor. A biblioteca do TikTok omite o campo `user` quando
alguem curte demais na mesma sala, e creditar isso para "desconhecido" criaria
um usuario fantasma que apareceria no ranking sem nunca ter existido.
"""

from collections import defaultdict

from core.events import EventType, LiveEvent
from game.colors import achatar

POR_PIXEL_PADRAO = 50
MAX_CURTIDAS_PADRAO = 10
MULTIPLICADOR_PADRAO = 10
PRESENTE_DESCONHECIDO_PADRAO = 1


def _inteiro(valor, padrao: int) -> int:
    """Converte o que vier (None, "", "3", 3.0) num inteiro utilizavel."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return padrao


class AcumuladorCurtidas:
    """Converte curtidas em pixels, sem perder o troco.

    Cinquenta curtidas valem um pixel. Mas ninguem curte de cinquenta em
    cinquenta: a biblioteca manda um evento por curtida, cada um com delta 1.
    Sem guardar o resto, quem curte 49 vezes nao ganha nada — e a regra "50
    curtidas = 1 pixel" seria mentira na pratica.

    O resto e por pessoa: as 19 curtidas de uma nao completam as 19 de outra.
    """

    def __init__(self, por_pixel: int = POR_PIXEL_PADRAO, maximo: int = MAX_CURTIDAS_PADRAO):
        if por_pixel < 1:
            raise ValueError(f"Curtidas por pixel precisa ser >= 1 (recebi {por_pixel}).")

        self.por_pixel = por_pixel
        self.maximo = max(0, maximo)
        self._resto: dict[str, int] = defaultdict(int)

    @classmethod
    def do_config(cls, cfg: dict) -> "AcumuladorCurtidas":
        like = (cfg.get("rewards") or {}).get("like") or {}
        return cls(
            por_pixel=_inteiro(like.get("curtidas_por_pixel"), POR_PIXEL_PADRAO),
            maximo=_inteiro(like.get("max_pixels"), MAX_CURTIDAS_PADRAO),
        )

    def creditar(self, handle: str, curtidas) -> int:
        """Soma as curtidas e devolve os pixels inteiros que sairam agora."""
        chave = (handle or "").strip().lstrip("@").lower()
        quantidade = _inteiro(curtidas, 0)

        if not chave or quantidade <= 0:
            return 0

        total = self._resto[chave] + quantidade
        self._resto[chave] = total % self.por_pixel

        # O excedente do teto e descartado de proposito: o teto existe para
        # cortar a rajada, nao para guarda-la e soltar depois.
        return min(total // self.por_pixel, self.maximo)


def _base_do_presente(nome: str, premios: dict) -> int:
    """Quanto vale um presente, pela tabela do config ou pelo padrao."""
    tabela = premios.get("gifts") or {}
    padrao = _inteiro(premios.get("presente_desconhecido"), PRESENTE_DESCONHECIDO_PADRAO)

    if not nome:
        return padrao

    if nome in tabela:
        return _inteiro(tabela[nome], padrao)

    # Tolera "rose", "ROSE " e "Rose": e o mesmo presente, e a pessoa que
    # mandou nao escolheu como o nome chega aqui.
    alvo = achatar(nome)
    for chave, valor in tabela.items():
        if achatar(chave) == alvo:
            return _inteiro(valor, padrao)

    return padrao


def pixels_do_evento(
    evento: LiveEvent,
    cfg: dict,
    curtidas: AcumuladorCurtidas | None = None,
) -> int:
    """Quantos pixels este evento concede. Zero para o que nao paga."""
    if not evento.handle():
        return 0

    premios = cfg.get("rewards") or {}
    tipo = evento.type

    if tipo == EventType.GIFT:
        base = _base_do_presente(evento.gift_name, premios)
        quantidade = max(1, _inteiro(evento.quantity, 1))
        teto = max(1, _inteiro(premios.get("max_multiplicador"), MULTIPLICADOR_PADRAO))
        return base * min(quantidade, teto)

    if tipo == EventType.LIKE:
        if curtidas is None:
            return 0
        return curtidas.creditar(evento.handle(), evento.like_delta)

    if tipo == EventType.FOLLOW:
        return _inteiro((premios.get("follow") or {}).get("pixels"), 0)

    if tipo == EventType.SHARE:
        return _inteiro((premios.get("share") or {}).get("pixels"), 0)

    # Comentario pinta, nao credita: se comentar desse pixel, o canvas seria
    # escrito de graca e a rosa perderia o sentido.
    return 0
