"""O caminho de um evento TikTok ate virar pixel na tela.

O pipeline e a costura: ele recebe um `LiveEvent` ja traduzido pelo adapter e
decide o que aquilo significa no jogo. Presente credita. Comentario com
coordenada pinta. Conversa comum nao faz nada.

Duas regras que parecem detalhe e nao sao:

- Evento sem autor nao faz NADA. A biblioteca manda curtidas sem `user` quando
  alguem curte demais, e creditar isso para "desconhecido" inflaria um usuario
  fantasma que apareceria no ranking sem nunca ter existido.
- Quando falta saldo, o pipeline devolve uma recusa visivel e NAO credita
  nada. Um erro silencioso aqui e a pior falha possivel: a pessoa manda uma
  rosa, escreve a coordenada, e nada acontece sem explicacao.
"""

import logging
from pathlib import Path

import pytest

from backend.database import Database
from core.config import carregar
from core.events import EventType, LiveEvent
from core.ratelimit import RateLimiter
from game.canvas import CanvasModel
from game.inventory import Inventario
from game.painting import ServicoPintura
from game.pipeline import Pipeline
from game.ranking import Ranking

RAIZ = Path(__file__).resolve().parent.parent
COLS, ROWS = 26, 51
PALETA = {
    "vermelho": "#FF3B5C",
    "verde": "#3DFF8A",
    "azul": "#3D9BFF",
    "roxo": "#A855F7",
    "amarelo": "#FFD93D",
}
ESPECIAIS = {
    "fogo": {"rotulo": "FOGO", "emoji": "🔥", "hex": "#FF6B1A", "efeito": "fogo"},
    "neon": {"rotulo": "NEON", "emoji": "✨", "hex": "#39FF14", "efeito": "neon"},
}


def cfg_teste(**over) -> dict:
    cfg = {
        "canvas": {"cols": COLS, "rows": ROWS, "paleta": PALETA, "especiais": ESPECIAIS},
        "rewards": {
            "pixel_custo": 1,
            "sobrescrita_custo": 2,
            "presente_desconhecido": 1,
            "max_multiplicador": 10,
            "gifts": {"Rose": 1, "Galaxy": 60, "Lion": 300},
            "like": {"curtidas_por_pixel": 20, "max_pixels": 10},
            "follow": {"pixels": 5},
            "share": {"pixels": 3},
        },
        "limits": {"max_pixels_por_evento": 400},
    }
    cfg.update(over)
    return cfg


class Cenario:
    def __init__(self, pipeline, canvas, inventario, db, ranking):
        self.pipeline = pipeline
        self.canvas = canvas
        self.inventario = inventario
        self.db = db
        self.ranking = ranking

    async def enviar(self, tipo, **kwargs) -> list[dict]:
        return await self.pipeline.processar(LiveEvent(type=tipo, **kwargs))

    def creditar(self, handle: str, quantos: int) -> None:
        self.inventario.adicionar(handle, quantos)


def tipos(mensagens: list[dict]) -> list[str]:
    return [m["type"] for m in mensagens]


def primeira(mensagens: list[dict], tipo: str) -> dict | None:
    for m in mensagens:
        if m["type"] == tipo:
            return m
    return None


async def montar(tmp_path, *, cfg=None, multiplicador=None) -> Cenario:
    cfg = cfg or cfg_teste()
    canvas = CanvasModel(COLS, ROWS)
    inventario = Inventario()
    db = Database(tmp_path / "pipeline.db")
    await db.abrir()
    ranking = Ranking(paleta=list(PALETA.values()), tamanho=5)

    servico = ServicoPintura(
        canvas,
        inventario,
        db,
        limiter=RateLimiter(now_fn=lambda: 0.0),
        cooldown=0.0,
        custo_virgem=cfg["rewards"]["pixel_custo"],
        custo_sobrescrita=cfg["rewards"]["sobrescrita_custo"],
        xp_virgem=10,
        xp_sobrescrita=15,
    )

    pipeline = Pipeline(
        cfg,
        servico=servico,
        inventario=inventario,
        db=db,
        ranking=ranking,
        multiplicador_fn=multiplicador,
    )
    return Cenario(pipeline, canvas, inventario, db, ranking)


