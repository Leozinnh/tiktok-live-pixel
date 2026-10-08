"""O inventario: quanto cada pessoa tem para gastar.

O painel de teste precisa de uma operacao que o jogo nao tem — "esta pessoa
agora tem N pixels". Nao e creditar: e DEFINIR. A diferenca aparece no segundo
clique. Se o botao do painel somasse em vez de definir, pedir 50 duas vezes
daria 100, e o streamer que quisesse repetir um teste nao teria como.
"""

import pytest

from game.inventory import Inventario


def test_definir_troca_o_saldo_pelo_valor_dito():
    inv = Inventario()
    inv.adicionar("joao", 10)

    inv.definir("joao", 3)

    assert inv.saldo("joao") == 3


def test_definir_duas_vezes_com_o_mesmo_valor_nao_soma():
    """Review Focus: e este o defeito que `adicionar` causaria no painel."""
    inv = Inventario()

    inv.definir("joao", 50)
    inv.definir("joao", 50)

    assert inv.saldo("joao") == 50


def test_definir_zero_zera():
    inv = Inventario()
    inv.adicionar("joao", 40)

    inv.definir("joao", 0)

    assert inv.saldo("joao") == 0


def test_definir_normaliza_o_handle():
    inv = Inventario()

    inv.definir("@Joao ", 7)

    assert inv.saldo("joao") == 7


def test_definir_negativo_e_erro():
    inv = Inventario()

    with pytest.raises(ValueError):
        inv.definir("joao", -1)


def test_definir_e_adicionar_convivem():
    inv = Inventario()

    inv.definir("joao", 10)
    inv.adicionar("joao", 5)

    assert inv.saldo("joao") == 15
