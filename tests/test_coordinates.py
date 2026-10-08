"""Parser de coordenadas.

E a porta de entrada do jogo: tudo que a audiencia digita passa por aqui.
Duas regras governam o desenho:

1. Aceitar as variacoes que uma pessoa realmente digita (espaco, minuscula,
   barra, prefixo de comando).
2. NUNCA adivinhar. Uma coordenada errada pintada e pior que um erro visivel,
   porque a pessoa nao entende por que o pixel foi parar no lugar errado.

Por isso o formato puro e estrito: o comentario inteiro tem que ser a
coordenada. "H5 legal!" nao pinta.
"""

import pytest

from game.coordinates import (
    Coordenada,
    indice_de,
    parece_pintura,
    parse_coordenada,
    parse_coordenadas,
    parse_pedido,
    rotulo_de,
)

COLS, ROWS = 26, 51


# --------------------------------------------------------------------------
# Formas aceitas
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "H5",
        "h5",
        "H 5",
        "h 5",
        "H-5",
        "  H5  ",
        "H\t5",
        "/H5",
        "/pixel H5",
        "/pintar H5",
        "/p H5",
        "/PINTAR h5",
    ],
)
def test_formas_aceitas_resolvem_para_h5(texto):
    resultado = parse_coordenada(texto, COLS, ROWS)

    assert resultado == Coordenada(x=7, y=5, rotulo="H5")


def test_a_e_a_primeira_coluna():
    assert parse_coordenada("A0", COLS, ROWS) == Coordenada(x=0, y=0, rotulo="A0")


def test_z_e_a_ultima_coluna_com_26_colunas():
    assert parse_coordenada("Z50", COLS, ROWS) == Coordenada(x=25, y=50, rotulo="Z50")


def test_coluna_dupla_funciona_quando_o_canvas_e_largo():
    """Com 50 colunas, AA e uma coordenada real (indice 26)."""
    resultado = parse_coordenada("AA5", cols=50, rows=51)

    assert resultado == Coordenada(x=26, y=5, rotulo="AA5")


# --------------------------------------------------------------------------
# Formas recusadas
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, motivo",
    [
        ("A51", "linha 51 nao existe num canvas de 0 a 50"),
        ("A999", "linha muito acima do limite"),
        ("1H", "ordem invertida"),
        ("ABC", "coluna dupla sem linha"),
        ("H", "falta a linha"),
        ("", "string vazia"),
        ("   ", "so espacos"),
        ("H5extra", "lixo depois da coordenada"),
        ("H5 H6", "duas coordenadas"),
        ("H5 legal!", "coordenada com texto junto"),
        ("-5H", "sinal antes da coluna"),
        ("H-", "traco sem linha"),
        ("#H5", "cerquilha nao e prefixo"),
        ("H5.5", "linha decimal"),
        ("ZZ", "sem linha"),
        ("/cor vermelho", "comando que nao pinta"),
        ("/ajuda", "comando sem coordenada"),
    ],
)
def test_formas_recusadas_devolvem_none(texto, motivo):
    assert parse_coordenada(texto, COLS, ROWS) is None, motivo


def test_coluna_alem_do_canvas_e_recusada():
    """AA5 e valida num canvas de 50 colunas, invalida num de 26."""
    assert parse_coordenada("AA5", cols=26, rows=51) is None


def test_linha_negativa_e_recusada():
    assert parse_coordenada("H-5", COLS, ROWS) is not None  # o traco e separador
    assert parse_coordenada("H--5", COLS, ROWS) is None


def test_entrada_nao_textual_e_recusada():
    assert parse_coordenada(None, COLS, ROWS) is None
    assert parse_coordenada(123, COLS, ROWS) is None


# --------------------------------------------------------------------------
# rotulo_de / indice_de
# --------------------------------------------------------------------------


def test_rotulo_de_reconstroi_a_coordenada():
    assert rotulo_de(7, 5) == "H5"
    assert rotulo_de(0, 0) == "A0"
    assert rotulo_de(25, 50) == "Z50"


def test_rotulo_de_usa_coluna_dupla_alem_de_z():
    assert rotulo_de(26, 0) == "AA0"
    assert rotulo_de(27, 3) == "AB3"
    assert rotulo_de(51, 0) == "AZ0"
    assert rotulo_de(52, 0) == "BA0"