# --------------------------------------------------------------------------
# Presentes
# --------------------------------------------------------------------------


async def test_rosa_credita_um_pixel(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.GIFT, username="joao", display_name="Joao", gift_name="Rose")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 1


async def test_presente_emite_aviso_na_tela(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(
        EventType.GIFT, username="joao", display_name="Joao", gift_name="Rose"
    )

    await c.db.fechar()
    aviso = primeira(mensagens, "toast")
    assert aviso is not None
    assert aviso["kind"] == "reward"
    assert "Joao" in aviso["text"]


async def test_presente_aparece_no_console(tmp_path, caplog):
    """O streamer descobre que o presente chegou pelo console.

    O console e o unico canal de quem esta transmitindo: a tela vive numa cena
    do OBS e o painel em outra janela, e nenhum dos dois esta na frente de quem
    esta ao vivo. Sem esta linha o presente chega, credita, e nao aparece em
    lugar nenhum — o sintoma e exatamente "enviei uma rosa e nao aconteceu
    nada", que e a pior falha possivel deste projeto.
    """
    c = await montar(tmp_path)

    with caplog.at_level(logging.INFO, logger="game.pipeline"):
        await c.enviar(
            EventType.GIFT, username="joao", display_name="Joao", gift_name="Rose"
        )

    await c.db.fechar()
    registros = [r for r in caplog.records if r.levelno >= logging.INFO]
    assert registros, "o presente nao deixou nenhuma linha no console"
    texto = registros[-1].getMessage()
    assert "Joao" in texto
    assert "Rose" in texto


async def test_presente_grande_vale_o_valor_do_presente(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.GIFT, username="joao", gift_name="Galaxy")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 60


async def test_streak_credita_de_uma_vez(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.GIFT, username="joao", gift_name="Rose", quantity=5)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 5


async def test_teto_por_evento_corta_a_rajada(tmp_path):
    cfg = cfg_teste(limits={"max_pixels_por_evento": 12})
    c = await montar(tmp_path, cfg=cfg)

    await c.enviar(EventType.GIFT, username="joao", gift_name="Lion", quantity=10)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 12


async def test_multiplicador_de_evento_vale_para_presentes(tmp_path):
    """E o que faz 'PIXEL TURBO' valer a pena para quem manda presente."""
    c = await montar(tmp_path, multiplicador=lambda: 3.0)

    await c.enviar(EventType.GIFT, username="joao", gift_name="Rose", quantity=2)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 6


async def test_multiplicador_nao_muda_o_custo_da_pintura(tmp_path):
    c = await montar(tmp_path, multiplicador=lambda: 3.0)
    c.creditar("joao", 1)

    await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 0
    assert c.canvas.celula(7, 5).pintada is True


async def test_presente_fica_registrado_no_banco(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.GIFT, username="joao", gift_name="Galaxy", quantity=2)

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao is not None
    assert joao["gifts_received"] == 1


# --------------------------------------------------------------------------
# Sem autor: nada acontece
# --------------------------------------------------------------------------


async def test_presente_sem_autor_nao_credita(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.GIFT, gift_name="Galaxy", quantity=10)

    await c.db.fechar()
    assert mensagens == []
    assert c.inventario.instantaneo() == {}


async def test_like_sem_autor_nao_credita(tmp_path):
    """Review Focus: e o caso real — a biblioteca omite `user` em curtida em massa."""
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.LIKE, like_delta=5000)

    await c.db.fechar()
    assert mensagens == []
    assert c.inventario.instantaneo() == {}


async def test_follow_sem_autor_nao_credita(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.FOLLOW)

    await c.db.fechar()
    assert mensagens == []
    assert c.inventario.instantaneo() == {}


async def test_comentario_sem_autor_nao_pinta(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.COMMENT, text="H5")

    await c.db.fechar()
    assert mensagens == []
    assert c.canvas.preenchidas() == 0


