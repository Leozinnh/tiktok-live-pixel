"""O agendador dos eventos automaticos.

So o que importa de verdade esta aqui: o multiplicador (que mexe na economia),
o fim da janela (que devolve o preco ao normal) e o forcar do painel.

O relogio e injetado, entao uma janela de 60 segundos vira uma linha.
"""

from game.events import CATALOGO_PADRAO, SchedulerEventos


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
    # O nome tambem vai no FIM, e nao so a chave: quem le a mensagem de fim e
    # a VOZ (ver `backend/estado.py`), e "arco_iris" nao se pronuncia.
    assert vistos[1]["name"] == "ARCO-ÍRIS"
    assert vistos[1]["emoji"] == "🌈"


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


def test_o_sorteio_nunca_repete_o_evento_anterior():
    """Dois CAOS seguidos leem como "so tem esse evento hoje".

    O anterior entra pela porta de tras de proposito: `forcar` e o caminho do
    painel, e o sorteio tem que respeitar o forcado tambem — por isso o
    `_ultimo` e marcado no `_comecar`, por onde os dois passam.
    """
    sched, relogio, vistos = montar({"events": {"first_after": 1, "interval": 10}})

    sched.forcar("caos")
    relogio.avanca(21.0)  # o CAOS dura 20
    sched.tick()  # encerra

    relogio.avanca(20.0)  # cobre qualquer folga de 10s
    sched.tick()  # sorteia o proximo

    inicios = [m for m in vistos if m["type"] == "event_start"]
    assert [m["key"] for m in inicios][0] == "caos"
    assert len(inicios) == 2
    assert inicios[1]["key"] != "caos", "o sorteio repetiu o evento anterior"


def test_o_intervalo_nao_e_um_metronomo():
    """A folga de +-25%: duas provas na mesma rodada.

    Um vaozinho de cada vez nao provaria nada (o sorteio podia estar cravado
    num valor so e calhar de ser diferente da media); o que prova e a serie:
    TODOS dentro da folga — um disparo a esmo seria pior que o metronomo — e
    nem todos iguais.
    """
    relogio = Relogio()
    vistos: list[tuple[float, dict]] = []
    sched = SchedulerEventos(
        {"events": {"first_after": 1, "interval": 10}},
        agora_fn=relogio,
        publicar=lambda m: vistos.append((relogio.t, m)),
        seed=1,
    )

    passos = 0
    while (
        sum(1 for _, m in vistos if m["type"] == "event_start") < 6 and passos < 4000
    ):
        relogio.avanca(0.25)
        sched.tick()
        passos += 1

    inicios = [t for t, m in vistos if m["type"] == "event_start"]
    fins = [t for t, m in vistos if m["type"] == "event_end"]
    assert len(inicios) == 6

    # O `tick` so olha o relogio de 0,25s em 0,25s, entao um vao pode passar
    # do teto nesse tanto.
    vaos = [inicios[i + 1] - fins[i] for i in range(len(fins))]
    assert all(7.5 - 0.25 <= vao <= 12.5 + 0.25 for vao in vaos), vaos
    assert len(set(vaos)) > 1, f"todos os vaos iguais: {vaos}"


def test_o_catalogo_padrao_tem_os_eventos_novos():
    """Cada evento novo mora em DOIS lugares: aqui e no `config.json` — e o
    catalogo do config SUBSTITUI o padrao inteiro. Se um deles ficar para tras
    num dos dois, o evento simplesmente nao existe daquele lado, e com um
    arquivo so o defeito nao aparece. (O outro lado — o efeito existir no
    desenho da tela — e o teste "todo efeito do config.json desenha" do
    `ui/js/eventos.test.mjs`.)
    """
    por_chave = {e["key"]: e for e in CATALOGO_PADRAO}

    for chave in [
        "tempestade",
        "codigo",
        "negativo",
        "fogos",
        "neve",
        "arcade",
        "filme",
    ]:
        definicao = por_chave[chave]
        assert definicao["effect"] == chave
        assert definicao["weight"] > 0, "peso zero: o evento nunca sai no sorteio"
        assert definicao["duration"] >= 15, "curto demais para o efeito ser visto"
        assert definicao["name"] and definicao["emoji"]
