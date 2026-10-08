"""A fila entre o adapter e o motor do jogo.

O adapter escreve de outra thread; o loop async consome. Sob enchente, a fila
descarta o evento MAIS ANTIGO: num jogo ao vivo o evento recente vale mais que
o antigo, e a fila nunca pode bloquear a thread que le o TikTok.
"""

from core.event_queue import EventQueue
from core.events import EventType, LiveEvent


def evento(texto: str) -> LiveEvent:
    return LiveEvent(type=EventType.COMMENT, username="joao", text=texto)


def test_round_trip_de_um_evento():
    fila = EventQueue()
    fila.put(evento("H5"))

    saida = fila.get_nowait()

    assert saida is not None
    assert saida.text == "H5"


def test_fila_vazia_devolve_none():
    assert EventQueue().get_nowait() is None


def test_drenar_devolve_na_ordem_de_chegada():
    fila = EventQueue()
    for i in range(5):
        fila.put(evento(str(i)))

    lote = fila.drain(10)

    assert [e.text for e in lote] == ["0", "1", "2", "3", "4"]


def test_drenar_respeita_o_limite():
    fila = EventQueue()
    for i in range(10):
        fila.put(evento(str(i)))

    lote = fila.drain(3)

    assert len(lote) == 3
    assert fila.size() == 7


def test_drenar_fila_vazia_devolve_lista_vazia():
    assert EventQueue().drain(10) == []


def test_drenar_com_limite_zero_nao_consome():
    fila = EventQueue()
    fila.put(evento("H5"))

    assert fila.drain(0) == []
    assert fila.size() == 1


def test_fila_cheia_descarta_o_mais_antigo():
    fila = EventQueue(maxsize=3)
    for i in range(3):
        fila.put(evento(str(i)))

    fila.put(evento("novo"))

    restantes = [e.text for e in fila.drain(10)]
    assert restantes == ["1", "2", "novo"]


def test_fila_cheia_nunca_levanta():
    """A thread do TikTok nao pode morrer por causa de uma enchente."""
    fila = EventQueue(maxsize=1)
    for i in range(1000):
        fila.put(evento(str(i)))


def test_descartados_conta_exato():
    fila = EventQueue(maxsize=2)
    for i in range(5):
        fila.put(evento(str(i)))

    assert fila.dropped == 3


def test_aceitos_conta_tudo_o_que_entrou():
    fila = EventQueue(maxsize=2)
    for i in range(5):
        fila.put(evento(str(i)))

    assert fila.accepted == 5


def test_size_acompanha_o_consumo():
    fila = EventQueue()
    for i in range(4):
        fila.put(evento(str(i)))

    fila.drain(2)

    assert fila.size() == 2


def test_carga_de_mil_eventos_nao_trava():
    """Existe para PROVAR o anti-spam: se travar, falhou."""
    fila = EventQueue(maxsize=5000)
    for i in range(5000):
        fila.put(evento(str(i)))

    assert len(fila.drain(5000)) == 5000
