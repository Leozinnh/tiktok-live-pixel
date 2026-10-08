"""As regras de pintura.

Este e o unico caminho pelo qual um pixel nasce. Nada mais escreve no canvas:
nem o pipeline, nem o WebSocket, nem o painel de teste — todos chamam `pintar`.
Concentrar a regra aqui e o que permite mudar o preco, a politica de
sobrescrita ou o rate limit sem tocar em mais nada.

A ordem das checagens e deliberada e importa:

1. Coordenada — e o motivo que a pessoa le na tela.
2. Saldo — barato, e evita que alguem sem pixels queime o cooldown.
3. Rate limit — so gasta o relogio de quem realmente ia pintar.

O saldo so e tocado depois das tres. Qualquer recusa sai daqui sem cobrar
nada e sem escrever no canvas.

A quarta regra e sobre o LOTE. `pintar_lote` pinta muitas celulas como UMA
acao da pessoa: o comentario "A2, B2, C3..." e um pedido, nao tres, e o
cooldown e do pedido. As tres checagens continuam valendo celula a celula — o
que muda e so o relogio, que bate uma vez. Ver `_Relogio`.
"""

from dataclasses import dataclass
from typing import Iterable

from backend.database import Database
from core.ratelimit import RateLimiter
from game.canvas import CanvasModel, Celula
from game.coordinates import Coordenada
from game.inventory import Inventario

MOTIVO_OK = "ok"
MOTIVO_SALDO = "saldo_insuficiente"
MOTIVO_COORDENADA = "coordenada_invalida"
MOTIVO_RATE = "rate_limit"

CUSTO_VIRGEM = 1
CUSTO_SOBRESCRITA = 2

# O XP nao e o custo. O preco existe para segurar vandalismo; o XP existe para
# recompensar quem esta construindo. Sobrescrever da mais XP porque custou mais
# — a pessoa abriu mao de dois pixels por aquele espaco.
XP_VIRGEM = 10
XP_SOBRESCRITA = 15

RESULTADO_OK = "ok"
RESULTADO_RECUSADO = "recusado"

CHAVE_RATE = "pintar"


@dataclass(slots=True)
class _Relogio:
    """O tique de cooldown de um LOTE de pinturas.

    O cooldown existe para uma pessoa nao monopolizar o quadro — nao para
    racionar pixel que ela ja pagou. Entao quem manda "A2, B2, C3..." num
    comentario passou pelo portao UMA vez: o tique e do comentario, e as
    celulas seguintes pegam a porteira aberta.

    O tique so sai quando um pixel sai de verdade. Saldo e coordenada sao
    checados antes, entao quem foi recusado por falta de saldo continua com a
    vez na mao para quando tiver como pagar.
    """

    autorizado: bool = False


@dataclass(slots=True)
class ResultadoPintura:
    """O que aconteceu com uma tentativa de pintura.

    `custo` e o que foi COBRADO (zero numa recusa); `necessario` e o que
    teria custado. Quem foi recusado por saldo precisa do segundo numero
    para saber quanto falta.
    """

    ok: bool
    motivo: str
    custo: int = 0
    necessario: int = 0
    xp: int = 0
    celula: Celula | None = None
    sobrescrita: bool = False
    dono_anterior: str | None = None


def motivo_legivel(motivo: str) -> str:
    """Texto para o HUD. O motivo cru fica no log; isto vai para a tela."""
    return {
        MOTIVO_OK: "",
        MOTIVO_SALDO: "SEM PIXELS — MANDE UMA ROSA 🌹",
        MOTIVO_COORDENADA: "COORDENADA FORA DO MAPA",
        MOTIVO_RATE: "CALMA! ESPERE 2 SEGUNDOS",
    }.get(motivo, "NAO DEU PARA PINTAR")


