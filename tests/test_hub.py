"""O hub de WebSocket: agrupa, nao repassa.

O jogo roda a 20 quadros por segundo. Uma LIVE cheia manda muito mais evento
do que isso — uma rajada de presentes, uma enxurrada de coordenadas depois de
um evento de ARCO-IRIS. Mandar um pacote por evento seria mil chamadas de
`send` por segundo por espectador: a banda nao aguenta e o navegador passa
mais tempo decodificando JSON do que desenhando.

A regra tem duas metades, e a diferenca entre elas importa:

- **Evento** (pintou, presente, toast) ACUMULA. Cada um e um fato que
  aconteceu e que a tela precisa mostrar; nenhum pode sumir. Mas todos cabem
  num pacote so.
- **Estado** (ranking, stats) SUBSTITUI. Nao interessa o ranking de tres
  quadros atras; interessa o de agora. Mandar os tres seria mandar dois
  numeros que ja nasceram velhos.
"""

import asyncio
import logging
import time

import pytest

from backend.hub import WebSocketHub


class ClienteFalso:
    """Um WebSocket de mentira: guarda o que recebeu."""

    def __init__(self, nome="cliente", falha=False, trava=False):
        self.nome = nome
        self.falha = falha
        self.trava = trava
        self.recebidos: list[dict] = []
        self.envios = 0
        self.removido = False

    async def send_json(self, pacote: dict) -> None:
        self.envios += 1
        if self.trava:
            await asyncio.sleep(3600)
        if self.falha:
            raise RuntimeError("conexao caiu")
        self.recebidos.append(pacote)

    def tipos(self) -> list[str]:
        return [p["type"] for p in self.recebidos]


def pixel(x=7, y=5):
    return {
        "type": "pixel_painted",
        "x": x,
        "y": y,
        "coordinate": "H5",
        "color": "#FF3B5C",
        "user": "@joao",
    }


# --------------------------------------------------------------------------
# Agrupamento
# --------------------------------------------------------------------------


