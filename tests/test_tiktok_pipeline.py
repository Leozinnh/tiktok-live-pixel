"""A costura: do Webcast cru do TikTok ate um pixel no canvas.

Os dois arquivos anteriores testam as pontas separadas — a traducao de um
lado, as regras do jogo do outro. Este testa a EMENDA, que e onde os defeitos
de verdade moram: cada lado passa sozinho e o jogo ainda pode creditar cinco
vezes o que devia.

O caso central e o streak de presente. Os numeros aqui nao sao decorativos:

- Sem o filtro de `streaking`, 40 rosas viram 1+2+...+40 = 820 pixels.
- Com o filtro, viram 40 — que o teto de streak ainda reduz para 10.

Tres ordens de grandeza de diferenca na economia do jogo, decididas por um
`if` de uma linha.
"""

from types import SimpleNamespace

import pytest

from core.event_queue import EventQueue
from core.events import EventType
from game.rewards import AcumuladorCurtidas
from test_pipeline import montar
from tiktok.adapter import evento_de_comentario, evento_de_presente, evento_de_like
from tiktok.simulado import SimuladorLive


def usuario(unique_id="joao", nickname="Joao"):
    return SimpleNamespace(unique_id=unique_id, nickname=nickname)


def rosa(streaking: bool, repeat_count: int, user=None):
    return SimpleNamespace(
        user=user or usuario(),
        streaking=streaking,
        repeat_count=repeat_count,
        gift=SimpleNamespace(id=5655, name="Rose"),
    )


def tipos(mensagens: list[dict]) -> list[str]:
    return [m["type"] for m in mensagens]


# --------------------------------------------------------------------------
# Streak, de ponta a ponta
# --------------------------------------------------------------------------


async def test_streak_de_quarenta_rosas_credita_dez_pixels_e_nao_oitocentos(tmp_path):
    """Review Focus: o defeito que este teste pega derruba a economia."""
    c = await montar(tmp_path)

    # Uma sequencia real: 40 eventos crus, so o ultimo consolidado.
    crus = [rosa(streaking=True, repeat_count=n) for n in range(1, 40)]
    crus.append(rosa(streaking=False, repeat_count=40))

    for evento in (evento_de_presente(o) for o in crus):
        if evento is not None:
            await c.pipeline.processar(evento)

    await c.db.fechar()

    # 1+2+...+40 = 820 sem filtro; 40 com filtro; 10 com o teto de streak.
    assert c.inventario.saldo("joao") == 10


async def test_streak_aparece_uma_vez_so_no_banco(tmp_path):
    c = await montar(tmp_path)

    crus = [rosa(streaking=True, repeat_count=n) for n in range(1, 40)]
    crus.append(rosa(streaking=False, repeat_count=40))
    for evento in (evento_de_presente(o) for o in crus):
        if evento is not None:
            await c.pipeline.processar(evento)

    presentes = await c.db.conn.execute_fetchall(
        "SELECT quantity, pixel_reward FROM gifts WHERE handle = ?", ("joao",)
    )
    await c.db.fechar()

    assert len(presentes) == 1
    assert presentes[0][0] == 40
    assert presentes[0][1] == 10


async def test_streak_de_presente_caro_para_no_teto_por_evento(tmp_path):
    """Sao DOIS tetos, e o de evento morde primeiro.

    O teto de streak (`max_multiplicador`) age sobre quantas vezes a base do
    presente conta: 20 Galaxias viram 10. O teto por evento
    (`max_pixels_por_evento`) e o limite absoluto do que UM evento pode
    creditar, independente do presente: 400.

    10 x 60 = 600 passaria pelo primeiro e morre no segundo.
    """
    c = await montar(tmp_path)

    def galaxia(streaking, repeat_count):
        return SimpleNamespace(
            user=usuario(),
            streaking=streaking,
            repeat_count=repeat_count,
            gift=SimpleNamespace(id=1, name="Galaxy"),
        )

    crus = [galaxia(True, n) for n in range(1, 20)]
    crus.append(galaxia(False, 20))
    for evento in (evento_de_presente(o) for o in crus):
        if evento is not None:
            await c.pipeline.processar(evento)

    await c.db.fechar()

    # 20 x 60 = 1200; o teto de streak corta para 10 x 60 = 600; o teto por
    # evento corta de novo para 400.
    assert c.inventario.saldo("joao") == 400


# --------------------------------------------------------------------------
# Comentario traduzido pintando de verdade
# --------------------------------------------------------------------------


