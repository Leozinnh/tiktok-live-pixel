"""Quanto cada interacao vale em pixels.

Esta e a economia do jogo, e ela precisa ser previsivel: a pessoa manda uma
rosa, ve "+1 PIXEL" na tela, e entende a regra sem ninguem explicar. Se o
mesmo presente valesse 1 hoje e 3 amanha, a unica leitura possivel seria
"esse jogo e aleatorio", e ninguem manda a segunda rosa.

Os dois limites que existem aqui (multiplicador de streak e teto por evento)
nao sao sobre dinheiro — sao sobre a tela. Uma rajada nao pode pintar o canvas
inteiro de uma vez e apagar o que a sala passou a hora construindo.
"""

import pytest

from core.events import EventType, LiveEvent
from game.rewards import AcumuladorCurtidas, pixels_do_evento

CFG = {
    "rewards": {
        "pixel_custo": 1,
        "sobrescrita_custo": 2,
        "presente_desconhecido": 1,
        "max_multiplicador": 10,
        "gifts": {
            "Rose": 1,
            "Finger Heart": 2,
            "Perfume": 5,
            "Galaxy": 60,
            "Lion": 300,
        },
        "like": {"curtidas_por_pixel": 20, "max_pixels": 10},
        "follow": {"pixels": 5},
        "share": {"pixels": 3},
    }
}


def evento(tipo, **kwargs) -> LiveEvent:
    return LiveEvent(type=tipo, **kwargs)


# --------------------------------------------------------------------------
# Presentes
# --------------------------------------------------------------------------


def test_rosa_vale_um_pixel():
    e = evento(EventType.GIFT, username="joao", gift_name="Rose", quantity=1)

    assert pixels_do_evento(e, CFG) == 1


def test_presente_mais_caro_vale_mais():
    e = evento(EventType.GIFT, username="joao", gift_name="Galaxy", quantity=1)

    assert pixels_do_evento(e, CFG) == 60


def test_streak_multiplica_pelo_numero_de_presentes():
    e = evento(EventType.GIFT, username="joao", gift_name="Finger Heart", quantity=5)

    assert pixels_do_evento(e, CFG) == 10


def test_streak_de_rosa_vira_dez_pixels():
    e = evento(EventType.GIFT, username="joao", gift_name="Rose", quantity=10)

    assert pixels_do_evento(e, CFG) == 10


def test_multiplicador_tem_teto():
    """Um streak de 500 rosas nao pode ser 500 pixels de uma vez."""
    e = evento(EventType.GIFT, username="joao", gift_name="Rose", quantity=500)

    assert pixels_do_evento(e, CFG) == 10


def test_teto_do_multiplicador_respeita_o_valor_do_presente():
    e = evento(EventType.GIFT, username="joao", gift_name="Perfume", quantity=500)

    assert pixels_do_evento(e, CFG) == 50  # 5 x 10


def test_quantity_zero_conta_como_um():
    """A biblioteca manda 0 em alguns eventos; creditar 0 seria perder presente."""
    e = evento(EventType.GIFT, username="joao", gift_name="Rose", quantity=0)

    assert pixels_do_evento(e, CFG) == 1


def test_quantity_negativa_conta_como_um():
    e = evento(EventType.GIFT, username="joao", gift_name="Rose", quantity=-7)

    assert pixels_do_evento(e, CFG) == 1


def test_presente_desconhecido_vale_o_padrao():
    """Presente novo que a gente nunca viu ainda precisa recompensar."""
    e = evento(EventType.GIFT, username="joao", gift_name="PresenteNovo2027")

    assert pixels_do_evento(e, CFG) == 1


def test_presente_desconhecido_tambem_multiplica():
    e = evento(EventType.GIFT, username="joao", gift_name="PresenteNovo2027", quantity=4)

    assert pixels_do_evento(e, CFG) == 4


def test_presente_sem_nome_vale_o_padrao():
    e = evento(EventType.GIFT, username="joao", gift_name="")

    assert pixels_do_evento(e, CFG) == 1


