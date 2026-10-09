"""Os eventos automaticos da LIVE.

De tempo em tempo o jogo ANUNCIA alguma coisa e muda a regra por alguns
segundos. E o que faz a tela continuar viva quando ninguem esta mandando
nada — e o que da a quem esta so olhando um motivo para mandar a proxima
rosa ("falta 8 segundos de TURBO").

O agendador NAO pinta nada. Ele so decide QUANDO e quanto vale; quem pinta
continua sendo o `ServicoPintura`. O unico numero que sai daqui e o
multiplicador, que o pipeline le a cada evento.

Quem escuta o agendador: o telao (banner e efeito, pelo `publicar`), o
pipeline (o multiplicador) e a VOZ — o `estado` liga o `event_start` e o
`event_end` ao narrador, que anuncia o evento pelo alto-falante.

O relogio entra por parametro (`agora_fn`). Isso e o que permite testar uma
janela de 60 segundos sem esperar 60 segundos — e o que garante que o teste
nao fica lento nem instavel.
"""

import logging
import random
import time
from typing import Callable

logger = logging.getLogger(__name__)

# O catalogo do spec §13. `weight` e o peso do sorteio: TURBO e HORA DO PIXEL
# aparecem mais porque sao os que dao mais pixel, e evento que da pixel e o
# que faz a audiencia mandar presente.
CATALOGO_PADRAO = (
    {
        "key": "hora_do_pixel",
        "name": "HORA DO PIXEL",
        "emoji": "🎨",
        "duration": 30.0,
        "multiplier": 2.0,
        "weight": 3.0,
        "effect": "brilho",
    },
    {
        "key": "arco_iris",
        "name": "ARCO-ÍRIS",
        "emoji": "🌈",
        "duration": 60.0,
        "multiplier": 1.0,
        "weight": 2.0,
        "effect": "arco_iris",
    },
    {
        "key": "pixel_turbo",
        "name": "PIXEL TURBO",
        "emoji": "⚡",
        "duration": 30.0,
        "multiplier": 3.0,
        "weight": 3.0,
        "effect": "rastro",
    },
    {
        "key": "caos",
        "name": "CAOS",
        "emoji": "💥",
        "duration": 20.0,
        "multiplier": 1.5,
        "weight": 1.0,
        "effect": "caos",
    },
    {
        "key": "desafio",
        "name": "DESAFIO",
        "emoji": "🎯",
        "duration": 45.0,
        "multiplier": 1.0,
        "weight": 1.0,
        "effect": "desafio",
    },
    {
        "key": "tempestade",
        "name": "TEMPESTADE",
        "emoji": "⛈️",
        "duration": 25.0,
        "multiplier": 2.0,
        "weight": 1.5,
        "effect": "tempestade",
    },
    {
        "key": "codigo",
        "name": "CHUVA DE CÓDIGO",
        "emoji": "👾",
        "duration": 40.0,
        "multiplier": 1.0,
        "weight": 1.5,
        "effect": "codigo",
    },
    {
        "key": "negativo",
        "name": "NEGATIVO",
        "emoji": "🔄",
        "duration": 30.0,
        "multiplier": 1.5,
        "weight": 1.5,
        "effect": "negativo",
    },
    {
        "key": "fogos",
        "name": "FOGOS",
        "emoji": "🎆",
        "duration": 35.0,
        "multiplier": 2.0,
        "weight": 1.5,
        "effect": "fogos",
    },
    {
        "key": "neve",
        "name": "NEVE",
        "emoji": "❄️",
        "duration": 40.0,
        "multiplier": 1.5,
        "weight": 1.5,
        "effect": "neve",
    },
    {
        "key": "arcade",
        "name": "ARCADE",
        "emoji": "🕹️",
        "duration": 30.0,
        "multiplier": 2.0,
        "weight": 1.5,
        "effect": "arcade",
    },
    {
        "key": "filme",
        "name": "FILME ANTIGO",
        "emoji": "🎞️",
        "duration": 40.0,
        "multiplier": 1.5,
        "weight": 1.5,
        "effect": "filme",
    },
)

INTERVALO_PADRAO = 180.0
PRIMEIRO_EM_PADRAO = 75.0

# A folga do intervalo entre eventos: +-25%. Um relogio cravado vira
# metronomo — a audiencia decora o horario e para de prestar atencao na
# espera. O sorteio do intervalo usa a mesma semente do sorteio do evento,
# entao o teste continua deterministico.
JITTER_DO_INTERVALO = 0.25


def _catalogo(bruto) -> tuple[dict, ...]:
    """Normaliza o catalogo vindo da config, ou usa o padrao."""
    if not bruto:
        return CATALOGO_PADRAO

    saida = []
    for item in bruto:
        if not item.get("key"):
            continue
        saida.append(
            {
                "key": str(item["key"]),
                "name": str(item.get("name") or item["key"]).upper(),
                "emoji": str(item.get("emoji") or "🎉"),
                "duration": max(1.0, float(item.get("duration") or 30.0)),
                "multiplier": max(1.0, float(item.get("multiplier") or 1.0)),
                "weight": max(0.0, float(item.get("weight") or 1.0)),
                "effect": item.get("effect"),
            }
        )

    return tuple(saida) or CATALOGO_PADRAO


