"""O canvas em memoria.

E a fonte de verdade para renderizacao: o SQLite e write-behind, entao um
disco lento nunca aparece na tela. Nada aqui toca o banco.

O canvas NAO pode assumir 26x51. A expansao do mapa e uma mudanca de config,
nao uma reescrita, entao os testes usam tamanhos diferentes de proposito.
"""

import json

import pytest

from game.canvas import CanvasModel, Celula


def test_total_e_o_produto_das_dimensoes():
    assert CanvasModel(26, 51).total == 1326


def test_total_acompanha_outras_dimensoes():
    assert CanvasModel(50, 100).total == 5000
    assert CanvasModel(1, 1).total == 1


def test_canvas_nasce_vazio():
    canvas = CanvasModel(26, 51)

    assert canvas.preenchidas() == 0
    assert canvas.celula(0, 0).color is None


def test_pintar_devolve_a_celula_pintada():
    canvas = CanvasModel(26, 51)

    celula = canvas.pintar(7, 5, "#FF0055", "joao")

    assert celula.x == 7
    assert celula.y == 5
    assert celula.color == "#FF0055"
    assert celula.owner_id == "joao"


def test_celula_pintada_aparece_na_consulta():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")

    celula = canvas.celula(7, 5)

    assert celula is not None
    assert celula.color == "#FF0055"
    assert celula.pintada is True


def test_pintar_registra_quando():
    canvas = CanvasModel(26, 51)

    celula = canvas.pintar(7, 5, "#FF0055", "joao")

    assert celula.painted_at is not None
    assert "T" in celula.painted_at  # ISO 8601


def test_pintar_com_efeito_guarda_o_efeito():
    canvas = CanvasModel(26, 51)

    celula = canvas.pintar(7, 5, "#FF0055", "joao", efeito="fogo")

    assert celula.effect == "fogo"


def test_pintar_por_cima_substitui_o_dono():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")

    canvas.pintar(7, 5, "#00FF00", "maria")

    celula = canvas.celula(7, 5)
    assert celula.color == "#00FF00"
    assert celula.owner_id == "maria"


def test_pintar_por_cima_nao_aumenta_o_preenchido():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")
    canvas.pintar(7, 5, "#00FF00", "maria")

    assert canvas.preenchidas() == 1


def test_preenchidas_conta_so_o_que_tem_cor():
    canvas = CanvasModel(26, 51)
    canvas.pintar(0, 0, "#FF0055", "joao")
    canvas.pintar(1, 0, "#00FF00", "maria")

    assert canvas.preenchidas() == 2


@pytest.mark.parametrize(
    "x, y",
    [(-1, 0), (0, -1), (26, 0), (0, 51), (26, 51), (999, 999)],
)
def test_pintar_fora_do_canvas_levanta(x, y):
    canvas = CanvasModel(26, 51)

    with pytest.raises(IndexError):
        canvas.pintar(x, y, "#FF0055", "joao")


@pytest.mark.parametrize("x, y", [(-1, 0), (26, 0), (0, 51), (999, 999)])
def test_consultar_fora_do_canvas_devolve_none(x, y):
    assert CanvasModel(26, 51).celula(x, y) is None


def test_o_limite_superior_e_inclusivo():
    canvas = CanvasModel(26, 51)

    celula = canvas.pintar(25, 50, "#FF0055", "joao")

    assert celula.x == 25
    assert celula.y == 50


def test_para_dict_e_serializavel_em_json():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao", efeito="fogo")

    texto = json.dumps(canvas.para_dict())

    assert "H5" in texto or "#FF0055" in texto


def test_para_dict_traz_dimensoes_e_contagem():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")

    dados = canvas.para_dict()

    assert dados["cols"] == 26
    assert dados["rows"] == 51
    assert dados["total"] == 1326
    assert dados["filled"] == 1


def test_para_dict_envia_so_as_celulas_pintadas():
    """1326 celulas vazias em todo hello seria desperdicio de banda."""
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")

    dados = canvas.para_dict()

    assert len(dados["cells"]) == 1
    assert dados["cells"][0]["x"] == 7
    assert dados["cells"][0]["y"] == 5


def test_para_dict_traz_o_rotulo_da_coordenada():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")

    assert canvas.para_dict()["cells"][0]["coordinate"] == "H5"