async def test_comentario_do_webcast_pinta_o_canvas(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    bruto = SimpleNamespace(user=usuario(), content="H5")
    mensagens = await c.pipeline.processar(evento_de_comentario(bruto))

    await c.db.fechar()

    assert "pixel_painted" in tipos(mensagens)
    pintado = next(m for m in mensagens if m["type"] == "pixel_painted")
    assert pintado["coordinate"] == "H5"
    assert pintado["user"] == "@joao"
    assert c.canvas.celula(7, 5).pintada is True


async def test_comentario_com_alias_antigo_tambem_pinta(tmp_path):
    """A v3 da biblioteca renomeou `comment` para `content`."""
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    bruto = SimpleNamespace(user=usuario(), comment="H5")
    mensagens = await c.pipeline.processar(evento_de_comentario(bruto))

    await c.db.fechar()

    assert "pixel_painted" in tipos(mensagens)


async def test_coordenada_invalida_do_webcast_avisa_a_pessoa(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    bruto = SimpleNamespace(user=usuario(), content="A51")
    mensagens = await c.pipeline.processar(evento_de_comentario(bruto))

    await c.db.fechar()

    assert tipos(mensagens) == ["toast"]
    assert mensagens[0]["kind"] == "error"


async def test_conversa_comum_nao_gera_aviso(tmp_path):
    c = await montar(tmp_path)

    bruto = SimpleNamespace(user=usuario(), content="bom dia gente")
    mensagens = await c.pipeline.processar(evento_de_comentario(bruto))

    await c.db.fechar()

    assert mensagens == []


# --------------------------------------------------------------------------
# Curtidas traduzidas
# --------------------------------------------------------------------------


async def test_curtidas_do_webcast_viram_pixel_no_acumulador(tmp_path):
    c = await montar(tmp_path)
    acumulador = AcumuladorCurtidas(por_pixel=20, maximo=10)

    total = 0
    for _ in range(3):
        cru = SimpleNamespace(user=usuario(), count=20, total=total + 20)
        total += 20
        evento = evento_de_like(cru, total - 20)
        await c.pipeline.processar(evento)

    await c.db.fechar()

    assert c.inventario.saldo("joao") == 3


async def test_curtida_atrasada_nao_credita_de_novo(tmp_path):
    """Um evento fora de ordem nao pode pagar duas vezes pela mesma curtida."""
    c = await montar(tmp_path)

    adiantado = SimpleNamespace(user=usuario(), count=20, total=200)
    await c.pipeline.processar(evento_de_like(adiantado, 180))

    atrasado = SimpleNamespace(user=usuario(), count=20, total=100)
    await c.pipeline.processar(evento_de_like(atrasado, 200))

    await c.db.fechar()

    assert c.inventario.saldo("joao") == 1


# --------------------------------------------------------------------------
# O modo teste percorre o mesmo caminho
# --------------------------------------------------------------------------


def simulador(cfg: dict, **kw) -> tuple[SimuladorLive, EventQueue]:
    """O simulador escreve numa fila, como o adapter real."""
    fila = EventQueue()
    return SimuladorLive(fila, cfg, **kw), fila


async def test_rajada_do_simulador_sem_saldo_nao_pinta_nada(tmp_path):
    """Review Focus: o MODO TESTE nao pode ser um atalho.

    Se a rajada do simulador pintasse por fora do `ServicoPintura`, ela
    testaria um jogo que nao existe — e um espectador sem rosa nenhuma
    encheria o canvas no modo teste e nao na LIVE."""
    c = await montar(tmp_path)
    sim, fila = simulador(c.pipeline.cfg, nomes=["ana", "bruno"], seed=42)

    for evento in sim.rajada(150, modo="pintura"):
        assert fila.get_nowait() is evento
        await c.pipeline.processar(evento)

    await c.db.fechar()

    assert c.canvas.preenchidas() == 0
    assert c.inventario.saldo("ana") == 0


async def test_rajada_do_simulador_com_saldo_pinta_area_de_verdade(tmp_path):
    c = await montar(tmp_path)
    sim, _ = simulador(c.pipeline.cfg, nomes=["ana", "bruno"], seed=42)

    for nome in ("ana", "bruno"):
        c.creditar(nome, 300)

    for evento in sim.rajada(150, modo="pintura"):
        await c.pipeline.processar(evento)

    await c.db.fechar()

    assert c.canvas.preenchidas() >= 100


async def test_rajada_de_pintura_nao_repete_celula(tmp_path):
    """Embaralhar de verdade e o que faz 150 eventos cobrirem 150 celulas
    distintas em vez de amontoar num canto."""
    c = await montar(tmp_path)
    sim, _ = simulador(c.pipeline.cfg, seed=7)

    celulas = [e.text for e in sim.rajada(150, modo="pintura")]

    await c.db.fechar()
    assert len(set(celulas)) == 150


async def test_simulador_e_adapter_real_entram_pela_mesma_porta(tmp_path):
    """Os dois escrevem `LiveEvent` na mesma fila; o jogo nao distingue."""
    sim, fila = simulador({"canvas": {"cols": 26, "rows": 51}}, seed=1)

    sim.comentar("ana", "H5")

    evento = fila.get_nowait()
    assert evento.type == EventType.COMMENT
    assert evento.handle() == "ana"
    assert evento.text == "H5"
