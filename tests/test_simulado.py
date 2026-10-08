"""O adapter falso: a fonte de eventos do MODO TESTE.

Este e o arquivo que permite desenvolver e demonstrar o jogo inteiro sem
nenhuma LIVE aberta. Ele fala a mesma lingua do adapter real — escreve
`LiveEvent` na mesma `EventQueue` — entao nada abaixo dele sabe a diferenca.

Isso tem uma consequencia que vale mais que a conveniencia: qualquer bug que
apareca no modo teste e um bug do jogo, nao um bug "do simulador". O caminho
percorrido e exatamente o mesmo.
"""

from core.event_queue import EventQueue
from core.events import EventType
from game.coordinates import parse_coordenada
from tiktok.simulado import SimuladorLive, nomes_de_teste


def cfg(cols=26, rows=51) -> dict:
    return {
        "canvas": {
            "cols": cols,
            "rows": rows,
            "paleta": {"vermelho": "#FF3B5C", "verde": "#3DFF8A"},
        },
        "rewards": {"gifts": {"Rose": 1, "Galaxy": 60, "Lion": 300}},
    }


def novo(**kw) -> tuple[SimuladorLive, EventQueue]:
    fila = EventQueue()
    return SimuladorLive(fila, cfg(), **kw), fila


# --------------------------------------------------------------------------
# Ciclo de vida
# --------------------------------------------------------------------------


def test_comeca_desconectado():
    sim, _ = novo()

    assert sim.status.connected is False


def test_start_marca_conectado_com_detalhe_de_teste():
    sim, _ = novo()

    sim.start()

    assert sim.status.connected is True
    assert "teste" in sim.status.detail.lower()


def test_stop_encerra():
    sim, _ = novo()
    sim.start()

    sim.stop()

    assert sim.status.connected is False
    assert sim.status.detail == "encerrado"


def test_start_duas_vezes_nao_quebra():
    sim, _ = novo()
    sim.start()
    sim.start()

    assert sim.status.connected is True


# --------------------------------------------------------------------------
# Eventos individuais
# --------------------------------------------------------------------------


def test_comentar_enfileira_um_comentario():
    sim, fila = novo()

    evento = sim.comentar("@Joao", "H5")

    assert evento.type == EventType.COMMENT
    assert evento.text == "H5"
    assert evento.username == "joao"
    assert fila.size() == 1


def test_comentar_aceita_nome_de_exibicao():
    sim, _ = novo()

    evento = sim.comentar("joao", "H5", display_name="João Silva")

    assert evento.handle() == "joao"
    assert evento.actor() == "João Silva"


def test_comentar_inventa_um_apelido_quando_nao_se_diz_qual():
    """A HUD mostra apelido, nao handle — e o TikTok real manda nickname."""
    sim, _ = novo()

    evento = sim.comentar("maria", "A0")

    assert evento.handle() == "maria"
    assert evento.actor() == "Maria"


def test_comentar_com_apelido_vazio_cai_para_o_handle():
    """Nem todo mundo tem nickname; o fallback precisa ser alcancavel."""
    sim, _ = novo()

    evento = sim.comentar("maria", "A0", display_name="")

    assert evento.actor() == "maria"


def test_presentear_traz_nome_e_quantidade():
    sim, fila = novo()

    evento = sim.presentear("joao", "Galaxy", 3)

    assert evento.type == EventType.GIFT
    assert evento.gift_name == "Galaxy"
    assert evento.quantity == 3
    assert fila.size() == 1


def test_presente_de_teste_tem_id_estavel():
    """O `gift_id` entra na tabela `gifts`; dois eventos do mesmo presente
    nao podem gravar ids diferentes."""
    sim, _ = novo()

    a = sim.presentear("joao", "Rose", 1)
    b = sim.presentear("maria", "Rose", 1)

    assert a.gift_id == b.gift_id
    assert a.gift_id is not None


def test_presente_desconhecido_nao_quebra():
    sim, _ = novo()

    evento = sim.presentear("joao", "PresenteQueNaoExiste", 1)

    assert evento.gift_name == "PresenteQueNaoExiste"
    assert evento.gift_id is not None


def test_curtir_manda_o_incremento():
    sim, _ = novo()

    evento = sim.curtir("joao", 7)

    assert evento.type == EventType.LIKE
    assert evento.like_delta == 7
    assert evento.like_total == 7