# --------------------------------------------------------------------------
# Curtidas
# --------------------------------------------------------------------------


async def test_vinte_curtidas_viraram_um_pixel(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.LIKE, username="joao", like_delta=20)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 1


async def test_curtidas_picadas_ao_longo_do_tempo(tmp_path):
    c = await montar(tmp_path)

    for _ in range(20):
        await c.enviar(EventType.LIKE, username="joao", like_delta=1)

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 1


async def test_seguir_credita_cinco(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.FOLLOW, username="joao", display_name="Joao")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 5


async def test_compartilhar_credita_tres(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.SHARE, username="joao", display_name="Joao")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 3


# --------------------------------------------------------------------------
# Pintura por comentario
# --------------------------------------------------------------------------


async def test_comentario_com_coordenada_pinta(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", display_name="Joao", text="H5")

    await c.db.fechar()
    assert c.canvas.celula(7, 5).pintada is True
    assert "pixel_painted" in tipos(mensagens)


async def test_mensagem_de_pintura_segue_o_protocolo(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", display_name="Joao", text="H5")
    pintura = primeira(mensagens, "pixel_painted")

    await c.db.fechar()
    assert pintura["x"] == 7
    assert pintura["y"] == 5
    assert pintura["coordinate"] == "H5"
    assert pintura["user"] == "@joao"
    assert pintura["cost"] == 1
    assert pintura["color"].startswith("#")
    assert isinstance(pintura["ts"], int)
    assert pintura["effect"] is None


async def test_pintura_entra_no_feed(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="h 5")
    entrada = primeira(mensagens, "feed")

    await c.db.fechar()
    assert entrada is not None
    assert entrada["coordinate"] == "H5"
    assert entrada["user"] == "@joao"


@pytest.mark.parametrize("texto", ["H5", "h5", "h 5", "/H5", "/pixel H5", "/pintar h-5"])
async def test_todas_as_grafias_pintam(tmp_path, texto):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    await c.enviar(EventType.COMMENT, username="joao", text=texto)

    await c.db.fechar()
    assert c.canvas.celula(7, 5).pintada is True


async def test_pintura_desconta_o_saldo(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 3)

    await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 2


async def test_sobrescrita_desconta_dois(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)
    c.creditar("maria", 5)
    await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.enviar(EventType.COMMENT, username="maria", text="H5")

    await c.db.fechar()
    assert c.inventario.saldo("maria") == 3
    assert c.canvas.celula(7, 5).owner_id == "maria"


# --------------------------------------------------------------------------
# Recusa: precisa ser visivel
# --------------------------------------------------------------------------


async def test_pintura_sem_saldo_avisa_na_tela(tmp_path):
    """Review Focus: recusa silenciosa e a pior falha possivel do jogo."""
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", display_name="Joao", text="H5")

    await c.db.fechar()
    aviso = primeira(mensagens, "toast")
    assert aviso is not None
    assert aviso["kind"] == "error"
    assert "ROSA" in aviso["text"] or "PIXEL" in aviso["text"]


async def test_pintura_sem_saldo_nao_pinta(tmp_path):
    c = await montar(tmp_path)

    await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.db.fechar()
    assert c.canvas.preenchidas() == 0


async def test_pintura_sem_saldo_nao_emite_pixel_painted(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.db.fechar()
    assert "pixel_painted" not in tipos(mensagens)


async def test_coordenada_fora_do_mapa_avisa(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="A51")
    aviso = primeira(mensagens, "toast")

    await c.db.fechar()
    assert aviso is not None
    assert aviso["kind"] == "error"
    assert c.inventario.saldo("joao") == 5


async def test_conversa_comum_nao_gera_aviso(tmp_path):
    """Quem esta so conversando nao pode receber erro do jogo."""
    c = await montar(tmp_path)

    mensagens = await c.enviar(
        EventType.COMMENT, username="joao", display_name="Joao", text="bom dia gente"
    )

    await c.db.fechar()
    assert mensagens == []


# --------------------------------------------------------------------------
# Cores
# --------------------------------------------------------------------------


async def test_cor_automatica_e_atribuida_na_primeira_pintura(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="H5")
    pintura = primeira(mensagens, "pixel_painted")

    await c.db.fechar()
    assert pintura["color"] in PALETA.values()


async def test_a_cor_e_estavel_entre_pinturas(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 2)

    primeira_pintura = primeira(
        await c.enviar(EventType.COMMENT, username="joao", text="H5"), "pixel_painted"
    )
    segunda_pintura = primeira(
        await c.enviar(EventType.COMMENT, username="joao", text="H6"), "pixel_painted"
    )

    await c.db.fechar()
    assert primeira_pintura["color"] == segunda_pintura["color"]


async def test_cada_pessoa_pinta_com_a_cor_do_proprio_handle(tmp_path):
    """A cor sai do handle, nao de um sorteio nem da ordem de chegada."""
    from game.colors import cor_automatica

    c = await montar(tmp_path)
    c.creditar("joao", 1)
    c.creditar("maria", 1)

    a = primeira(await c.enviar(EventType.COMMENT, username="joao", text="H5"), "pixel_painted")
    b = primeira(await c.enviar(EventType.COMMENT, username="maria", text="H6"), "pixel_painted")

    await c.db.fechar()
    assert a["color"] == cor_automatica("joao", list(PALETA.values()))
    assert b["color"] == cor_automatica("maria", list(PALETA.values()))


async def test_comando_de_cor_troca_a_cor(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    await c.enviar(EventType.COMMENT, username="joao", text="/cor roxo")

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="H5")
    pintura = primeira(mensagens, "pixel_painted")

    await c.db.fechar()
    assert pintura["color"] == "#A855F7"


async def test_comando_de_cor_responde_na_tela(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="/cor roxo")
    aviso = primeira(mensagens, "toast")

    await c.db.fechar()
    assert aviso is not None
    assert "ROXO" in aviso["text"].upper()


async def test_o_aviso_da_cor_diz_que_ainda_falta_pintar(tmp_path):
    """`/cor` troca a cor, nao pinta — e o aviso precisa dizer isso.

    Sem esta linha o aviso anuncia a cor e para. Quem manda so a cor no painel
    le "agora pinta de ROXO", olha a grid, ve ela intacta e conclui que o jogo
    travou: foi exatamente o que aconteceu. O aviso e o unico retorno que essa
    pessoa recebe, entao ele tem que terminar com o proximo passo, nao com a
    cor.
    """
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="/cor roxo")
    aviso = primeira(mensagens, "toast")

    await c.db.fechar()
    assert "ROXO" in aviso["text"].upper()
    assert "H5" in aviso["text"], "o aviso nao diz que ainda falta comentar a coordenada"


async def test_cor_com_hex_funciona(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    await c.enviar(EventType.COMMENT, username="joao", text="/color #FF00AA")

    pintura = primeira(await c.enviar(EventType.COMMENT, username="joao", text="H5"), "pixel_painted")

    await c.db.fechar()
    assert pintura["color"] == "#FF00AA"


async def test_cor_escolhida_sobrevive_ao_banco(tmp_path):
    c = await montar(tmp_path)
    await c.enviar(EventType.COMMENT, username="joao", display_name="Joao", text="/cor roxo")

    joao = await c.db.usuario("joao")
    await c.db.fechar()
    assert joao["color"] == "#A855F7"


async def test_cor_especial_leva_efeito_para_a_pintura(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    await c.enviar(EventType.COMMENT, username="joao", text="/cor fogo")

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="H5")
    pintura = primeira(mensagens, "pixel_painted")

    await c.db.fechar()
    assert pintura["effect"] == "fogo"
    assert pintura["color"] == "#FF6B1A"


async def test_cor_especial_fica_registrada_como_efeito(tmp_path):
    """O efeito precisa sobreviver ao restart junto com a cor."""
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    await c.enviar(EventType.COMMENT, username="joao", text="/cor neon")

    joao = await c.db.usuario("joao")

    await c.enviar(EventType.COMMENT, username="joao", text="H5")
    celulas = await c.db.carregar_canvas()
    await c.db.fechar()

    assert joao["color"] == "#39FF14"
    assert joao["effect"] == "neon"
    assert celulas[0].effect == "neon"


async def test_comando_de_cor_invalido_avisa_e_nao_muda(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    mensagens = await c.enviar(EventType.COMMENT, username="joao", text="/cor rosa-choque")
    pintura = primeira(
        await c.enviar(EventType.COMMENT, username="joao", text="H5"), "pixel_painted"
    )

    await c.db.fechar()
    assert "toast" in tipos(mensagens)
    assert pintura["color"] in PALETA.values()


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------


async def test_pintura_entra_no_ranking(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)

    await c.enviar(EventType.COMMENT, username="joao", display_name="Joao", text="H5")

    await c.db.fechar()
    entrada = c.ranking.entrada("joao")
    assert entrada.pixels == 1
    assert entrada.xp == 10
    assert entrada.nome == "Joao"


async def test_ranking_soma_ao_longo_da_live(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 5)

    for i in range(5):
        await c.enviar(EventType.COMMENT, username="joao", text=f"H{i}")

    await c.db.fechar()
    assert c.ranking.entrada("joao").pixels == 5


async def test_sobrescrita_da_xp_maior_no_ranking(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    c.creditar("maria", 5)
    await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.enviar(EventType.COMMENT, username="maria", text="H5")

    await c.db.fechar()
    assert c.ranking.entrada("maria").xp == 15


async def test_ranking_conhece_a_cor_escolhida(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 1)
    await c.enviar(EventType.COMMENT, username="joao", text="/cor roxo")

    await c.enviar(EventType.COMMENT, username="joao", text="H5")

    await c.db.fechar()
    assert c.ranking.entrada("joao").cor == "#A855F7"


# --------------------------------------------------------------------------
# Eventos de sistema
# --------------------------------------------------------------------------


async def test_evento_de_sistema_e_ignorado(tmp_path):
    c = await montar(tmp_path)

    mensagens = await c.enviar(EventType.SYSTEM, text="conectado")

    await c.db.fechar()
    assert mensagens == []


async def test_pipeline_sobrevive_a_evento_malformado(tmp_path):
    """Campos nulos sao plausiveis: o adapter reflete o JSON do TikTok."""
    c = await montar(tmp_path)

    for tipo in EventType:
        await c.enviar(
            tipo,
            username="joao",
            text=None,
            gift_name=None,
            quantity=None,
            like_delta=None,
        )

    await c.db.fechar()
    assert c.canvas.preenchidas() == 0


# --------------------------------------------------------------------------
# Desenhar de uma vez: cem rosas e a lista de coordenadas
# --------------------------------------------------------------------------
# O gesto que o jogo precisa suportar: a pessoa manda um presente grande e
# escreve o desenho inteiro num comentario. Duas coisas tinham que deixar de
# atrapalhar — o presente que ficava no teto do multiplicador e o comentario
# que so entendia uma coordenada.


async def test_comentario_com_lista_pinta_o_desenho_de_uma_vez(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 10)

    mensagens = await c.enviar(
        EventType.COMMENT, username="joao", display_name="Joao", text="A2, B2, C3"
    )

    await c.db.fechar()
    pintados = [m for m in mensagens if m["type"] == "pixel_painted"]
    assert [m["coordinate"] for m in pintados] == ["A2", "B2", "C3"]
    assert c.inventario.saldo("joao") == 7


async def test_lista_cada_pixel_entra_no_feed(tmp_path):
    """A tela desenha celula a celula: um aviso so nao pinta tres quadrados."""
    c = await montar(tmp_path)
    c.creditar("joao", 10)

    mensagens = await c.enviar(
        EventType.COMMENT, username="joao", display_name="Joao", text="A2, B2"
    )

    await c.db.fechar()
    assert tipos(mensagens).count("feed") == 2


async def test_lista_maior_que_o_saldo_pinta_o_que_cabe_e_avisa(tmp_path):
    c = await montar(tmp_path)
    c.creditar("joao", 2)

    mensagens = await c.enviar(
        EventType.COMMENT, username="joao", display_name="Joao", text="A2, B2, C3, D3"
    )

    await c.db.fechar()
    pintados = [m for m in mensagens if m["type"] == "pixel_painted"]
    avisos = [m for m in mensagens if m["type"] == "toast"]
    assert len(pintados) == 2
    assert len(avisos) == 1
    assert "SEM PIXELS" in avisos[0]["text"]
    # O aviso e do telao, mas a resposta e DELA: sem o nome, quem mandou o
    # desenho nao sabe que a recusa e para ela.
    assert "@joao" in avisos[0]["text"]


async def test_peca_ilegivel_na_lista_nao_custa_o_desenho(tmp_path):
    """O estrago do paste multi-linha no campo de uma linha do painel.

    O navegador colou as tres linhas da receita grudadinhas, e "AE22" + "S23"
    virou "AE22S23". Nao da para adivinhar onde era a quebra — mas as outras
    72 celulas eram perfeitamente legiveis, e a regra antiga jogava todas fora
    por causa dessa.
    """
    c = await montar(tmp_path)
    c.creditar("joao", 10)

    mensagens = await c.enviar(
        EventType.COMMENT, username="joao", display_name="Joao", text="A2, B2, AE22S23"
    )

    await c.db.fechar()
    pintados = [m for m in mensagens if m["type"] == "pixel_painted"]
    assert [m["coordinate"] for m in pintados] == ["A2", "B2"]

    aviso = primeira(mensagens, "toast")
    assert aviso["kind"] == "error"
    # A peca ruim e NOMEADA. Sem o nome, quem colou 74 celulas e viu 72 vai
    # procurar o defeito no lugar errado.
    assert "AE22S23" in aviso["text"]


async def test_comentario_de_varias_linhas_pinta_o_desenho(tmp_path):
    """A receita de um desenho tem varias linhas, e o campo do painel tambem."""
    c = await montar(tmp_path)
    c.creditar("joao", 10)

    mensagens = await c.enviar(
        EventType.COMMENT,
        username="joao",
        display_name="Joao",
        text="A2,B2,C3\nD3,E3,F3",
    )

    await c.db.fechar()
    pintados = [m for m in mensagens if m["type"] == "pixel_painted"]
    assert [m["coordinate"] for m in pintados] == ["A2", "B2", "C3", "D3", "E3", "F3"]


async def test_lista_so_de_lixo_continua_dando_nao_entendi(tmp_path):
    """Sem nada legivel nao ha o que pintar, e o aviso velho continua valendo."""
    c = await montar(tmp_path)
    c.creditar("joao", 10)

    mensagens = await c.enviar(
        EventType.COMMENT, username="joao", display_name="Joao", text="A51, B99"
    )

    await c.db.fechar()
    assert c.canvas.preenchidas() == 0
    assert primeira(mensagens, "toast")["text"] == "NAO ENTENDI — ESCREVA LETRA + NUMERO, EX: H5"


async def test_cem_rosas_valem_cem_pixels_no_config_que_esta_no_repo(tmp_path):
    """Cem rosas tem que virar cem pixels, nao dez.

    Este teste le o `config.json` DE VERDADE, e nao o de mentira da suite. O
    `max_multiplicador` existia so como constante no codigo e como numero nos
    testes — nunca tinha chegado ao arquivo que o jogo carrega, entao o teto
    de 10 valia em silencio e um streak de cem rosas pagava o mesmo que um de
    dez. Configuracao que so existe no teste nao configura nada.
    """
    cfg = carregar(RAIZ / "config.json", exigir_username=False)
    c = await montar(tmp_path, cfg=cfg)

    await c.enviar(
        EventType.GIFT,
        username="joao",
        display_name="Joao",
        gift_name="Rose",
        quantity=100,
    )

    await c.db.fechar()
    assert c.inventario.saldo("joao") == 100
