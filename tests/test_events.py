"""O agendador dos eventos automaticos.

So o que importa de verdade esta aqui: o multiplicador (que mexe na economia),
o fim da janela (que devolve o preco ao normal) e o forcar do painel.

O relogio e injetado, entao uma janela de 60 segundos vira uma linha.
"""

from game.events import SchedulerEventos


class Relogio:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def avanca(self, segundos: float) -> None:
        self.t += segundos


def montar(cfg=None):
    relogio = Relogio()
    vistos = []
    sched = SchedulerEventos(cfg or {}, agora_fn=relogio, publicar=vistos.append, seed=1)
    return sched, relogio, vistos


def test_fora_de_evento_um_pixel_vale_um():
    sched, _, _ = montar()
    assert sched.multiplicador_pixels() == 1.0
    assert sched.estado() is None


def test_durante_o_evento_o_multiplicador_vale_e_depois_volta():
    """Review Focus: um evento que nao termina deixa a economia inflada
    para sempre — e ninguem percebe ate o ranking virar poeira."""
    sched, relogio, _ = montar()

    sched.forcar("pixel_turbo")
    assert sched.multiplicador_pixels() == 3.0

    relogio.avanca(29.0)
    sched.tick()
    assert sched.multiplicador_pixels() == 3.0, "acabou antes da hora"

    relogio.avanca(2.0)
    sched.tick()
    assert sched.multiplicador_pixels() == 1.0, "o evento nao terminou"
    assert sched.estado() is None


def test_forcar_chave_desconhecida_devolve_none():
    sched, _, _ = montar()
    assert sched.forcar("nao_existe") is None
    assert sched.multiplicador_pixels() == 1.0


def test_o_evento_avisa_a_tela_quando_comeca_e_quando_acaba():
    sched, relogio, vistos = montar()

    sched.forcar("arco_iris")
    relogio.avanca(61.0)
    sched.tick()

    tipos = [m["type"] for m in vistos]
    assert tipos == ["event_start", "event_end"]
    assert vistos[0]["name"] == "ARCO-ÍRIS"
    assert vistos[1]["key"] == "arco_iris"


def test_forcar_um_segundo_evento_encerra_o_primeiro():
    sched, _, vistos = montar()

    sched.forcar("caos")
    sched.forcar("pixel_turbo")

    assert [m["type"] for m in vistos] == ["event_start", "event_end", "event_start"]
    assert sched.multiplicador_pixels() == 3.0


def test_um_evento_automatico_chega_sozinho():
    sched, relogio, _ = montar({"events": {"first_after": 10, "interval": 60}})

    relogio.avanca(9.0)
    sched.tick()
    assert sched.estado() is None

    relogio.avanca(2.0)
    sched.tick()
    assert sched.estado() is not None


def test_com_os_eventos_desligados_o_sorteio_para_mas_o_painel_ainda_forca():
    """`events.active: false` e o freio de mao do streamer.

    Existe para o momento em que um evento atrapalha em vez de ajudar — um
    sorteio, uma fala, um convidado. O que ele desliga e o SORTEIO; forcar um
    evento pelo painel continua funcionando, senao nao haveria como voltar
    atras sem reiniciar o servidor no meio da LIVE.
    """
    sched, relogio, _ = montar(
        {"events": {"active": False, "first_after": 1, "interval": 1}}
    )

    relogio.avanca(600.0)
    for _ in range(50):
        sched.tick()
    assert sched.estado() is None, "sorteou um evento com os eventos desligados"

    assert sched.forcar("caos") is not None
    assert sched.multiplicador_pixels() == 1.5
