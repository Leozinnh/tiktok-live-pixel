"""Validacao da configuracao.

A config e o unico lugar onde a afinacao do jogo vive. Ela e validada no boot
e o programa se RECUSA a subir com valor invalido: um jogo configurado errado
que sobe e pior que um que nao sobe, porque o erro so aparece no ar.
"""

import json

import pytest

from core.config import PADROES, ConfigError, carregar


def escrever(tmp_path, dados: dict):
    caminho = tmp_path / "config.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def test_config_ausente_levanta_citando_o_caminho(tmp_path):
    alvo = tmp_path / "nao_existe.json"

    with pytest.raises(ConfigError) as erro:
        carregar(alvo)

    assert "nao_existe.json" in str(erro.value)


def test_json_malformado_levanta_citando_o_caminho(tmp_path):
    caminho = tmp_path / "config.json"
    caminho.write_text("{ isso nao e json", encoding="utf-8")

    with pytest.raises(ConfigError) as erro:
        carregar(caminho)

    assert "config.json" in str(erro.value)


def test_chave_ausente_e_preenchida_pelo_default(tmp_path):
    caminho = escrever(tmp_path, {})

    cfg = carregar(caminho, exigir_username=False)

    assert cfg["canvas"]["cols"] == PADROES["canvas"]["cols"]
    assert cfg["canvas"]["rows"] == PADROES["canvas"]["rows"]


def test_default_do_canvas_e_50_por_51(tmp_path):
    caminho = escrever(tmp_path, {})

    cfg = carregar(caminho, exigir_username=False)

    assert cfg["canvas"]["cols"] == 50
    assert cfg["canvas"]["rows"] == 51


def test_valor_do_usuario_sobrevive_ao_merge(tmp_path):
    caminho = escrever(tmp_path, {"canvas": {"cols": 50}})

    cfg = carregar(caminho, exigir_username=False)

    assert cfg["canvas"]["cols"] == 50
    # A irma nao configurada continua vindo do default.
    assert cfg["canvas"]["rows"] == PADROES["canvas"]["rows"]


@pytest.mark.parametrize("cols", [0, -1, 703, "vinte e seis"])
def test_colunas_invalidas_sao_recusadas_citando_a_chave(tmp_path, cols):
    caminho = escrever(tmp_path, {"canvas": {"cols": cols}})

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=False)

    assert "canvas.cols" in str(erro.value)


@pytest.mark.parametrize("rows", [0, -1, "cinquenta e um"])
def test_linhas_invalidas_sao_recusadas_citando_a_chave(tmp_path, rows):
    caminho = escrever(tmp_path, {"canvas": {"rows": rows}})

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=False)

    assert "canvas.rows" in str(erro.value)


@pytest.mark.parametrize(
    "chave, valor",
    [
        ("fonte_regua_min", 0),
        ("fonte_regua_max", -3),
        ("fonte_regua_max", 1000),
        ("fonte_instrucoes", "grande"),
        ("fonte_rodape", 0),
    ],
)
def test_tela_invalida_recusa_a_config(tmp_path, chave, valor):
    """Fonte zero nao existe, e uma fonte maior que o quadro nao tem layout."""
    caminho = escrever(tmp_path, {"tela": {chave: valor}})

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=False)

    assert f"tela.{chave}" in str(erro.value)


def test_teto_da_fonte_abaixo_do_piso_recusa_a_config(tmp_path):
    """Um teto abaixo do piso deixaria a conta da fonte sem resposta."""
    caminho = escrever(
        tmp_path, {"tela": {"fonte_regua_min": 20, "fonte_regua_max": 10}}
    )

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=False)

    assert "fonte_regua_max" in str(erro.value)


def test_702_colunas_e_o_maximo_aceito(tmp_path):
    """702 = colunas de A ate ZZ. Alem disso o rotulo deixa de ser legivel."""
    caminho = escrever(tmp_path, {"canvas": {"cols": 702}})

    cfg = carregar(caminho, exigir_username=False)

    assert cfg["canvas"]["cols"] == 702


@pytest.mark.parametrize("porta", [0, -1, 70000, "oitenta"])
def test_porta_invalida_e_recusada(tmp_path, porta):
    caminho = escrever(tmp_path, {"server": {"port": porta}})

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=False)

    assert "server.port" in str(erro.value)


def test_placeholder_de_username_e_recusado_em_modo_live(tmp_path):
    caminho = escrever(tmp_path, {"tiktok": {"username": "@SEU_USUARIO"}})

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=True)

    assert "tiktok.username" in str(erro.value)


def test_placeholder_e_aceito_em_modo_teste(tmp_path):
    caminho = escrever(tmp_path, {"tiktok": {"username": "@SEU_USUARIO"}})

    cfg = carregar(caminho, exigir_username=False)

    assert cfg["tiktok"]["username"] == "@SEU_USUARIO"


def test_username_real_e_aceito(tmp_path):
    caminho = escrever(tmp_path, {"tiktok": {"username": "@meninodolancer"}})

    cfg = carregar(caminho, exigir_username=True)

    assert cfg["tiktok"]["username"] == "@meninodolancer"


def test_custo_de_sobrescrita_menor_que_um_e_recusado(tmp_path):
    """Sobrescrita de graca tornaria o vandalismo trivial."""
    caminho = escrever(tmp_path, {"rewards": {"sobrescrita_custo": 0}})

    with pytest.raises(ConfigError) as erro:
        carregar(caminho, exigir_username=False)

    assert "rewards.sobrescrita_custo" in str(erro.value)


def test_config_real_do_projeto_e_valida():
    """A config que vai pro ar tem que ser valida. Pega erro de digitacao."""
    cfg = carregar("config.json", exigir_username=False)

    # O TAMANHO da grade e escolha do streamer e muda com o quadro que ele
    # quer (25x26 e o desenho grande de hoje, 50x51 foi o de ontem). O que
    # este teste guarda e o que NAO pode mudar sem conserto em outro lugar: a
    # coluna ainda caber num rotulo que a audiencia consegue escrever (702 =
    # A..ZZ) e a paleta continuar tendo as cores que ela aprendeu.
    assert 1 <= cfg["canvas"]["cols"] <= 702
    assert cfg["canvas"]["rows"] >= 1
    assert cfg["rewards"]["sobrescrita_custo"] >= 1
    assert len(cfg["canvas"]["paleta"]) >= 8
    assert cfg["tela"]["fonte_regua_max"] >= cfg["tela"]["fonte_regua_min"]
