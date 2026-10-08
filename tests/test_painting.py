"""Regras de pintura: quanto custa, quem pode, o que acontece quando nao pode.

A regra central do jogo vive aqui. Pixel virgem custa 1; pixel de outra pessoa
custa 2. Isso permite disputar terreno — a arte coletiva e viva — mas faz o
vandalismo em massa custar caro.

O caso mais importante desta suite e a RECUSA: quando falta saldo, nada pode
ser cobrado e nada pode ser pintado. Uma cobranca parcial, ou uma cobranca sem
pintura, e o tipo de bug que a pessoa so descobre quando ja perdeu os pixels.
"""

import pytest

from backend.database import Database
from core.ratelimit import RateLimiter
from game.canvas import CanvasModel
from game.coordinates import Coordenada, rotulo_de
from game.inventory import Inventario
from game.painting import (
    MOTIVO_COORDENADA,
    MOTIVO_RATE,
    MOTIVO_SALDO,
    ServicoPintura,
)

COLS, ROWS = 26, 51


class Relogio:
    def __init__(self):
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


class Cenario:
    """Canvas + inventario + banco + servico, ja ligados."""

    def __init__(self, canvas, inventario, db, servico):
        self.canvas = canvas
        self.inventario = inventario
        self.db = db
        self.servico = servico

    def creditar(self, handle: str, quantos: int) -> None:
        self.inventario.adicionar(handle, quantos)

    async def pintar_de(self, handle: str, x: int, y: int, cor: str = "#FF0055"):
        """Credita e pinta. Existe para ninguem esquecer o saldo do pintor."""
        self.inventario.adicionar(handle, 5)
        return await self.servico.pintar(handle, x, y, cor)

    async def acoes(self) -> list[dict]:
        async with self.db.conn.execute(
            "SELECT handle, x, y, cost, overwrite, result, reason "
            "FROM paint_actions ORDER BY id"
        ) as cursor:
            return [dict(linha) for linha in await cursor.fetchall()]


async def montar(tmp_path, *, cooldown: float = 0.0, relogio=None) -> Cenario:
    canvas = CanvasModel(COLS, ROWS)
    inventario = Inventario()
    db = Database(tmp_path / "pintura.db")
    await db.abrir()

    limiter = RateLimiter(now_fn=relogio) if relogio is not None else None
    servico = ServicoPintura(canvas, inventario, db, limiter=limiter, cooldown=cooldown)
    return Cenario(canvas, inventario, db, servico)


# --------------------------------------------------------------------------
# Custo
# --------------------------------------------------------------------------


async def test_pixel_virgem_custa_um(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    resultado = await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.db.fechar()
    assert resultado.ok is True
    assert resultado.custo == 1
    assert c.inventario.saldo("joao") == 4


async def test_pixel_de_outro_custa_dois(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 5)

    resultado = await c.servico.pintar("maria", 7, 5, "#00FF00")

    await c.db.fechar()
    assert resultado.ok is True
    assert resultado.custo == 2
    assert c.inventario.saldo("maria") == 3


async def test_repetir_a_propria_cor_custa_um(tmp_path):
    """Pintar por cima de si mesmo nao e disputa, e ajuste."""
    c = await montar(tmp_path)
    c.creditar("joao", 5)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    resultado = await c.servico.pintar("joao", 7, 5, "#FFFFFF")

    await c.db.fechar()
    assert resultado.ok is True
    assert resultado.custo == 1


# --------------------------------------------------------------------------
# Recusa por saldo: NAO pinta e NAO cobra
# --------------------------------------------------------------------------


async def test_saldo_insuficiente_recusa_sem_cobrar(tmp_path):
    """Review Focus: a recusa nao pode custar nada a quem foi recusado."""
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 1)

    resultado = await c.servico.pintar("maria", 7, 5, "#00FF00")

    await c.db.fechar()
    assert resultado.ok is False
    assert resultado.motivo == MOTIVO_SALDO
    assert c.inventario.saldo("maria") == 1


