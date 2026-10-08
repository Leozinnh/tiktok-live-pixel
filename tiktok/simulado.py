"""A fonte de eventos do MODO TESTE.

Isto e o que permite construir, testar e demonstrar o jogo inteiro sem
nenhuma LIVE aberta — e, mais tarde, ensaiar uma demonstracao sem depender
de ter audiencia.

O ponto importante e que ele NAO e um atalho. Ele escreve `LiveEvent` na
mesma `EventQueue` que o adapter real, e o resto do jogo nao sabe qual dos
dois esta do outro lado. Um bug que aparece aqui e um bug do jogo.

O `seed` existe porque um teste que falha so as vezes e um teste que ninguem
conserta: com a mesma semente, a mesma turma e a mesma rajada.
"""

import random
import zlib

from core.event_queue import EventQueue
from core.events import EventType, LiveEvent
from game.coordinates import rotulo_de
from tiktok.base import AdapterStatus

# Handles plausiveis. Nao sao pessoas reais: sao nomes de teste, e a lista
# nunca deve casar com a de ninguem de verdade.
POOL_DE_NOMES = (
    "ana_pixel",
    "bruno_art",
    "carla.draws",
    "duda_ink",
    "edu_arts",
    "fer.pinta",
    "gabi_neon",
    "hugo_craft",
    "iris_cores",
    "joao_px",
    "kaká_art",
    "lari_draw",
    "marcos_8bit",
    "nina_pixel",
    "otto_hue",
    "paula_rgb",
    "queila_art",
    "rafa_neon",
    "sara_dots",
    "tiago_px",
    "ursula_ink",
    "vitor_art",
    "wanda_cores",
    "xuxu_pixel",
    "yuri_draw",
    "zeca_8bit",
    "bia_pinta",
    "caio_neon",
    "dora_art",
    "enzo_px",
    "flor_ink",
    "gael_draw",
    "helo_cores",
    "igor_pixel",
    "juju_art",
    "kira_neon",
    "luan_px",
    "mia_draw",
    "noah_ink",
    "olga_art",
    "pedro_px",
    "quirino.art",
    "rita_neon",
    "sonia_draw",
    "teo_pixel",
    "uma_cores",
    "vera_ink",
    "will_art",
    "xenia_px",
    "zoe_draw",
)

# Conversa de chat comum. Serve para exercitar o caminho em que o jogo
# precisa ficar QUIETO — quem nao tentou pintar nao pode receber "nao entendi".
CONVERSA = (
    "oi",
    "bom dia",
    "hahaha",
    "que legal",
    "como pinta?",
    "manda uma rosa",
    "isso ficou incrivel",
    "boa noite gente",
    "kkkkk",
    "top demais",
    "vou mandar presente",
    "quem ta pintando?",
)

# Tentativas que o parser RECUSA e que ainda assim merecem resposta, porque
# quem escreveu estava claramente tentando pintar.
TENTATIVAS_ERRADAS = ("A51", "AA5", "1H", "Z99", "H", "ABC", "H5 legal!")

CORES = ("vermelho", "verde", "azul", "roxo", "rosa", "amarelo")


def nomes_de_teste(quantos: int, seed: int | None = None) -> list[str]:
    """`quantos` handles distintos, estaveis para uma mesma semente.

    Pedir mais do que o pool tem nao explode: os excedentes ganham um sufixo
    numerico, para que o ranking nunca misture duas pessoas numa ficha so.
    """
    if quantos <= 0:
        return []

    sorteio = random.Random(seed)
    tamanho = len(POOL_DE_NOMES)

    if quantos <= tamanho:
        return sorteio.sample(POOL_DE_NOMES, quantos)

    saida = list(POOL_DE_NOMES)
    for i in range(quantos - tamanho):
        saida.append(f"{POOL_DE_NOMES[i % tamanho]}{i // tamanho + 2}")
    sorteio.shuffle(saida)
    return saida


def _id_do_presente(nome: str) -> str:
    """Id estavel por nome.

    O `gift_id` entra na tabela `gifts`; se dois eventos do mesmo presente
    gravassem ids diferentes, o relatorio de presentes viraria uma bagunca.
    `crc32` em vez de `hash()` porque o hash de string muda a cada processo.
    """
    return str(zlib.crc32(nome.encode("utf-8")))


