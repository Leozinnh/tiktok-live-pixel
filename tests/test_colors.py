"""Cores: a automatica por usuario, e a escolhida por comando.

A cor automatica precisa ser ESTAVEL entre reinicios. Isso descarta `hash()`,
que e aleatorizado por PYTHONHASHSEED: com ele, o mesmo @joao apareceria
vermelho hoje e azul amanha, e a comunidade acharia que a arte mudou sozinha.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from game.colors import (
    PALETA_PADRAO,
    Cor,
    chave_especial,
    cor_automatica,
    parse_cor,
    separar_cor,
)

RAIZ = Path(__file__).resolve().parent.parent

ESPECIAIS = {
    "arco_iris": {"rotulo": "ARCO-ÍRIS", "emoji": "🌈", "efeito": "arco_iris"},
    "eletrico": {"rotulo": "ELÉTRICO", "emoji": "⚡", "efeito": "eletrico"},
}

CORES = list(PALETA_PADRAO.values())


# --------------------------------------------------------------------------
# Cor automatica
# --------------------------------------------------------------------------


def test_cor_automatica_e_estavel_entre_processos():
    """A prova de que nao usamos `hash()`: sementes diferentes, mesma cor."""
    codigo = (
        "from game.colors import cor_automatica, PALETA_PADRAO;"
        "print(cor_automatica('joao', list(PALETA_PADRAO.values())))"
    )
    saidas = set()

    for semente in ("0", "1", "12345"):
        ambiente = {**os.environ, "PYTHONHASHSEED": semente}
        resultado = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True,
            text=True,
            env=ambiente,
            cwd=RAIZ,
            check=True,
        )
        saidas.add(resultado.stdout.strip())

    assert len(saidas) == 1, f"a cor mudou entre processos: {saidas}"


def test_cor_automatica_e_deterministica_na_mesma_chamada():
    assert cor_automatica("joao", CORES) == cor_automatica("joao", CORES)


def test_cor_automatica_ignora_maiuscula_e_espaco():
    assert cor_automatica("  Joao ", CORES) == cor_automatica("joao", CORES)


def test_cor_automatica_devolve_cor_da_paleta():
    assert cor_automatica("joao", CORES) in CORES


def test_cor_automatica_espalha_entre_os_nomes():
    """Nao precisa ser perfeito, mas 200 nomes nao podem caber em 2 cores."""
    usadas = {cor_automatica(f"usuario{i}", CORES) for i in range(200)}

    assert len(usadas) >= len(CORES) - 1


def test_cor_automatica_com_paleta_vazia_nao_quebra():
    assert cor_automatica("joao", []) == "#FFFFFF"


# --------------------------------------------------------------------------
# Cores por nome
# --------------------------------------------------------------------------


def test_nome_de_cor_resolve_para_o_hex():
    cor = parse_cor("vermelho", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex == PALETA_PADRAO["vermelho"]


def test_nome_de_cor_ignora_maiuscula_e_espaco():
    cor = parse_cor("  VERMELHO  ", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex == PALETA_PADRAO["vermelho"]


def test_nome_fora_da_paleta_e_recusado():
    """`roxo` existe no padrao, mas nao nesta paleta."""
    enxuta = {"vermelho": "#FF0000", "azul": "#0000FF"}

    assert parse_cor("roxo", enxuta, ESPECIAIS) is None


def test_cor_por_nome_nao_vem_com_efeito():
    cor = parse_cor("vermelho", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.efeito is None


# --------------------------------------------------------------------------
# Cores por hex
# --------------------------------------------------------------------------


def test_hex_valido_e_aceito():
    cor = parse_cor("#FF0055", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex == "#FF0055"


def test_hex_e_normalizado_para_maiuscula():
    cor = parse_cor("#ff0055", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex == "#FF0055"


@pytest.mark.parametrize(
    "texto",
    ["#FFF", "#FF005", "#FF00555", "#GGGGGG", "#", "##FF0055", "FF0055"],
)
def test_hex_malformado_e_recusado(texto):
    assert parse_cor(texto, PALETA_PADRAO, ESPECIAIS) is None


# --------------------------------------------------------------------------
# Cores especiais
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    ["arco_iris", "arco-iris", "arco iris", "arco-íris", "ARCO ÍRIS", "arcoiris"],
)
def test_especial_tolera_variacoes_de_escrita(texto):
    cor = parse_cor(texto, PALETA_PADRAO, ESPECIAIS)

    assert cor is not None, texto
    assert cor.efeito == "arco_iris"


def test_especial_com_acento_resolve():
    cor = parse_cor("elétrico", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.efeito == "eletrico"


def test_especial_desconhecido_e_recusado():
    assert parse_cor("diamante", PALETA_PADRAO, ESPECIAIS) is None


def test_especial_traz_um_hex_de_base():
    """O efeito anima por cima, mas precisa de uma cor de partida."""
    cor = parse_cor("arco_iris", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex.startswith("#")
    assert len(cor.hex) == 7


def test_chave_especial_e_o_inverso():
    assert chave_especial("arco_iris", ESPECIAIS) == "arco_iris"
    assert chave_especial("ARCO-ÍRIS", ESPECIAIS) == "arco_iris"
    assert chave_especial("inexistente", ESPECIAIS) is None


# --------------------------------------------------------------------------
# Comando /cor
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    ["/cor vermelho", "/cor  vermelho", "/color vermelho", "cor vermelho"],
)
def test_prefixo_de_comando_e_aceito(texto):
    cor = parse_cor(texto, PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex == PALETA_PADRAO["vermelho"]


def test_prefixo_de_comando_aceita_hex():
    cor = parse_cor("/cor #00FF88", PALETA_PADRAO, ESPECIAIS)

    assert cor is not None
    assert cor.hex == "#00FF88"


@pytest.mark.parametrize("texto", ["", "   ", "/cor", "/cor ", None, 42])
def test_entradas_vazias_ou_invalidas_devolvem_none(texto):
    assert parse_cor(texto, PALETA_PADRAO, ESPECIAIS) is None


def test_cor_e_imutavel():
    cor = parse_cor("vermelho", PALETA_PADRAO, ESPECIAIS)

    assert isinstance(cor, Cor)
    with pytest.raises(Exception):
        cor.hex = "#000000"


# --------------------------------------------------------------------------
# Cor colada na coordenada
# --------------------------------------------------------------------------


def test_separar_cor_devolve_a_cor_e_o_resto():
    cor, resto = separar_cor("/vermelho W1, X1", PALETA_PADRAO, ESPECIAIS)

    assert cor == Cor(hex=PALETA_PADRAO["vermelho"])
    assert resto == "W1, X1"


def test_separar_cor_de_uma_cor_so_deixa_o_resto_vazio():
    cor, resto = separar_cor("azul", PALETA_PADRAO, ESPECIAIS)

    assert cor == Cor(hex=PALETA_PADRAO["azul"])
    assert resto == ""


def test_separar_cor_le_o_nome_composto_das_especiais():
    """So as especiais tem nome de duas palavras: "arco iris W1" e uma jogada."""
    cor, resto = separar_cor("arco iris W1", PALETA_PADRAO, ESPECIAIS)

    assert cor == Cor(hex="#FF00E5", efeito="arco_iris")
    assert resto == "W1"


@pytest.mark.parametrize("texto", ["oi gente", "W1, X1", "/pontos", "", None])
def test_separar_cor_sem_cor_no_comeco_devolve_none(texto):
    assert separar_cor(texto, PALETA_PADRAO, ESPECIAIS) is None