async def test_saldo_insuficiente_nao_altera_o_canvas(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 1)

    await c.servico.pintar("maria", 7, 5, "#00FF00")

    celula = c.canvas.celula(7, 5)
    await c.db.fechar()
    assert celula.color == "#FF0055"
    assert celula.owner_id == "joao"


async def test_recusa_por_saldo_informa_quanto_faltou(tmp_path):
    """Quem foi recusado precisa saber quanto precisava, nao so que falhou."""
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 1)

    resultado = await c.servico.pintar("maria", 7, 5, "#00FF00")

    await c.db.fechar()
    assert resultado.custo == 0
    assert resultado.necessario == 2


async def test_sem_saldo_nenhum_recusa(tmp_path):
    c = await montar(tmp_path)

    resultado = await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.db.fechar()
    assert resultado.ok is False
    assert resultado.motivo == MOTIVO_SALDO


async def test_saldo_exato_e_aceito(tmp_path):
    """O limite nao pode ser conservador: 2 paga uma sobrescrita de 2."""
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 2)

    resultado = await c.servico.pintar("maria", 7, 5, "#00FF00")

    await c.db.fechar()
    assert resultado.ok is True
    assert c.inventario.saldo("maria") == 0


async def test_recusa_nao_grava_celula_no_banco(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 1)

    await c.servico.pintar("maria", 7, 5, "#00FF00")
    carregado = await c.db.carregar_canvas()

    await c.db.fechar()
    assert len(carregado) == 1
    assert carregado[0].owner_id == "joao"


async def test_pintura_bem_sucedida_nao_passa_fome(tmp_path):
    """O saldo tem que sobreviver a varias pinturas seguidas."""
    c = await montar(tmp_path)
    c.creditar("joao", 3)

    assert (await c.servico.pintar("joao", 0, 0, "#FF0055")).ok is True
    assert (await c.servico.pintar("joao", 1, 0, "#FF0055")).ok is True
    assert (await c.servico.pintar("joao", 2, 0, "#FF0055")).ok is True
    quarto = await c.servico.pintar("joao", 3, 0, "#FF0055")

    await c.db.fechar()
    assert quarto.ok is False
    assert c.canvas.preenchidas() == 3


# --------------------------------------------------------------------------
# Coordenada invalida
# --------------------------------------------------------------------------


@pytest.mark.parametrize("x, y", [(-1, 0), (26, 0), (0, 51), (999, 999)])
async def test_coordenada_invalida_recusa_sem_cobrar(tmp_path, x, y):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    resultado = await c.servico.pintar("joao", x, y, "#FF0055")

    await c.db.fechar()
    assert resultado.ok is False
    assert resultado.motivo == MOTIVO_COORDENADA
    assert c.inventario.saldo("joao") == 5


async def test_coordenada_invalida_vem_antes_do_saldo(tmp_path):
    """Sem saldo E fora do canvas: o motivo reportado e a coordenada.

    O motivo e o que a pessoa le na tela. "Fora do mapa" e acionavel;
    "sem pixels" faria ela mandar uma rosa para ganhar um pixel e
    continuar sem entender por que nao pintou.
    """
    c = await montar(tmp_path)

    resultado = await c.servico.pintar("joao", 999, 999, "#FF0055")

    await c.db.fechar()
    assert resultado.motivo == MOTIVO_COORDENADA


# --------------------------------------------------------------------------
# Persistencia da pintura
# --------------------------------------------------------------------------