class SimuladorLive:
    """Fonte de eventos falsa, com a mesma interface do adapter real."""

    def __init__(
        self,
        queue: EventQueue,
        config: dict | None = None,
        nomes: list[str] | None = None,
        seed: int | None = None,
    ):
        cfg = config or {}
        canvas = cfg.get("canvas") or {}
        premios = cfg.get("rewards") or {}

        self.queue = queue
        self.cols = max(1, int(canvas.get("cols") or 26))
        self.rows = max(1, int(canvas.get("rows") or 51))
        self.presentes = list((premios.get("gifts") or {"Rose": 1}).keys())

        self._sorteio = random.Random(seed)
        self._nomes = list(nomes) if nomes else nomes_de_teste(24, seed=seed)
        if not self._nomes:
            self._nomes = ["espectador"]

        self._status = AdapterStatus()
        self._like_total = 0
        self._ordem: list[int] = []

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    @property
    def status(self) -> AdapterStatus:
        return self._status

    def start(self) -> None:
        self._status = AdapterStatus(connected=True, detail="MODO TESTE — sem LIVE")

    def stop(self) -> None:
        self._status = AdapterStatus(connected=False, detail="encerrado")

    # ------------------------------------------------------------------
    # Eventos individuais
    # ------------------------------------------------------------------

    def comentar(self, username: str, texto: str, display_name: str | None = None) -> LiveEvent:
        """`display_name=None` inventa um apelido; `display_name=""` deixa o
        evento sem apelido nenhum, que e como se testa o fallback para o
        handle — no TikTok real, nem todo mundo tem nickname."""
        evento = LiveEvent(
            type=EventType.COMMENT,
            username=_limpar(username),
            display_name=_rotulo(username) if display_name is None else display_name,
            text=texto,
        )
        self.queue.put(evento)
        return evento

    def presentear(
        self, username: str, gift_name: str = "Rose", quantity: int = 1
    ) -> LiveEvent:
        nome = gift_name or "Rose"
        evento = LiveEvent(
            type=EventType.GIFT,
            username=_limpar(username),
            display_name=_rotulo(username),
            gift_name=nome,
            gift_id=_id_do_presente(nome),
            quantity=max(1, int(quantity)),
        )
        self.queue.put(evento)
        return evento

    def curtir(self, username: str, quantidade: int = 1) -> LiveEvent:
        delta = max(0, int(quantidade))
        self._like_total += delta
        evento = LiveEvent(
            type=EventType.LIKE,
            username=_limpar(username),
            display_name=_rotulo(username),
            like_delta=delta,
            like_total=self._like_total,
        )
        self.queue.put(evento)
        return evento

    def seguir(self, username: str) -> LiveEvent:
        evento = LiveEvent(
            type=EventType.FOLLOW,
            username=_limpar(username),
            display_name=_rotulo(username),
        )
        self.queue.put(evento)
        return evento

    def compartilhar(self, username: str) -> LiveEvent:
        evento = LiveEvent(
            type=EventType.SHARE,
            username=_limpar(username),
            display_name=_rotulo(username),
        )
        self.queue.put(evento)
        return evento

    def entrar(self, username: str) -> LiveEvent:
        evento = LiveEvent(
            type=EventType.JOIN,
            username=_limpar(username),
            display_name=_rotulo(username),
        )
        self.queue.put(evento)
        return evento

    # ------------------------------------------------------------------
    # Rajada
    # ------------------------------------------------------------------

    def rajada(self, quantos: int, modo: str = "misto") -> list[LiveEvent]:
        """`quantos` eventos de uma vez.

        `modo="pintura"` manda so coordenadas validas, varrendo o canvas em
        ordem embaralhada — e assim que se enche a tela rapido para ver como
        o desenho fica. `modo="misto"` reproduz o que uma LIVE de verdade
        manda: muita conversa, alguns presentes, curtidas e coordenadas.
        """
        if quantos <= 0:
            return []

        if modo == "pintura":
            return [self._de_pintura(i) for i in range(quantos)]

        return [self._aleatorio() for _ in range(quantos)]

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _de_pintura(self, indice: int) -> LiveEvent:
        """Varre o canvas em ordem embaralhada, sem repetir antes de esgotar.

        Embaralhar de verdade (e nao sortear com reposicao) e o que garante
        que 400 eventos cubram 400 celulas distintas em vez de amontoar num
        canto e deixar o resto vazio.
        """
        total = self.cols * self.rows
        if indice % total == 0:
            ordem = list(range(total))
            self._sorteio.shuffle(ordem)
            self._ordem = ordem

        celula = self._ordem[indice % total]
        x, y = celula % self.cols, celula // self.cols

        return self.comentar(self._sorteio.choice(self._nomes), rotulo_de(x, y))

    def _aleatorio(self) -> LiveEvent:
        nome = self._sorteio.choice(self._nomes)
        dado = self._sorteio.random()

        if dado < 0.55:
            return self.comentar(nome, self._texto_de_chat())

        if dado < 0.72:
            return self.presentear(
                nome,
                self._sorteio.choice(self.presentes),
                self._sorteio.choice((1, 1, 1, 2, 3, 5, 10)),
            )

        if dado < 0.86:
            return self.curtir(nome, self._sorteio.choice((1, 3, 5, 10, 20, 50)))

        if dado < 0.95:
            return self.seguir(nome)

        return self.compartilhar(nome)

    def _texto_de_chat(self) -> str:
        dado = self._sorteio.random()

        # A maioria de quem escreve num jogo de pintar esta tentando pintar.
        if dado < 0.6:
            x = self._sorteio.randrange(self.cols)
            y = self._sorteio.randrange(self.rows)
            return rotulo_de(x, y)

        if dado < 0.72:
            return f"/cor {self._sorteio.choice(CORES)}"

        if dado < 0.82:
            return self._sorteio.choice(TENTATIVAS_ERRADAS)

        return self._sorteio.choice(CONVERSA)


# --------------------------------------------------------------------------
# Auxiliares
# --------------------------------------------------------------------------


def _limpar(username: str) -> str:
    return (username or "").strip().lstrip("@").lower()


def _rotulo(username: str) -> str:
    """Nome de exibicao de teste: o handle com a primeira letra maiuscula."""
    limpo = _limpar(username)
    return limpo[:1].upper() + limpo[1:] if limpo else "Espectador"