def test_rotulo_de_e_o_inverso_de_parse():
    for x in (0, 7, 25, 26, 51, 52):
        for y in (0, 5, 50):
            rotulo = rotulo_de(x, y)
            voltou = parse_coordenada(rotulo, cols=100, rows=51)
            assert voltou is not None
            assert (voltou.x, voltou.y) == (x, y)


def test_indice_de_cresce_por_linha():
    assert indice_de(0, 0, 26) == 0
    assert indice_de(25, 0, 26) == 25
    assert indice_de(0, 1, 26) == 26
    assert indice_de(7, 5, 26) == 5 * 26 + 7


def test_indice_de_acompanha_a_largura_do_canvas():
    """O indice nao pode assumir 26 colunas: trocar a largura muda o mapa."""
    assert indice_de(7, 5, cols=50) == 5 * 50 + 7


# --------------------------------------------------------------------------
# Vale a pena responder?
# --------------------------------------------------------------------------

# A LIVE tem gente conversando. Responder "coordenada invalida" para quem
# escreveu "oi" transforma o feed num painel de erros e ensina as pessoas a
# ignorar as mensagens do jogo. Mas quem ESCREVEU uma coordenada e errou
# precisa saber — senao fica mandando rosa e achando que o jogo quebrou.


@pytest.mark.parametrize("texto", ["A51", "AA5", "1H", "/H5", "/pintar A51", "Z99", "h51"])
def test_parece_pintura_para_tentativas(texto):
    assert parece_pintura(texto) is True


@pytest.mark.parametrize(
    "texto", ["oi", "bom dia", "hahaha", "muito legal", "", "   ", "obrigado gente"]
)
def test_conversa_comum_nao_parece_pintura(texto):
    assert parece_pintura(texto) is False


@pytest.mark.parametrize("texto", ["H", "ABC", "abc"])
def test_texto_ambiguo_nao_parece_pintura(texto):
    """Letra solta e indistinguivel de conversa; o rodape ensina o formato."""
    assert parece_pintura(texto) is False


@pytest.mark.parametrize("texto", [None, 42, []])
def test_parece_pintura_aceita_lixo(texto):
    assert parece_pintura(texto) is False


# --------------------------------------------------------------------------
# Listas: "A2, B2, C3" de uma vez
# --------------------------------------------------------------------------
# Quem manda cem rosas e quer desenhar escreve a lista inteira num comentario.
# O formato e ESTENDIDO, nunca relaxado: o que ja pintava um pixel continua
# pintando o mesmo pixel, e a lista so existe quando TODAS as pecas sao
# coordenadas validas. Meia lista e pior que lista nenhuma — a pessoa acha que
# pintou e vai embora.
#
# A unica excecao e a peca que NAO da para ler. Ela e DENUNCIADA e o resto
# pinta: um comentario de 74 celulas colado com as linhas grudadas nao pode
# virar zero pixel por causa de duas pecas coladas.


@pytest.mark.parametrize(
    "texto",
    [
        "A2, B2, C3",
        "A2,B2,C3",
        "A2; B2; C3",
        "A2 B2 C3",
        "a2, b 2, c-3",
        "/pintar A2, B2, C3",
        "/p A2, B2, C3",
    ],
)
def test_lista_separada_por_virgula_espaco_ou_ponto_e_virgula(texto):
    assert parse_coordenadas(texto, COLS, ROWS) == [
        Coordenada(x=0, y=2, rotulo="A2"),
        Coordenada(x=1, y=2, rotulo="B2"),
        Coordenada(x=2, y=3, rotulo="C3"),
    ]


def test_uma_coordenada_so_e_uma_lista_de_um():
    assert parse_coordenadas("H5", COLS, ROWS) == [Coordenada(x=7, y=5, rotulo="H5")]


def test_h_5_continua_sendo_uma_celula():
    """O espaco separa lista — mas so quando a frase INTEIRA nao e coordenada.

    "H 5" pinta H5 desde o primeiro dia. Se a lista viesse primeiro, "H 5"
    viraria duas palavras e nenhuma delas seria coordenada: quem escreve com
    espaco, que e o jeito mais comum de errar o formato, pararia de pintar.
    """
    assert parse_coordenadas("H 5", COLS, ROWS) == [Coordenada(x=7, y=5, rotulo="H5")]