async def test_pintura_grava_no_historico(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    await c.servico.pintar("joao", 7, 5, "#FF0055")
    historico = await c.db.historico_pixel(7, 5)

    await c.db.fechar()
    assert len(historico) == 1
    assert historico[0]["owner_id"] == "joao"


async def test_sobrescrita_acrescenta_ao_historico(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 5)

    await c.servico.pintar("maria", 7, 5, "#00FF00")
    historico = await c.db.historico_pixel(7, 5)

    await c.db.fechar()
    assert len(historico) == 2


async def test_historico_sobrevive_a_recusa(tmp_path):
    """So a pintura efetiva entra no historico; a tentativa vai para o log."""
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.servico.pintar("joao", 7, 5, "#00FF00")  # ja gastou o unico
    historico = await c.db.historico_pixel(7, 5)

    await c.db.fechar()
    assert len(historico) == 1


async def test_efeito_especial_e_persistido(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    await c.servico.pintar("joao", 7, 5, "#FF0055", efeito="fogo")
    celulas = await c.db.carregar_canvas()

    await c.db.fechar()
    assert celulas[0].effect == "fogo"


# --------------------------------------------------------------------------
# Contadores do usuario
# --------------------------------------------------------------------------


async def test_pintura_contabiliza_um_pixel(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    await c.servico.pintar("joao", 7, 5, "#FF0055")

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao["pixels_painted"] == 1
    assert joao["pixels_overwritten"] == 0


async def test_sobrescrita_conta_como_sobrescrita(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 5)

    await c.servico.pintar("maria", 7, 5, "#00FF00")

    maria = await c.db.usuario("maria")
    await c.db.fechar()
    assert maria["pixels_painted"] == 1
    assert maria["pixels_overwritten"] == 1


async def test_xp_virgem_vale_dez(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    await c.servico.pintar("joao", 7, 5, "#FF0055")

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao["xp"] == 10


async def test_xp_da_sobrescrita_vale_quinze(tmp_path):
    """O XP nao e o custo: sobrescrever custa 2 e vale 15."""
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 5)

    await c.servico.pintar("maria", 7, 5, "#00FF00")

    maria = await c.db.usuario("maria")
    await c.db.fechar()
    assert maria["xp"] == 15


async def test_ajuste_proprio_vale_dez(tmp_path):
    """Repintar o proprio pixel nao e sobrescrita, entao nao vale os 15."""
    c = await montar(tmp_path)
    c.creditar("joao", 5)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.servico.pintar("joao", 7, 5, "#FFFFFF")

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao["xp"] == 20  # 10 + 10


async def test_dono_anterior_registra_a_perda(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 5)

    await c.servico.pintar("maria", 7, 5, "#00FF00")

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao["pixels_lost"] == 1


async def test_pintar_em_si_mesmo_nao_conta_perda(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.servico.pintar("joao", 7, 5, "#FFFFFF")

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao["pixels_lost"] == 0


# --------------------------------------------------------------------------
# Log de acoes: toda tentativa fica registrada
# --------------------------------------------------------------------------


async def test_pintura_bem_sucedida_entra_no_log(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    await c.servico.pintar("joao", 7, 5, "#FF0055")
    acoes = await c.acoes()

    await c.db.fechar()
    assert len(acoes) == 1
    assert acoes[0]["result"] == "ok"
    assert acoes[0]["handle"] == "joao"
    assert acoes[0]["cost"] == 1
    assert acoes[0]["overwrite"] == 0


async def test_pintura_recusada_entra_no_log_com_o_motivo(tmp_path):
    """Sem isto, "por que meu pixel nao apareceu?" nao tem resposta."""
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 1)

    await c.servico.pintar("maria", 7, 5, "#00FF00")
    acoes = await c.acoes()

    await c.db.fechar()
    assert len(acoes) == 2
    recusada = acoes[1]
    assert recusada["handle"] == "maria"
    assert recusada["result"] == "recusado"
    assert recusada["reason"] == MOTIVO_SALDO
    assert recusada["overwrite"] == 1


# --------------------------------------------------------------------------
# Rate limit
# --------------------------------------------------------------------------


async def test_segunda_pintura_em_menos_de_dois_segundos_e_recusada(tmp_path):
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    resultado = await c.servico.pintar("joao", 8, 5, "#FF0055")

    await c.db.fechar()
    assert resultado.ok is False
    assert resultado.motivo == MOTIVO_RATE


async def test_rate_limit_nao_cobra(tmp_path):
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.servico.pintar("joao", 8, 5, "#FF0055")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 9


async def test_rate_limit_libera_depois_do_cooldown(tmp_path):
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    relogio.avancar(2.1)
    resultado = await c.servico.pintar("joao", 8, 5, "#FF0055")

    await c.db.fechar()
    assert resultado.ok is True


async def test_cooldown_nao_afeta_outro_usuario(tmp_path):
    """O limite e por pessoa. Um espectador animado nao cala a sala."""
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)
    c.creditar("maria", 10)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    resultado = await c.servico.pintar("maria", 8, 5, "#00FF00")

    await c.db.fechar()
    assert resultado.ok is True


async def test_cooldown_desligado_permite_rajada(tmp_path):
    c = await montar(tmp_path, cooldown=0.0)
    c.creditar("joao", 10)

    for i in range(5):
        assert (await c.servico.pintar("joao", i, 0, "#FF0055")).ok is True

    await c.db.fechar()
    assert c.canvas.preenchidas() == 5


async def test_recusa_por_rate_limit_nao_gasta_o_saldo_da_proxima(tmp_path):
    """Ser barrado pelo relogio nao pode adiantar o proximo relogio."""
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)
    await c.servico.pintar("joao", 7, 5, "#FF0055")

    relogio.avancar(1.0)
    barrado = await c.servico.pintar("joao", 8, 5, "#FF0055")
    relogio.avancar(1.1)  # 2.1s desde a pintura efetiva
    resultado = await c.servico.pintar("joao", 8, 5, "#FF0055")

    await c.db.fechar()
    assert barrado.ok is False
    assert resultado.ok is True


# --------------------------------------------------------------------------
# Inventario
# --------------------------------------------------------------------------


async def test_inventario_acumula(tmp_path):
    c = await montar(tmp_path)

    c.creditar("joao", 3)
    c.creditar("joao", 4)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 7


async def test_inventario_de_desconhecido_e_zero(tmp_path):
    c = await montar(tmp_path)

    await c.db.fechar()
    assert c.inventario.saldo("ninguem") == 0


async def test_inventario_nao_vai_negativo(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    gastou = c.inventario.gastar("joao", 5)

    await c.db.fechar()
    assert gastou is False
    assert c.inventario.saldo("joao") == 1


async def test_inventario_devolve_pixels(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)
    c.inventario.gastar("joao", 3)

    c.creditar("joao", 1)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 3


async def test_inventario_ignora_caixa_e_espaco(tmp_path):
    """O handle do TikTok chega com e sem @; o saldo e da mesma pessoa."""
    c = await montar(tmp_path)
    c.creditar("Joao", 3)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 3
    assert c.inventario.saldo(" JOAO ") == 3


async def test_resultado_carrega_o_xp_concedido(tmp_path):
    """Quem chama `pintar` precisa do XP para atualizar o ranking sem recalcular."""
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    virgem = await c.servico.pintar("joao", 7, 5, "#FF0055")
    propria = await c.servico.pintar("joao", 7, 5, "#FFFFFF")

    await c.db.fechar()
    assert virgem.xp == 10
    assert propria.xp == 10


async def test_resultado_da_sobrescrita_carrega_quinze_de_xp(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("joao", 7, 5)
    c.creditar("maria", 5)

    resultado = await c.servico.pintar("maria", 7, 5, "#00FF00")

    await c.db.fechar()
    assert resultado.xp == 15


async def test_recusa_nao_concede_xp(tmp_path):
    c = await montar(tmp_path)

    resultado = await c.servico.pintar("joao", 7, 5, "#FF0055")

    await c.db.fechar()
    assert resultado.xp == 0


# --------------------------------------------------------------------------
# Lote: um comentario, muitas celulas
# --------------------------------------------------------------------------
# Um comentario com vinte coordenadas e UMA acao da pessoa. O cooldown existe
# para ninguem monopolizar o quadro — nao para racionar pixel que ela ja pagou.
# Cobrando 2 segundos por PIXEL, "A2, B2, C3..." viraria uma fila de minutos e
# a lista nunca serviria para desenhar coisa nenhuma.


def alvos(*pares) -> list[Coordenada]:
    return [
        Coordenada(x=x, y=y, rotulo=rotulo_de(x, y)) for x, y in pares
    ]


async def test_lote_pinta_todas_as_celulas(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 10)

    resultados = await c.servico.pintar_lote(
        "joao", alvos((0, 2), (1, 2), (2, 3)), "#FF0055"
    )

    await c.db.fechar()
    assert [r.ok for r in resultados] == [True, True, True]
    assert c.canvas.celula(2, 3).pintada is True


async def test_lote_gasta_um_unico_tique_de_cooldown(tmp_path):
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)

    resultados = await c.servico.pintar_lote(
        "joao", alvos((0, 2), (1, 2), (2, 3), (3, 3), (4, 3)), "#FF0055"
    )

    await c.db.fechar()
    assert [r.ok for r in resultados] == [True] * 5
    assert c.inventario.saldo("joao") == 5


async def test_lote_seguinte_espera_o_cooldown(tmp_path):
    """O tique e do lote — nao um passe livre.

    Sem isto, a lista contornaria o limite anti-monopolio: quem manda "A0, B0,
    C0, ..." em sequencia pintaria o quadro inteiro sem esperar nunca.
    """
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)
    c.creditar("joao", 10)

    await c.servico.pintar_lote("joao", alvos((0, 0)), "#FF0055")
    recusado = await c.servico.pintar_lote("joao", alvos((1, 1)), "#FF0055")

    await c.db.fechar()
    assert recusado[0].ok is False
    assert recusado[0].motivo == MOTIVO_RATE


async def test_lote_para_quando_o_saldo_acaba_e_nao_cobra_o_que_nao_pintou(tmp_path):
    """Review Focus: a recusa nao pode custar nada a quem foi recusado.

    Com saldo para tres, a lista de cinco pinta tres e recusa duas — e o saldo
    termina em zero, nunca negativo.
    """
    c = await montar(tmp_path)
    c.creditar("joao", 3)

    resultados = await c.servico.pintar_lote(
        "joao", alvos((0, 2), (1, 2), (2, 3), (3, 3), (4, 3)), "#FF0055"
    )

    await c.db.fechar()
    assert [r.ok for r in resultados] == [True, True, True, False, False]
    assert resultados[3].motivo == MOTIVO_SALDO
    assert c.inventario.saldo("joao") == 0


async def test_lote_sem_saldo_nao_gasta_o_cooldown(tmp_path):
    """Quem nao pintou nada nao perdeu a vez: o tique so sai quando um pixel sai."""
    relogio = Relogio()
    c = await montar(tmp_path, cooldown=2.0, relogio=relogio)

    vazio = await c.servico.pintar_lote("joao", alvos((0, 0)), "#FF0055")
    c.creditar("joao", 5)
    depois = await c.servico.pintar_lote("joao", alvos((0, 0)), "#FF0055")

    await c.db.fechar()
    assert vazio[0].motivo == MOTIVO_SALDO
    assert depois[0].ok is True


async def test_lote_sobrescreve_e_cobra_o_preco_de_sobrescrita(tmp_path):
    c = await montar(tmp_path)
    await c.pintar_de("maria", 7, 5)
    c.creditar("joao", 10)

    resultados = await c.servico.pintar_lote(
        "joao", alvos((7, 5), (8, 5)), "#00FF00"
    )

    await c.db.fechar()
    assert [r.custo for r in resultados] == [2, 1]
    assert c.inventario.saldo("joao") == 7