def test_curtidas_somam_no_total():
    """O total precisa ser monotono, igual ao do TikTok de verdade."""
    sim, _ = novo()

    sim.curtir("joao", 5)
    sim.curtir("joao", 9)
    evento = sim.curtir("joao", 1)

    assert evento.like_delta == 1
    assert evento.like_total == 15


def test_curtida_zerada_ainda_e_enfileirada():
    """O simulador nao filtra: quem filtra e o adapter real. Aqui a gente
    quer poder mandar um evento estranho de proposito."""
    sim, fila = novo()

    sim.curtir("joao", 0)

    assert fila.size() == 1


def test_seguir_e_compartilhar():
    sim, fila = novo()

    sim.seguir("joao")
    sim.compartilhar("maria")

    primeiro = fila.get_nowait()
    segundo = fila.get_nowait()
    assert primeiro.type == EventType.FOLLOW
    assert segundo.type == EventType.SHARE


def test_entrar_enfileira_uma_chegada():
    sim, fila = novo()

    sim.entrar("joao")

    evento = fila.get_nowait()
    assert evento.type == EventType.JOIN
    assert evento.username == "joao"


# --------------------------------------------------------------------------
# Rajada
# --------------------------------------------------------------------------


def test_rajada_produz_exatamente_a_quantidade_pedida():
    sim, fila = novo(seed=1)

    eventos = sim.rajada(200)

    assert len(eventos) == 200
    assert fila.size() == 200


def test_rajada_e_reprodutivel_com_a_mesma_semente():
    """Um teste que falha so as vezes e um teste que ninguem conserta."""
    a, _ = novo(seed=99)
    b, _ = novo(seed=99)

    primeira = [(e.type, e.username, e.text, e.quantity) for e in a.rajada(50)]
    segunda = [(e.type, e.username, e.text, e.quantity) for e in b.rajada(50)]

    assert primeira == segunda


def test_rajada_com_cem_por_cento_de_coordenadas_pinta_o_canvas():
    sim, _ = novo(seed=7)

    eventos = sim.rajada(120, modo="pintura")
    coordenadas = [
        parse_coordenada(e.text, 26, 51) for e in eventos if e.type == EventType.COMMENT
    ]

    validas = [c for c in coordenadas if c is not None]
    assert len(validas) == len(coordenadas)
    assert len(validas) > 0


def test_rajada_misturada_tem_variedade():
    """Uma rajada so de presentes nao exercita o parser; so de comentarios
    nao exercita o credito. A mistura tem que ter os quatro tipos."""
    sim, _ = novo(seed=3)

    tipos = {e.type for e in sim.rajada(300)}

    assert EventType.COMMENT in tipos
    assert EventType.GIFT in tipos
    assert EventType.LIKE in tipos
    assert EventType.FOLLOW in tipos


def test_rajada_de_pintura_cobre_uma_area_do_canvas():
    """A graca do modo teste e encher a tela rapido para ver o desenho."""
    sim, _ = novo(seed=11)

    eventos = sim.rajada(400, modo="pintura")
    celulas = {
        (c.x, c.y)
        for c in (parse_coordenada(e.text, 26, 51) for e in eventos)
        if c is not None
    }

    assert len(celulas) > 20


def test_rajada_vazia_devolve_lista_vazia():
    sim, fila = novo(seed=1)

    assert sim.rajada(0) == []
    assert fila.size() == 0


def test_rajada_negativa_nao_quebra():
    sim, fila = novo(seed=1)

    assert sim.rajada(-5) == []
    assert fila.size() == 0


def test_rajada_usa_presentes_da_configuracao():
    sim, _ = novo(seed=5)

    nomes = {e.gift_name for e in sim.rajada(300) if e.type == EventType.GIFT}

    assert nomes <= {"Rose", "Galaxy", "Lion"}


# --------------------------------------------------------------------------
# Nomes
# --------------------------------------------------------------------------


def test_nomes_de_teste_sao_estaveis():
    """Mesma semente, mesma turma — senao o teste vira ruido."""
    assert nomes_de_teste(30, seed=4) == nomes_de_teste(30, seed=4)


def test_nomes_de_teste_sem_repeticao_dentro_de_uma_turma():
    nomes = nomes_de_teste(30, seed=4)

    assert len(set(nomes)) == 30


def test_nomes_de_teste_aceitam_pedir_mais_que_o_pool():
    """O pool tem tamanho fixo; pedir alem disso nao pode explodir."""
    nomes = nomes_de_teste(500, seed=4)

    assert len(nomes) == 500
    assert all(n.strip() for n in nomes)
