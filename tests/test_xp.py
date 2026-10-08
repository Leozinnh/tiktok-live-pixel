"""Progressao: quanto XP vale o que, e quando isso vira um titulo.

A curva e uma escolha de design, nao uma constante fisica — mas as fronteiras
tem que ser exatas. Se `xp_para_nivel` e `nivel_para_xp` discordarem em um
ponto, o HUD mostra "faltam 0 XP para o nivel 5" para sempre, e ninguem
entende por que o nivel nao sobe.

O outro motivo de existir deste modulo: o titulo e o que a pessoa ve. "Mestre"
na tela vale mais que "nivel 20" para quem esta assistindo.
"""

import pytest

from game.xp import (
    BASE_POR_NIVEL,
    PASSO_POR_NIVEL,
    TITULOS,
    nivel_para_xp,
    progresso_nivel,
    titulo_de,
    xp_para_nivel,
)

# A curva do config.json: 100 XP para o nivel 2, +25 a cada nivel seguinte.


# --------------------------------------------------------------------------
# Fronteiras exatas
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "xp, esperado",
    [
        (0, 1),
        (1, 1),
        (99, 1),
        (100, 2),  # 100 exatos ja sobem
        (101, 2),
        (224, 2),
        (225, 3),  # 100 + 125
        (549, 4),
        (550, 5),  # Pintor
        (1800, 10),  # Artista
        (6175, 20),  # Mestre
        (13050, 30),  # Pixel Master
        (34300, 50),  # Lenda
    ],
)
def test_xp_para_nivel(xp, esperado):
    assert xp_para_nivel(xp) == esperado


@pytest.mark.parametrize(
    "nivel, esperado",
    [
        (1, 0),
        (2, 100),
        (3, 225),
        (4, 375),
        (5, 550),
        (10, 1800),
        (20, 6175),
        (30, 13050),
        (50, 34300),
    ],
)
def test_nivel_para_xp(nivel, esperado):
    assert nivel_para_xp(nivel) == esperado


def test_as_duas_funcoes_concordam_em_toda_a_curva():
    """Review Focus: fronteira que discorda e nivel que nunca sobe.

    Varremos XP por XP numa faixa larga e conferimos as duas direcoes.
    """
    for xp in range(0, 40000):
        nivel = xp_para_nivel(xp)
        assert nivel_para_xp(nivel) <= xp, f"xp={xp} nivel={nivel} cedo demais"
        assert nivel_para_xp(nivel + 1) > xp, f"xp={xp} nivel={nivel} tarde demais"


def test_curva_e_monotonica():
    anterior = -1
    for xp in range(0, 20000, 7):
        nivel = xp_para_nivel(xp)
        assert nivel >= anterior
        anterior = nivel


# --------------------------------------------------------------------------
# Entradas degeneradas
# --------------------------------------------------------------------------


@pytest.mark.parametrize("xp", [-1000, -1])
def test_xp_negativo_e_nivel_um(xp):
    assert xp_para_nivel(xp) == 1


def test_nivel_um_nao_custa_nada():
    assert nivel_para_xp(1) == 0


@pytest.mark.parametrize("nivel", [0, -5])
def test_nivel_abaixo_de_um_nao_custa_nada(nivel):
    assert nivel_para_xp(nivel) == 0


def test_curva_aceita_parametros_proprios():
    """A curva e configuravel; os testes acima usam so os padroes."""
    assert nivel_para_xp(2, base=10, passo=0) == 10
    assert nivel_para_xp(3, base=10, passo=0) == 20
    assert xp_para_nivel(19, base=10, passo=0) == 2
    assert xp_para_nivel(20, base=10, passo=0) == 3


def test_passos_maiores_que_a_base_tambem_funcionam():
    """passo > base nao pode quebrar a estimativa por forma fechada."""
    for xp in range(0, 3000, 13):
        nivel = xp_para_nivel(xp, base=10, passo=50)
        assert nivel_para_xp(nivel, base=10, passo=50) <= xp
        assert nivel_para_xp(nivel + 1, base=10, passo=50) > xp


# --------------------------------------------------------------------------
# Titulos
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nivel, esperado",
    [
        (1, "Novato"),
        (4, "Novato"),
        (5, "Pintor"),
        (9, "Pintor"),
        (10, "Artista"),
        (19, "Artista"),
        (20, "Mestre"),
        (29, "Mestre"),
        (30, "Pixel Master"),
        (49, "Pixel Master"),
        (50, "Lenda"),
        (99, "Lenda"),
        (500, "Lenda"),
    ],
)
def test_titulo_de(nivel, esperado):
    assert titulo_de(nivel) == esperado


def test_titulo_nunca_e_vazio():
    for nivel in range(-10, 300):
        assert titulo_de(nivel).strip()


def test_marcos_do_titulo_batem_com_a_tabela():
    """Os seis marcos do spec, na ordem, sem buraco nem sobreposicao."""
    marcos = [n for n, _ in TITULOS]
    assert marcos == sorted(marcos)
    assert len(marcos) == len(set(marcos))
    assert TITULOS[0] == (1, "Novato")
    assert TITULOS[-1] == (50, "Lenda")


# --------------------------------------------------------------------------
# Progresso: o que a barra do HUD precisa
# --------------------------------------------------------------------------


def test_progresso_no_inicio_do_nivel():
    p = progresso_nivel(0)

    assert p["nivel"] == 1
    assert p["titulo"] == "Novato"
    assert p["faltam"] == 100
    assert p["fracao"] == 0.0


def test_progresso_no_meio_do_nivel():
    p = progresso_nivel(50)

    assert p["nivel"] == 1
    assert p["faltam"] == 50
    assert p["fracao"] == 0.5


def test_progresso_no_ultimo_xp_do_nivel():
    p = progresso_nivel(99)

    assert p["nivel"] == 1
    assert p["faltam"] == 1
    assert 0.98 < p["fracao"] < 1.0


def test_progresso_logo_depois_de_subir():
    p = progresso_nivel(100)

    assert p["nivel"] == 2
    assert p["faltam"] == 125
    assert p["fracao"] == 0.0


def test_fracao_fica_sempre_entre_zero_e_um():
    for xp in range(0, 35000, 37):
        p = progresso_nivel(xp)
        assert 0.0 <= p["fracao"] <= 1.0, f"fracao fora da faixa em xp={xp}"


def test_progresso_carrega_o_total_de_xp():
    p = progresso_nivel(4321)

    assert p["xp"] == 4321
    assert p["titulo"] == titulo_de(p["nivel"])


def test_progresso_do_ultimo_nivel_nao_estoura():
    """No nivel 50 o proximo ainda existe — a barra nao pode dividir por zero."""
    p = progresso_nivel(34300)

    assert p["nivel"] == 50
    assert p["faltam"] > 0
    assert 0.0 <= p["fracao"] <= 1.0


def test_padroes_sao_os_do_config():
    assert BASE_POR_NIVEL == 100
    assert PASSO_POR_NIVEL == 25