# --------------------------------------------------------------------------
# Curtidas
# --------------------------------------------------------------------------


def test_curtidas_viram_pixel_no_multiplo():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)
    e = evento(EventType.LIKE, username="joao", like_delta=20)

    assert pixels_do_evento(e, CFG, a) == 1


def test_curtidas_abaixo_do_multiplo_nao_pagam_ainda():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)
    e = evento(EventType.LIKE, username="joao", like_delta=19)

    assert pixels_do_evento(e, CFG, a) == 0


def test_o_resto_das_curtidas_nao_e_perdido():
    """Dezenove curtidas de um em um ainda precisam virar um pixel."""
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)

    total = 0
    for _ in range(19):
        total += pixels_do_evento(evento(EventType.LIKE, username="joao", like_delta=1), CFG, a)
    assert total == 0

    total += pixels_do_evento(evento(EventType.LIKE, username="joao", like_delta=1), CFG, a)

    assert total == 1


def test_curtidas_de_pessoas_diferentes_nao_se_somam():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)
    for _ in range(19):
        pixels_do_evento(evento(EventType.LIKE, username="joao", like_delta=1), CFG, a)

    sozinho = pixels_do_evento(
        evento(EventType.LIKE, username="maria", like_delta=1), CFG, a
    )

    assert sozinho == 0


def test_curtidas_tem_teto_por_evento():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)
    e = evento(EventType.LIKE, username="joao", like_delta=2000)

    assert pixels_do_evento(e, CFG, a) == 10


def test_curtidas_negativas_nao_geram_pixels():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)
    e = evento(EventType.LIKE, username="joao", like_delta=-500)

    assert pixels_do_evento(e, CFG, a) == 0


def test_curtidas_sem_acumulador_nao_pagam():
    """Sem acumulador nao da para saber o resto — melhor nao pagar que pagar errado."""
    e = evento(EventType.LIKE, username="joao", like_delta=100)

    assert pixels_do_evento(e, CFG, None) == 0


# --------------------------------------------------------------------------
# Seguir e compartilhar
# --------------------------------------------------------------------------


def test_seguir_vale_cinco():
    e = evento(EventType.FOLLOW, username="joao")

    assert pixels_do_evento(e, CFG) == 5


def test_compartilhar_vale_tres():
    e = evento(EventType.SHARE, username="joao")

    assert pixels_do_evento(e, CFG) == 3


# --------------------------------------------------------------------------
# O que nao paga
# --------------------------------------------------------------------------


def test_comentario_nao_paga_pixel():
    """Comentario pinta, nao credita. Senao o canvas seria escrito de graca."""
    e = evento(EventType.COMMENT, username="joao", text="H5")

    assert pixels_do_evento(e, CFG) == 0


def test_evento_de_sistema_nao_paga():
    e = evento(EventType.SYSTEM, text="live conectada")

    assert pixels_do_evento(e, CFG) == 0


def test_evento_sem_autor_nao_paga():
    """Review Focus: a curtida sem `user` nao pode creditar para ninguem."""
    e = evento(EventType.GIFT, gift_name="Galaxy", quantity=10)

    assert pixels_do_evento(e, CFG) == 0


# --------------------------------------------------------------------------
# Acumulador isolado
# --------------------------------------------------------------------------


def test_acumulador_le_o_config():
    a = AcumuladorCurtidas.do_config(CFG)

    assert a.por_pixel == 20
    assert a.maximo == 10


def test_acumulador_sem_config_usa_padroes():
    a = AcumuladorCurtidas.do_config({"rewards": {}})

    assert a.por_pixel > 0
    assert a.maximo > 0


def test_acumulador_devolve_zero_para_curtida_zero():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)

    assert a.creditar("joao", 0) == 0


def test_acumulador_ignora_handle_vazio():
    a = AcumuladorCurtidas(por_pixel=20, maximo=10)

    assert a.creditar("", 100) == 0