def test_a_mesma_celula_duas_vezes_conta_uma():
    """"A2, a2, A-2" e um pedido, nao tres.

    Sem deduplicar, colar a mesma lista duas vezes cobraria o dobro pelo mesmo
    pixel — e a segunda pintura apagaria a primeira no historico sem que
    ninguem tivesse pedido isso.
    """
    assert parse_coordenadas("A2, a2, A-2", COLS, ROWS) == [
        Coordenada(x=0, y=2, rotulo="A2")
    ]


@pytest.mark.parametrize(
    "texto, esperadas, invalidas",
    [
        ("A2, B2, oi", ["A2", "B2"], ["oi"]),
        ("A2, B2 legal", ["A2", "B2"], ["legal"]),
        ("A2, A51", ["A2"], ["A51"]),
        ("A2, AA5", ["A2"], ["AA5"]),
        ("A2, /cor", ["A2"], ["/cor"]),
        ("A2, /pintar", ["A2"], ["/pintar"]),
        ("oi, A2", ["A2"], ["oi"]),
    ],
)
def test_peca_ilegivel_e_denunciada_e_o_resto_pinta(texto, esperadas, invalidas):
    """Uma peca que nao da para ler nao pode custar o desenho inteiro.

    Foi assim que o coracao de 74 celulas virou zero: o campo do painel tem
    uma linha so, o navegador colou as tres linhas da receita grudadinhas
    ("AE22" + "S23" = "AE22S23"), e a regra antiga jogava fora as outras 72.
    """
    pedido = parse_pedido(texto, COLS, ROWS)
    assert [c.rotulo for c in pedido.coordenadas] == esperadas
    assert pedido.invalidas == invalidas


@pytest.mark.parametrize(
    "texto, esperadas",
    [
        ("A2,", ["A2"]),
        (", A2", ["A2"]),
        ("A2, , B2", ["A2", "B2"]),
        ("A2, B2,", ["A2", "B2"]),
    ],
)
def test_virgula_solta_nao_e_erro(texto, esperadas):
    """Virgula no fim e pontuacao, nao coordenada ilegivel.

    Ninguem merece ler "NAO ENTENDI ''" por ter deixado uma virgula.
    """
    pedido = parse_pedido(texto, COLS, ROWS)
    assert [c.rotulo for c in pedido.coordenadas] == esperadas
    assert pedido.invalidas == []


@pytest.mark.parametrize(
    "texto, esperadas",
    [
        ("A2\nB2\nC3", ["A2", "B2", "C3"]),
        ("A2\r\nB2\r\nC3", ["A2", "B2", "C3"]),
        ("A2,\nB2,\nC3", ["A2", "B2", "C3"]),
        ("U20,V20\nT21,U21", ["U20", "V20", "T21", "U21"]),
    ],
)
def test_quebra_de_linha_tambem_separa(texto, esperadas):
    """A receita tem varias linhas, e o campo do painel tem varias linhas.

    Se a quebra nao separasse, o texto que chega do <textarea> seria lido como
    uma coordenada so e o desenho inteiro morreria.
    """
    assert [c.rotulo for c in parse_coordenadas(texto, 50, 51)] == esperadas


def test_as_linhas_grudadas_nao_derrubam_o_desenho():
    """O estrago do paste multi-linha num campo de uma linha so.

    Nao da para adivinhar onde era a quebra — "AE22" + "S23" virou "AE22S23" e
    a informacao morreu. Mas as celulas em volta continuam perfeitamente
    legiveis, e 72 pixels na tela valem muito mais que zero.
    """
    pedido = parse_pedido("U20,V20,AB20,AE22S23,T23,U23,V23", 50, 51)
    assert [c.rotulo for c in pedido.coordenadas] == [
        "U20",
        "V20",
        "AB20",
        "T23",
        "U23",
        "V23",
    ]
    assert pedido.invalidas == ["AE22S23"]


@pytest.mark.parametrize("texto", [None, 42, ["A2"], ""])
def test_lista_aceita_lixo_nao_textual(texto):
    assert parse_coordenadas(texto, COLS, ROWS) == []


def test_a_lista_nao_engole_a_coordenada_singular():
    """A versao estrita continua estrita: quem pergunta por UMA celula recebe
    None quando o texto tem duas."""
    assert parse_coordenada("H5 H6", COLS, ROWS) is None
    assert len(parse_coordenadas("H5 H6", COLS, ROWS)) == 2