class ServicoPintura:
    """Aplica a regra de pintura e registra tudo o que tentou acontecer."""

    def __init__(
        self,
        canvas: CanvasModel,
        inventario: Inventario,
        db: Database,
        limiter: RateLimiter | None = None,
        cooldown: float = 0.0,
        custo_virgem: int = CUSTO_VIRGEM,
        custo_sobrescrita: int = CUSTO_SOBRESCRITA,
        xp_virgem: int = XP_VIRGEM,
        xp_sobrescrita: int = XP_SOBRESCRITA,
    ):
        self.canvas = canvas
        self.inventario = inventario
        self.db = db
        self.limiter = limiter
        self.cooldown = cooldown
        self.custo_virgem = custo_virgem
        self.custo_sobrescrita = custo_sobrescrita
        self.xp_virgem = xp_virgem
        self.xp_sobrescrita = xp_sobrescrita

    # ------------------------------------------------------------------
    # O caminho unico
    # ------------------------------------------------------------------

    async def pintar(
        self,
        handle: str,
        x: int,
        y: int,
        cor: str,
        efeito: str | None = None,
    ) -> ResultadoPintura:
        """Uma celula. Equivale a um lote de um."""
        return await self._tentar(handle, x, y, cor, efeito, _Relogio())

    async def pintar_lote(
        self,
        handle: str,
        coordenadas: Iterable[Coordenada],
        cor: str,
        efeito: str | None = None,
    ) -> list[ResultadoPintura]:
        """Uma lista de celulas como UMA acao da pessoa.

        Um resultado por celula, na ordem pedida. Quando o saldo acaba no meio,
        as primeiras pintam, as ultimas sao recusadas, e nada e cobrado duas
        vezes — quem chama decide o que dizer a respeito.
        """
        relogio = _Relogio()

        resultados: list[ResultadoPintura] = []
        for coordenada in coordenadas:
            resultados.append(
                await self._tentar(handle, coordenada.x, coordenada.y, cor, efeito, relogio)
            )
        return resultados

    async def _tentar(
        self,
        handle: str,
        x: int,
        y: int,
        cor: str,
        efeito: str | None,
        relogio: _Relogio,
    ) -> ResultadoPintura:
        handle = (handle or "").strip().lstrip("@").lower()

        # 1. A coordenada existe?
        celula = self.canvas.celula(x, y)
        if celula is None:
            return await self._recusar(handle, x, y, cor, MOTIVO_COORDENADA)

        dono_anterior = celula.owner_id if celula.pintada else None
        sobrescrita = dono_anterior is not None and dono_anterior != handle
        custo = self.custo_sobrescrita if sobrescrita else self.custo_virgem

        # 2. Tem como pagar?
        if self.inventario.saldo(handle) < custo:
            return await self._recusar(
                handle, x, y, cor, MOTIVO_SALDO, custo, sobrescrita, dono_anterior
            )

        # 3. Esta na hora? A pergunta e feita uma vez por lote, e nao uma vez
        # por celula — ver `_Relogio`.
        if not relogio.autorizado:
            if not self._pode_agora(handle):
                return await self._recusar(
                    handle, x, y, cor, MOTIVO_RATE, custo, sobrescrita, dono_anterior
                )
            relogio.autorizado = True

        # Daqui para baixo nada mais pode falhar sem cobrar: o saldo ja saiu.
        self.inventario.gastar(handle, custo)
        pintada = self.canvas.pintar(x, y, cor, handle, efeito)

        await self.db.salvar_pixel(
            x, y, cor, handle, efeito, painted_at=pintada.painted_at
        )
        await self.db.registrar_historico(
            x, y, cor, handle, efeito, painted_at=pintada.painted_at
        )
        # `pixels_painted` conta CELULAS; o XP tem tabela propria, mais generosa
        # na sobrescrita. Um ranking por celulas premia quem cobre area; o XP
        # premia quem disputa terreno caro.
        xp = self.xp_sobrescrita if sobrescrita else self.xp_virgem
        await self.db.contabilizar_pintura(
            handle, pixels=1, sobrescrita=sobrescrita, xp=xp
        )

        if sobrescrita and dono_anterior:
            await self.db.registrar_perda(dono_anterior)

        await self.db.registrar_acao(
            handle, x, y, cor, custo, sobrescrita, RESULTADO_OK, None
        )

        return ResultadoPintura(
            ok=True,
            motivo=MOTIVO_OK,
            custo=custo,
            necessario=custo,
            xp=xp,
            celula=pintada,
            sobrescrita=sobrescrita,
            dono_anterior=dono_anterior,
        )

    # ------------------------------------------------------------------
    # Interno
    # ------------------------------------------------------------------

    def _pode_agora(self, handle: str) -> bool:
        if self.limiter is None or self.cooldown <= 0:
            return True
        # Cooldown da REGRA fica em zero de proposito: a camada 1 e global
        # por `rule_key`, entao usa-la aqui deixaria a primeira pintura da
        # sala bloqueando a de todo mundo pelos proximos 2 segundos. O
        # limite que queremos e o da camada 2, por pessoa.
        return self.limiter.allow_rule(CHAVE_RATE, 0.0, handle, self.cooldown)

    async def _recusar(
        self,
        handle: str,
        x: int,
        y: int,
        cor: str,
        motivo: str,
        custo: int = 0,
        sobrescrita: bool = False,
        dono_anterior: str | None = None,
    ) -> ResultadoPintura:
        await self.db.registrar_acao(
            handle, x, y, cor, custo, sobrescrita, RESULTADO_RECUSADO, motivo
        )
        return ResultadoPintura(
            ok=False,
            motivo=motivo,
            custo=0,
            necessario=custo,
            celula=None,
            sobrescrita=sobrescrita,
            dono_anterior=dono_anterior,
        )