def test_carregar_repovoa_o_canvas():
    canvas = CanvasModel(26, 51)

    canvas.carregar(
        [
            Celula(x=7, y=5, color="#FF0055", owner_id="joao"),
            Celula(x=0, y=0, color="#00FF00", owner_id="maria"),
        ]
    )

    assert canvas.preenchidas() == 2
    assert canvas.celula(7, 5).owner_id == "joao"


def test_carregar_substitui_o_estado_anterior():
    canvas = CanvasModel(26, 51)
    canvas.pintar(1, 1, "#000000", "antigo")

    canvas.carregar([Celula(x=7, y=5, color="#FF0055", owner_id="joao")])

    assert canvas.preenchidas() == 1
    assert canvas.celula(1, 1).color is None


def test_carregar_ignora_celula_fora_do_canvas():
    """Um banco de um canvas maior nao pode derrubar um canvas menor."""
    canvas = CanvasModel(10, 10)

    canvas.carregar(
        [
            Celula(x=7, y=5, color="#FF0055", owner_id="joao"),
            Celula(x=99, y=99, color="#FF0000", owner_id="antigo"),
        ]
    )

    assert canvas.preenchidas() == 1


def test_celulas_pintadas_lista_so_as_com_cor():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")
    canvas.pintar(0, 0, "#00FF00", "maria")

    pintadas = canvas.celulas_pintadas()

    assert len(pintadas) == 2
    assert {(c.x, c.y) for c in pintadas} == {(7, 5), (0, 0)}


def test_apagar_limpa_a_celula():
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao")

    canvas.apagar(7, 5)

    assert canvas.celula(7, 5).color is None
    assert canvas.preenchidas() == 0


def test_apagar_fora_do_canvas_levanta():
    with pytest.raises(IndexError):
        CanvasModel(26, 51).apagar(99, 99)


def test_para_dict_do_canvas_segue_a_forma_do_spec_12():
    """O `hello` e lido pela tela; os nomes sao os do spec §12."""
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao", efeito="fogo")

    dados = canvas.para_dict()
    celula = dados["cells"][0]

    assert dados["filled"] == 1
    assert "preenchidas" not in dados
    for chave in ("x", "y", "coordinate", "color", "user", "effect", "ts"):
        assert chave in celula, f"falta `{chave}` do spec §12"
    assert celula["coordinate"] == "H5"
    assert celula["user"] == "@joao"
    assert celula["effect"] == "fogo"


def test_limpar_devolve_o_quadro_inteiro_ao_estado_virgem():
    """O botao LIMPAR do painel. Apaga TUDO de uma vez.

    E a operacao mais destrutiva do jogo, e a unica que nao tem volta: nao ha
    desfazer, o desenho da comunidade some. Por isso ela e testada contra o
    estado que importa — nenhuma celula pintada, nenhum dono, nenhum efeito —
    e nao contra "o metodo foi chamado".
    """
    canvas = CanvasModel(26, 51)
    canvas.pintar(7, 5, "#FF0055", "joao", efeito="fogo")
    canvas.pintar(0, 0, "#00FF00", "maria")
    canvas.pintar(25, 50, "#0000FF", "ana")

    canvas.limpar()

    assert canvas.preenchidas() == 0
    assert canvas.celulas_pintadas() == []
    assert canvas.para_dict()["cells"] == []
    # Os donos tambem: sem isto o placar continuaria dizendo que joao pintou
    # um pixel que nao existe mais.
    assert canvas.donos() == set()
    assert canvas.celula(7, 5).effect is None
    assert canvas.celula(7, 5).painted_at is None


def test_limpar_num_canvas_ja_vazio_nao_quebra():
    """Clicar duas vezes no botao e a coisa mais normal do mundo."""
    canvas = CanvasModel(26, 51)

    canvas.limpar()
    canvas.limpar()

    assert canvas.preenchidas() == 0


def test_limpar_nao_muda_o_tamanho_do_canvas():
    """O quadro volta a ficar em branco; a grade continua sendo a mesma."""
    canvas = CanvasModel(50, 51)
    canvas.pintar(10, 10, "#FF0055", "joao")

    canvas.limpar()

    assert (canvas.cols, canvas.rows) == (50, 51)
    assert canvas.total == 50 * 51
    # E da para pintar de novo logo depois.
    canvas.pintar(10, 10, "#FF0055", "joao")
    assert canvas.preenchidas() == 1