async def test_mil_publicacoes_viram_um_unico_envio():
    """Review Focus: sem agrupar, isto seriam 1000 chamadas de `send`."""
    hub = WebSocketHub(intervalo=0.05)
    cliente = ClienteFalso()
    hub.registrar(cliente)

    for i in range(1000):
        hub.publicar(pixel(x=i % 26, y=i // 26))

    await hub.despejar()

    assert cliente.envios == 1
    assert cliente.recebidos[0]["type"] == "pixels"
    assert len(cliente.recebidos[0]["items"]) == 1000


# --------------------------------------------------------------------------
# Console
# --------------------------------------------------------------------------


async def test_o_toast_tambem_sai_no_console(caplog):
    """Todo toast que vai para a tela deixa uma linha no terminal.

    A cena do OBS fica fora do alcance de quem esta ao vivo: sem este
    espelho, "o jogo avisou?" so se responde olhando o video. So o toast
    vale a linha — pixel pintado e volume e afogaria o console.
    """
    hub = WebSocketHub()

    with caplog.at_level(logging.INFO, logger="backend.hub"):
        hub.publicar({"type": "toast", "kind": "error", "text": "SEM PIXELS - joao"})
        hub.publicar(pixel())

    linhas = [r.getMessage() for r in caplog.records]
    assert sum("Toast na tela" in linha for linha in linhas) == 1
    assert any("SEM PIXELS - joao" in linha for linha in linhas)


async def test_o_lote_preserva_a_ordem_dos_eventos():
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    for i in range(5):
        hub.publicar(pixel(x=i))

    await hub.despejar()

    assert [item["x"] for item in cliente.recebidos[0]["items"]] == [0, 1, 2, 3, 4]


async def test_cada_item_mantem_a_forma_do_protocolo():
    """A tela le `x`, `y`, `color` direto do item — sem reembrulhar."""
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    hub.publicar(pixel())
    await hub.despejar()

    item = cliente.recebidos[0]["items"][0]
    assert item["type"] == "pixel_painted"
    assert item["coordinate"] == "H5"
    assert item["color"] == "#FF3B5C"


async def test_lote_vazio_nao_envia_nada():
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    await hub.despejar()

    assert cliente.envios == 0


async def test_despejar_duas_vezes_nao_repete_o_lote():
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    hub.publicar(pixel())
    await hub.despejar()
    await hub.despejar()

    assert cliente.envios == 1


# --------------------------------------------------------------------------
# Estado: so o ultimo importa
# --------------------------------------------------------------------------


async def test_ranking_publicado_tres_vezes_envia_so_o_ultimo():
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    for posicao in (1, 2, 3):
        hub.publicar({"type": "ranking", "items": [{"posicao": posicao}]})

    await hub.despejar()

    assert cliente.envios == 1
    assert cliente.recebidos[0]["type"] == "ranking"
    assert cliente.recebidos[0]["items"][0]["posicao"] == 3


async def test_stats_tambem_substituem():
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    hub.publicar({"type": "stats", "preenchidas": 1})
    hub.publicar({"type": "stats", "preenchidas": 99})

    await hub.despejar()

    assert cliente.recebidos[0]["preenchidas"] == 99


async def test_estados_de_tipos_diferentes_convivem():
    """Substituir e por TIPO: um ranking nao pode apagar as stats."""
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    hub.publicar({"type": "ranking", "items": []})
    hub.publicar({"type": "stats", "preenchidas": 5})

    await hub.despejar()

    assert sorted(cliente.tipos()) == ["ranking", "stats"]


async def test_pixels_e_estado_saem_juntos_no_mesmo_quadro():
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    hub.publicar(pixel())
    hub.publicar({"type": "ranking", "items": []})

    await hub.despejar()

    assert cliente.tipos() == ["pixels", "ranking"]


async def test_lote_sai_antes_do_estado():
    """A tela aplica os pixels e so depois repinta o ranking — se o ranking
    chegasse primeiro, ele mostraria uma posicao que ainda nao aconteceu."""
    hub = WebSocketHub()
    cliente = ClienteFalso()
    hub.registrar(cliente)

    hub.publicar({"type": "ranking", "items": []})
    hub.publicar(pixel())

    await hub.despejar()

    assert cliente.tipos() == ["pixels", "ranking"]


# --------------------------------------------------------------------------
# Clientes
# --------------------------------------------------------------------------


def test_contar_reflete_os_registros():
    hub = WebSocketHub()
    a, b = ClienteFalso("a"), ClienteFalso("b")

    hub.registrar(a)
    hub.registrar(b)
    assert hub.contar() == 2

    hub.desregistrar(a)
    assert hub.contar() == 1


def test_registrar_o_mesmo_cliente_duas_vezes_conta_uma():
    hub = WebSocketHub()
    cliente = ClienteFalso()

    hub.registrar(cliente)
    hub.registrar(cliente)

    assert hub.contar() == 1


def test_desregistrar_quem_nunca_entrou_nao_quebra():
    hub = WebSocketHub()

    hub.desregistrar(ClienteFalso())

    assert hub.contar() == 0


async def test_cliente_que_falha_e_removido_sem_derrubar_os_outros():
    """Review Focus #4: um celular que perdeu o sinal nao pode levar a sala."""
    hub = WebSocketHub()
    bom = ClienteFalso("bom")
    ruim = ClienteFalso("ruim", falha=True)
    outro = ClienteFalso("outro")

    for c in (bom, ruim, outro):
        hub.registrar(c)

    hub.publicar(pixel())
    await hub.despejar()

    assert hub.contar() == 2
    assert bom.recebidos and outro.recebidos
    assert ruim.recebidos == []


async def test_cliente_travado_e_removido_pelo_timeout():
    """Um cliente que aceita a conexao e nunca le entope o quadro inteiro."""
    hub = WebSocketHub(timeout_envio=0.05)
    preso = ClienteFalso("preso", trava=True)
    vivo = ClienteFalso("vivo")
    hub.registrar(preso)
    hub.registrar(vivo)

    hub.publicar(pixel())
    await asyncio.wait_for(hub.despejar(), timeout=2.0)

    assert hub.contar() == 1
    assert vivo.recebidos


async def test_publicar_sem_cliente_nao_quebra():
    hub = WebSocketHub()

    hub.publicar(pixel())
    await hub.despejar()

    assert hub.contar() == 0


async def test_entrar_no_meio_nao_recebe_o_que_passou():
    """Um espectador que chegou agora nao pode receber 500 pixels antigos."""
    hub = WebSocketHub()
    antigo = ClienteFalso("antigo")
    hub.registrar(antigo)

    for i in range(50):
        hub.publicar(pixel(x=i % 26))
    await hub.despejar()

    novo = ClienteFalso("novo")
    hub.registrar(novo)

    hub.publicar(pixel(x=1))
    await hub.despejar()

    assert antigo.envios == 2
    assert novo.envios == 1
    assert len(novo.recebidos[0]["items"]) == 1


# --------------------------------------------------------------------------
# Custo
# --------------------------------------------------------------------------


def test_publicar_dez_mil_vezes_e_barato():
    """Review Focus: `publicar` e chamado no caminho quente do jogo.

    Ele NAO pode fazer I/O, nao pode pegar lock global e nao pode alocar
    nada alem de uma entrada de lista."""
    hub = WebSocketHub()

    inicio = time.perf_counter()
    for i in range(10_000):
        hub.publicar(pixel(x=i % 26))
    gasto = time.perf_counter() - inicio

    assert gasto < 0.5, f"10.000 publicacoes levaram {gasto:.3f}s"


async def test_lote_e_limitado_e_descarta_o_mais_antigo():
    """Uma rajada absurda num quadro so nao pode virar um pacote de megabytes."""
    hub = WebSocketHub(max_lote=100)
    cliente = ClienteFalso()
    hub.registrar(cliente)

    for i in range(500):
        hub.publicar(pixel(x=i))
    await hub.despejar()

    itens = cliente.recebidos[0]["items"]
    assert len(itens) == 100
    # Sobreviveu o mais NOVO, como na `EventQueue`: num jogo ao vivo o evento
    # recente vale mais que o antigo.
    assert itens[-1]["x"] == 499
    assert itens[0]["x"] == 400


# --------------------------------------------------------------------------
# Ciclo de vida
# --------------------------------------------------------------------------


async def test_iniciar_e_parar():
    hub = WebSocketHub(intervalo=0.01)
    cliente = ClienteFalso()
    hub.registrar(cliente)

    await hub.iniciar()
    hub.publicar(pixel())
    await asyncio.sleep(0.1)
    await hub.parar()

    assert cliente.envios >= 1


async def test_iniciar_duas_vezes_nao_cria_dois_lacos():
    hub = WebSocketHub(intervalo=0.01)
    cliente = ClienteFalso()
    hub.registrar(cliente)

    await hub.iniciar()
    await hub.iniciar()
    hub.publicar(pixel())
    await asyncio.sleep(0.1)
    await hub.parar()

    assert cliente.envios == 1


async def test_parar_sem_iniciar_nao_quebra():
    hub = WebSocketHub()

    await hub.parar()

    assert hub.contar() == 0


async def test_parar_despeja_o_que_sobrou():
    """Os ultimos pixels antes de desligar nao podem ficar no buffer."""
    hub = WebSocketHub(intervalo=10.0)
    cliente = ClienteFalso()
    hub.registrar(cliente)

    await hub.iniciar()
    hub.publicar(pixel())
    await hub.parar()

    assert cliente.envios == 1


async def test_o_laco_nao_morre_se_um_quadro_falhar():
    """O laco tem que sobreviver a um erro; se ele morrer, a tela congela."""

    class ClienteExplosivo(ClienteFalso):
        async def send_json(self, pacote):
            raise ValueError("qualquer coisa")

    hub = WebSocketHub(intervalo=0.01)
    hub.registrar(ClienteExplosivo())

    await hub.iniciar()
    hub.publicar(pixel())
    await asyncio.sleep(0.05)

    # O laco continua vivo: um cliente novo ainda recebe.
    vivo = ClienteFalso()
    hub.registrar(vivo)
    hub.publicar(pixel())
    await asyncio.sleep(0.05)
    await hub.parar()

    assert vivo.envios >= 1