class SchedulerEventos:
    """Decide quando comeca e quando termina cada evento da LIVE."""

    def __init__(
        self,
        cfg: dict | None = None,
        agora_fn: Callable[[], float] | None = None,
        publicar: Callable[[dict], None] | None = None,
        seed: int | None = None,
    ):
        eventos_cfg = ((cfg or {}).get("events") or (cfg or {}).get("eventos") or {})

        self.catalogo = _catalogo(eventos_cfg.get("catalog"))
        self.por_chave = {e["key"]: e for e in self.catalogo}
        # O freio de mao. Desliga o SORTEIO, nao o agendador: `forcar` continua
        # valendo, senao nao haveria como voltar atras sem reiniciar o servidor
        # no meio da LIVE.
        self.sorteia = bool(eventos_cfg.get("active", True))
        self.intervalo = max(
            1.0, float(eventos_cfg.get("interval") or INTERVALO_PADRAO)
        )
        self.primeiro_em = max(
            0.0, float(eventos_cfg.get("first_after") or PRIMEIRO_EM_PADRAO)
        )

        self.agora = agora_fn or time.monotonic
        self.publicar = publicar or (lambda _msg: None)
        self._sorteio = random.Random(seed)

        self._ativo: dict | None = None
        self._proximo = self.agora() + self.primeiro_em
        # A chave do ultimo evento que comecou (sorteado ou forcado). O
        # sorteio evita repeti-la: dois CAOS seguidos parecem defeito.
        self._ultimo: str | None = None

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    @property
    def ativo(self) -> dict | None:
        return self._ativo

    def multiplicador_pixels(self) -> float:
        """Quanto vale um pixel agora. Fora de evento, 1.0."""
        return float(self._ativo["multiplier"]) if self._ativo else 1.0

    def restante(self) -> float:
        if self._ativo is None:
            return 0.0
        return max(0.0, float(self._ativo["ends_at"]) - self.agora())

    def estado(self) -> dict | None:
        """O evento em curso, na forma que a tela e o painel leem."""
        if self._ativo is None:
            return None
        return {
            "key": self._ativo["key"],
            "name": self._ativo["name"],
            "emoji": self._ativo["emoji"],
            "effect": self._ativo["effect"],
            "multiplier": self._ativo["multiplier"],
            "duration": self._ativo["duration"],
            "remaining": round(self.restante(), 1),
        }

    # ------------------------------------------------------------------
    # O relogio
    # ------------------------------------------------------------------

    def tick(self) -> None:
        """Avanca o relogio. Chamado uma vez por quadro; nunca levanta."""
        try:
            self._tick()
        except Exception:
            # O laco do jogo nao pode morrer por causa do agendador.
            logger.exception("Falha no agendador de eventos")

    def _tick(self) -> None:
        agora = self.agora()

        if self._ativo is not None:
            if agora >= self._ativo["ends_at"]:
                self._encerrar()
            return

        if agora >= self._proximo:
            if not self.sorteia:
                # Desligado pelo painel: empurra a tentativa em vez de
                # sortear, para que religar nao dispare um evento acumulado.
                self._proximo = agora + self.intervalo
                return

            escolhido = self._sortear()
            if escolhido is not None:
                self._comecar(escolhido)
            else:
                # Catalogo vazio ou todo mundo com peso zero: nao trava, so
                # empurra a proxima tentativa.
                self._proximo = agora + self.intervalo

    # ------------------------------------------------------------------
    # Controle
    # ------------------------------------------------------------------

    def forcar(self, chave: str) -> dict | None:
        """Comeca um evento agora, pelo nome. `None` se a chave nao existe."""
        definicao = self.por_chave.get(chave)
        if definicao is None:
            return None

        if self._ativo is not None:
            self._encerrar()

        return self._comecar(definicao)

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _sortear(self) -> dict | None:
        candidatos = [e for e in self.catalogo if e["weight"] > 0]
        if not candidatos:
            return None

        # Nada de repetir o anterior, quando ha alternativa: o sorteio e com
        # reposicao, e sem esta poda o mesmo evento sair duas vezes seguidas
        # com a frequencia que a matematica manda — e na tela isso le como
        # "so tem esse evento hoje".
        if self._ultimo is not None:
            outros = [e for e in candidatos if e["key"] != self._ultimo]
            if outros:
                candidatos = outros

        pesos = [e["weight"] for e in candidatos]
        return self._sorteio.choices(candidatos, weights=pesos, k=1)[0]

    def _espera(self) -> float:
        """O intervalo ate o proximo evento, com a folga do metronomo."""
        return self.intervalo * (
            1.0 + JITTER_DO_INTERVALO * (2.0 * self._sorteio.random() - 1.0)
        )

    def _comecar(self, definicao: dict) -> dict:
        agora = self.agora()
        ends_at = agora + definicao["duration"]

        self._ativo = {**definicao, "ends_at": ends_at}
        self._proximo = ends_at + self._espera()
        self._ultimo = definicao["key"]

        aviso = {
            "type": "event_start",
            "key": definicao["key"],
            "name": definicao["name"],
            "emoji": definicao["emoji"],
            "effect": definicao["effect"],
            "multiplier": definicao["multiplier"],
            "duration": definicao["duration"],
        }
        self.publicar(aviso)
        logger.info("Evento no ar: %s %s", definicao["emoji"], definicao["name"])

        return {
            "key": definicao["key"],
            "name": definicao["name"],
            "ends_at": round(ends_at, 3),
        }

    def _encerrar(self) -> None:
        if self._ativo is None:
            return

        # O nome vai junto no aviso de fim: quem le e a VOZ (o narrador
        # anuncia "o ARCO-IRIS acabou"), e ela so tem esta mensagem para
        # saber de que evento se trata — a chave crua nao se pronuncia.
        chave = self._ativo["key"]
        nome = self._ativo["name"]
        emoji = self._ativo["emoji"]
        self._ativo = None
        self._proximo = self.agora() + self._espera()

        self.publicar({"type": "event_end", "key": chave, "name": nome, "emoji": emoji})
        logger.info("Evento encerrado: %s", chave)
