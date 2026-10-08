"""O servidor: a tela do OBS, o WebSocket e o painel de controle.

Este arquivo testa a unica superficie do sistema que fica exposta na rede
local. Duas preocupacoes governam o desenho, e as duas sao de seguranca:

1. **Nada fora das pastas de tela pode ser servido.** O projeto tem
   `config.json`, o banco `pixelworld.db` e o codigo-fonte na raiz. Um
   `StaticFiles` montado no diretorio errado, ou uma rota que aceite `..`,
   entrega tudo isso para quem abrir a porta.

2. **Nenhuma origem estranha pode dirigir o jogo.** O servidor roda em
   `localhost`. Sem cabecalhos de CORS, uma pagina qualquer que o streamer
   abra no navegador NAO consegue mandar `POST /api/simular` para ca. E o
   que impede que "abrir um link" vire "qualquer um pinta no seu canvas".

O cliente NUNCA pinta pelo WebSocket: pintura so nasce de evento do TikTok ou
do painel de controle. E o que impede que alguem abra o `localhost` e desenhe
de graca (spec §12).
"""

import json

import httpx
import pytest
from httpx import ASGITransport
from starlette.testclient import TestClient

from backend.app import criar_app
from backend.estado import EstadoJogo
from tiktok.base import AdapterStatus

COLS, ROWS = 26, 51

PALETA = {
    "vermelho": "#FF3B5C",
    "verde": "#3DFF8A",
    "azul": "#3D9BFF",
    "roxo": "#A855F7",
    "amarelo": "#FFD93D",
}


def cfg_teste(**over) -> dict:
    cfg = {
        "app": {"titulo": "PIXEL WORLD", "feed_size": 6, "events_per_frame": 400},
        "server": {"host": "127.0.0.1", "port": 8000, "frame_ms": 50},
        "canvas": {"cols": COLS, "rows": ROWS, "paleta": PALETA, "especiais": {}},
        "tiktok": {"username": "@criador", "cooldown_pintura": 0.0},
        "rewards": {
            "pixel_custo": 1,
            "sobrescrita_custo": 2,
            "presente_desconhecido": 1,
            "max_multiplicador": 10,
            "gifts": {"Rose": 1, "Galaxy": 60},
            "like": {"curtidas_por_pixel": 20, "max_pixels": 10},
            "follow": {"pixels": 5},
            "share": {"pixels": 3},
        },
        "limits": {"max_pixels_por_evento": 400},
    }
    cfg.update(over)
    return cfg


class Cenario:
    def __init__(self, estado, app, cliente):
        self.estado = estado
        self.app = app
        self.cliente = cliente

    async def get(self, url, **kw):
        return await self.cliente.get(url, **kw)

    async def post(self, url, **kw):
        return await self.cliente.post(url, **kw)

    async def delete(self, url, **kw):
        return await self.cliente.delete(url, **kw)

    async def simular(self, tipo="comentario", **campos):
        corpo = {"type": tipo, **campos}
        resposta = await self.post("/api/simular", json=corpo)
        await self.estado.processar_pendentes()
        return resposta


async def montar(tmp_path, **over) -> Cenario:
    estado = EstadoJogo(
        cfg_teste(**over), db_path=tmp_path / "app.db", modo_teste=True, seed=7
    )
    app = criar_app(estado)
    await estado.abrir()
    transporte = ASGITransport(app=app)
    cliente = httpx.AsyncClient(transport=transporte, base_url="http://test")
    return Cenario(estado, app, cliente)


def _receber(ws, segundos: float = 5.0):
    """`receive_json()` com prazo, para um fio quebrado FALHAR em vez de travar."""
    from concurrent.futures import ThreadPoolExecutor

    pool = ThreadPoolExecutor(max_workers=1)
    futuro = pool.submit(ws.receive_json)
    try:
        return futuro.result(timeout=segundos)
    finally:
        pool.shutdown(wait=False)


# --------------------------------------------------------------------------
# Tela do OBS
# --------------------------------------------------------------------------


async def test_raiz_devolve_200_e_html(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get("/")

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]


async def test_raiz_traz_o_titulo_do_jogo(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get("/")

    await c.estado.fechar()
    assert "PIXEL WORLD" in resposta.text


async def test_painel_de_controle_devolve_200(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get("/control")

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert "text/html" in resposta.headers["content-type"]


# --------------------------------------------------------------------------
# Path traversal — Review Focus #5
# --------------------------------------------------------------------------

# A raiz do projeto tem `config.json` (que aponta para a LIVE) e
# `pixelworld.db` (que tem o historico da comunidade). Servir qualquer um dos
# dois e um vazamento. Estas rotas tentam sair da pasta de telas.


@pytest.mark.parametrize(
    "caminho",
    [
        "/../config.json",
        "/%2e%2e/config.json",
        "/..%2fconfig.json",
        "/%2e%2e%2fconfig.json",
        "/ui/../../config.json",
        "/../pixelworld.db",
        "/../main.py",
        "/web.config",
        "/../.env",
        "/../requirements.txt",
    ],
)
async def test_travessia_de_caminho_nao_serve_a_raiz(tmp_path, caminho):
    c = await montar(tmp_path)

    resposta = await c.get(caminho)

    await c.estado.fechar()
    assert resposta.status_code != 200, f"`{caminho}` serviu a raiz do projeto!"
    assert "SEU_USUARIO" not in resposta.text


async def test_a_configuracao_nunca_sai_pelo_http(tmp_path):
    """A config aponta para a LIVE e nao pode ser publica."""
    c = await montar(tmp_path)

    for caminho in ("/config.json", "/ui/config.json", "/control/config.json"):
        resposta = await c.get(caminho)
        assert "tiktok" not in resposta.text.lower()

    await c.estado.fechar()


# --------------------------------------------------------------------------
# CORS — Review Focus #5
# --------------------------------------------------------------------------


async def test_o_servidor_nao_libera_origem_nenhuma(tmp_path):
    """Sem cabecalho de CORS, a pagina do OBS nao alcanca a API de controle
    a partir de outro site — e `localhost` sozinho ja e a defesa."""
    c = await montar(tmp_path)

    resposta = await c.get("/api/estado", headers={"Origin": "http://evil.test"})

    await c.estado.fechar()
    assert "access-control-allow-origin" not in resposta.headers


async def test_preflight_tambem_nao_libera(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.cliente.options(
        "/api/simular",
        headers={
            "Origin": "http://evil.test",
            "Access-Control-Request-Method": "POST",
        },
    )

    await c.estado.fechar()
    assert "access-control-allow-origin" not in resposta.headers


# --------------------------------------------------------------------------
# WebSocket
# --------------------------------------------------------------------------


def test_ws_manda_hello_com_o_canvas_ao_conectar(tmp_path):
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "ws.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        with cliente.websocket_connect("/ws") as ws:
            mensagem = ws.receive_json()

    assert mensagem["type"] == "hello"
    assert mensagem["canvas"]["cols"] == COLS
    assert mensagem["canvas"]["rows"] == ROWS


def test_ws_hello_traz_as_estatisticas(tmp_path):
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "ws.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        with cliente.websocket_connect("/ws") as ws:
            mensagem = ws.receive_json()

    assert mensagem["stats"]["total"] == COLS * ROWS
    assert mensagem["stats"]["filled"] == 0


def test_ws_hello_conta_o_evento_em_curso(tmp_path):
    """Quem conecta NO MEIO de um evento precisa ver o banner.

    Sem isto, um evento forçado antes de a pagina abrir some da tela: o
    multiplicador continua valendo (todo mundo ganha 3x) e o telao nao diz
    nada — a audiencia nao sabe por que os pixels estao rendendo mais, que e
    justamente o motivo de o evento existir. A pagina do OBS recarrega
    sozinha quando a cena fica ativa, entao isto acontece sozinho.
    """
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "ws.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        cliente.post("/api/evento", json={"key": "pixel_turbo"})
        with cliente.websocket_connect("/ws") as ws:
            hello = ws.receive_json()

    assert hello["type"] == "hello"
    assert hello["event"] is not None, "o hello chegou sem o evento em curso"
    assert hello["event"]["key"] == "pixel_turbo"
    assert hello["event"]["multiplier"] == 3.0
    assert hello["event"]["remaining"] > 0


def test_ws_hello_sem_evento_manda_none(tmp_path):
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "ws.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        with cliente.websocket_connect("/ws") as ws:
            hello = ws.receive_json()

    assert hello["event"] is None


def test_ws_hello_traz_as_celulas_ja_pintadas(tmp_path):
    """Quem chega no meio da LIVE precisa ver o desenho, nao um canvas vazio."""
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "ws.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        with cliente.websocket_connect("/ws") as ws:
            cliente.post(
                "/api/inventario", json={"user": "joao", "pixels": 10}
            )
            cliente.post(
                "/api/simular",
                json={"type": "comentario", "user": "joao", "text": "H5"},
            )
            hello = ws.receive_json()

    assert hello["type"] == "hello"
    assert hello["stats"]["filled"] >= 0


def test_ws_recebe_os_pixels_da_simulacao(tmp_path):
    """O caminho completo: painel -> fila -> pipeline -> hub -> tela."""
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "ws.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        with cliente.websocket_connect("/ws") as ws:
            ws.receive_json()  # hello

            cliente.post("/api/inventario", json={"user": "joao", "pixels": 10})
            cliente.post(
                "/api/simular",
                json={"type": "comentario", "user": "joao", "text": "H5"},
            )

            # `receive_json()` sem prazo PENDURA quando o fio esta quebrado:
            # o teste nunca falha, so trava. Receber numa thread com limite
            # transforma "nao chegou nada" em falha, que e o que se quer ler.
            tipos = []
            pacote = None
            for _ in range(20):
                pacote = _receber(ws)
                tipos.append(pacote["type"])
                if pacote["type"] == "pixels":
                    break

    assert "pixels" in tipos, f"nenhum quadro de pixels chegou: {tipos}"
    itens = pacote["items"]
    assert any(i["type"] == "pixel_painted" for i in itens)


# --------------------------------------------------------------------------
# API de controle — simulacao
# --------------------------------------------------------------------------


async def test_simular_comentario_com_coordenada_pinta(tmp_path):
    """Review Focus: o caminho do painel e o mesmo caminho da LIVE."""
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})

    await c.simular(tipo="comentario", user="joao", text="H5")

    celula = c.estado.canvas.celula(7, 5)
    await c.estado.fechar()
    assert celula.pintada is True
    assert celula.owner_id == "joao"


async def test_simular_comentario_gasta_o_pixel(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 3})

    await c.simular(tipo="comentario", user="joao", text="H5")

    saldo = c.estado.inventario.saldo("joao")
    await c.estado.fechar()
    assert saldo == 2


async def test_simular_sem_saldo_nao_pinta(tmp_path):
    c = await montar(tmp_path)

    await c.simular(tipo="comentario", user="joao", text="H5")

    await c.estado.fechar()
    assert c.estado.canvas.celula(7, 5).pintada is False


async def test_simular_comentario_invalido_nao_pinta(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})

    await c.simular(tipo="comentario", user="joao", text="A51")

    await c.estado.fechar()
    assert c.estado.canvas.preenchidas() == 0


async def test_o_historico_do_pixel_fala_a_lingua_de_quem_le(tmp_path):
    """O banco guarda `owner_id`/`painted_at`; o painel le `user`/`timestamp`.

    Enquanto os nomes de dentro do banco atravessavam a rede, o painel
    desenhava as amostras de cor e deixava as colunas de quem e quando em
    branco: um recurso que nao mostra nada e nao reclama. E a mesma regra que
    vale para o resto do que trafega — nomes internos ficam dentro.
    """
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    resposta = await c.get("/api/pixel/7/5")

    await c.estado.fechar()
    historico = resposta.json()["history"]
    assert len(historico) == 1
    assert historico[0]["user"] == "joao"
    assert historico[0]["timestamp"]


async def test_canvas_largo_aceita_a_ultima_coluna_e_recusa_a_de_fora(tmp_path):
    """Alargar o canvas e so mexer no config — mas o limite tem que valer.

    Com 50 colunas, `AX50` e a ultima celula da grade e `AY5` ja caiu fora
    dela. Quem separa as duas nao e o parser (ele nao conhece o tamanho do
    mapa de proposito), e sim o canvas. Por isso o teste atravessa o
    caminho inteiro — comentario entra, pixel sai — em vez de chamar
    `parse_coordenada` direto.
    """
    c = await montar(
        tmp_path,
        canvas={"cols": 50, "rows": 51, "paleta": PALETA, "especiais": {}},
    )
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})

    await c.simular(tipo="comentario", user="joao", text="AX50")
    await c.simular(tipo="comentario", user="joao", text="AY5")

    await c.estado.fechar()
    assert c.estado.canvas.celula(49, 50).pintada is True
    assert c.estado.canvas.preenchidas() == 1


async def test_simular_presente_credita(tmp_path):
    c = await montar(tmp_path)

    await c.simular(tipo="presente", user="maria", gift="Rose", quantity=5)

    saldo = c.estado.inventario.saldo("maria")
    await c.estado.fechar()
    assert saldo == 5


async def test_simular_curtida_credita_no_acumulador(tmp_path):
    c = await montar(tmp_path)

    await c.simular(tipo="curtida", user="ana", quantity=20)

    saldo = c.estado.inventario.saldo("ana")
    await c.estado.fechar()
    assert saldo == 1


async def test_simular_seguir_credita(tmp_path):
    c = await montar(tmp_path)

    await c.simular(tipo="seguir", user="bia")

    saldo = c.estado.inventario.saldo("bia")
    await c.estado.fechar()
    assert saldo == 5


async def test_simular_compartilhar_credita(tmp_path):
    c = await montar(tmp_path)

    await c.simular(tipo="compartilhar", user="caio")

    saldo = c.estado.inventario.saldo("caio")
    await c.estado.fechar()
    assert saldo == 3


async def test_simular_tipo_desconhecido_e_recusado(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post(
        "/api/simular", json={"type": "existe_isso_nao", "user": "joao"}
    )

    await c.estado.fechar()
    assert resposta.status_code == 422


async def test_simular_sem_username_e_recusado(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post("/api/simular", json={"type": "comentario", "text": "H5"})

    await c.estado.fechar()
    assert resposta.status_code == 422


async def test_simular_comentario_sem_texto_e_recusado(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post(
        "/api/simular", json={"type": "comentario", "user": "joao"}
    )

    await c.estado.fechar()
    assert resposta.status_code == 422


class FonteFalsa:
    """Uma fonte que NAO e o simulador — e a LIVE de verdade.

    Tem `start`, `stop` e `status` porque e isso que o estado do jogo usa
    no ciclo de vida, mas nao sabe inventar evento nenhum.
    """

    def __init__(self):
        self._status = AdapterStatus()

    @property
    def status(self) -> AdapterStatus:
        return self._status

    def start(self) -> None:
        self._status = AdapterStatus(connected=True, detail="conectado a LIVE")

    def stop(self) -> None:
        self._status = AdapterStatus(connected=False, detail="encerrado")


async def test_simular_fora_do_modo_teste_avisa_em_vez_de_explodir(tmp_path):
    """Com a LIVE de verdade conectada os botoes de simulacao nao tem para
    onde ir. Um 500 ali faria o streamer achar que o painel quebrou."""
    c = await montar(tmp_path)
    c.estado.fonte = FonteFalsa()

    resposta = await c.post(
        "/api/simular", json={"type": "comentario", "user": "joao", "text": "H5"}
    )

    await c.estado.fechar()
    assert resposta.status_code == 409


async def test_rajada_fora_do_modo_teste_tambem_avisa(tmp_path):
    c = await montar(tmp_path)
    c.estado.fonte = FonteFalsa()

    resposta = await c.post("/api/burst", json={"count": 10})

    await c.estado.fechar()
    assert resposta.status_code == 409


async def test_inventario_duas_vezes_com_o_mesmo_valor_nao_soma(tmp_path):
    """O botao do painel DEFINE o saldo. Se somasse, clicar duas vezes "50"
    daria 100 e o streamer nao teria como repetir um teste."""
    c = await montar(tmp_path)

    await c.post("/api/inventario", json={"user": "joao", "pixels": 50})
    await c.post("/api/inventario", json={"user": "joao", "pixels": 50})

    saldo = c.estado.inventario.saldo("joao")
    await c.estado.fechar()
    assert saldo == 50


async def test_o_feed_mostra_a_pintura_mais_nova_primeiro(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")
    await c.simular(tipo="comentario", user="joao", text="H6")

    dados = (await c.get("/api/estado")).json()

    await c.estado.fechar()
    assert dados["feed"][0]["coordinate"] == "H6"
    assert dados["feed"][1]["coordinate"] == "H5"


# --------------------------------------------------------------------------
# API de controle — estado
# --------------------------------------------------------------------------


async def test_estado_traz_o_snapshot(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get("/api/estado")

    await c.estado.fechar()
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["canvas"]["cols"] == COLS
    assert dados["canvas"]["rows"] == ROWS
    assert dados["canvas"]["total"] == COLS * ROWS
    assert dados["canvas"]["filled"] == 0


async def test_estado_conta_usuarios_e_cores(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    dados = (await c.get("/api/estado")).json()

    await c.estado.fechar()
    assert dados["canvas"]["filled"] == 1
    assert dados["users"] >= 1
    assert dados["colors"] >= 1


async def test_estado_traz_o_ranking(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    dados = (await c.get("/api/estado")).json()

    await c.estado.fechar()
    assert dados["ranking"][0]["handle"] == "joao"
    assert dados["ranking"][0]["pixels"] == 1
    assert "title" in dados["ranking"][0]


async def test_estado_traz_o_ultimo_feed(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    dados = (await c.get("/api/estado")).json()

    await c.estado.fechar()
    assert dados["feed"][0]["coordinate"] == "H5"


async def test_estado_traz_o_status_da_fonte(tmp_path):
    c = await montar(tmp_path)

    dados = (await c.get("/api/estado")).json()

    await c.estado.fechar()
    assert dados["fonte"]["connected"] is True
    assert "teste" in dados["fonte"]["detail"].lower()


# --------------------------------------------------------------------------
# API de controle — pixels
# --------------------------------------------------------------------------


async def test_pixel_traz_a_celula(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    resposta = await c.get("/api/pixel/7/5")

    await c.estado.fechar()
    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["coordinate"] == "H5"
    assert dados["user"] == "@joao"
    assert dados["color"]


async def test_pixel_virgem_tambem_responde(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get("/api/pixel/0/0")

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert resposta.json()["color"] is None


async def test_pixel_fora_do_canvas_e_404(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get(f"/api/pixel/{COLS}/0")

    await c.estado.fechar()
    assert resposta.status_code == 404


async def test_pixel_traz_o_historico(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.post("/api/inventario", json={"user": "maria", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")
    await c.simular(tipo="comentario", user="maria", text="H5")

    dados = (await c.get("/api/pixel/7/5")).json()

    await c.estado.fechar()
    assert len(dados["history"]) == 2
    assert dados["user"] == "@maria"


async def test_apagar_pixel_limpa_a_celula(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    resposta = await c.delete("/api/pixel/7/5")

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert c.estado.canvas.celula(7, 5).pintada is False
    assert c.estado.canvas.preenchidas() == 0


async def test_apagar_pixel_virgem_nao_quebra(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.delete("/api/pixel/0/0")

    await c.estado.fechar()
    assert resposta.status_code == 200


async def test_apagar_fora_do_canvas_e_404(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.delete(f"/api/pixel/0/{ROWS}")

    await c.estado.fechar()
    assert resposta.status_code == 404


# --------------------------------------------------------------------------
# API de controle — inventario e rajada
# --------------------------------------------------------------------------


async def test_inventario_credita_pixels(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post(
        "/api/inventario", json={"user": "@Joao", "pixels": 50}
    )

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert c.estado.inventario.saldo("joao") == 50


async def test_inventario_negativo_e_recusado(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post(
        "/api/inventario", json={"user": "joao", "pixels": -5}
    )

    await c.estado.fechar()
    assert resposta.status_code == 422


async def test_inventario_zerado_e_aceito(tmp_path):
    """Zerar o saldo de alguem e uma operacao legitima do painel."""
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 50})

    resposta = await c.post("/api/inventario", json={"user": "joao", "pixels": 0})

    await c.estado.fechar()
    assert resposta.status_code == 200


async def test_burst_enfileira_a_quantidade_pedida(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post("/api/burst", json={"count": 200})

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert resposta.json()["queued"] == 200


async def test_burst_nao_trava_o_servidor(tmp_path):
    """Review Focus: o botao de 200 eventos existe para testar carga."""
    c = await montar(tmp_path)

    resposta = await c.post("/api/burst", json={"count": 2000})

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert resposta.json()["queued"] == 2000


async def test_burst_maior_que_o_teto_e_recusado(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post("/api/burst", json={"count": 999_999})

    await c.estado.fechar()
    assert resposta.status_code == 422


async def test_burst_negativo_e_recusado(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.post("/api/burst", json={"count": -1})

    await c.estado.fechar()
    assert resposta.status_code == 422


# --------------------------------------------------------------------------
# API de controle — evento forcado (depende do scheduler, Task 11)
# --------------------------------------------------------------------------


async def test_forcar_evento_sem_scheduler_avisa(tmp_path):
    c = await montar(tmp_path)
    c.estado.scheduler = None

    resposta = await c.post("/api/evento", json={"key": "turbo"})

    await c.estado.fechar()
    assert resposta.status_code == 503


async def test_forcar_evento_com_scheduler_usa_a_chave(tmp_path):
    c = await montar(tmp_path)
    c.estado.scheduler = SchedulerFalso()

    resposta = await c.post("/api/evento", json={"key": "turbo"})

    await c.estado.fechar()
    assert resposta.status_code == 200
    assert c.estado.scheduler.forcados == ["turbo"]


async def test_forcar_evento_inexistente_e_404(tmp_path):
    c = await montar(tmp_path)
    c.estado.scheduler = SchedulerFalso(conhecidos={"turbo"})

    resposta = await c.post("/api/evento", json={"key": "nao_existe"})

    await c.estado.fechar()
    assert resposta.status_code == 404


class SchedulerFalso:
    def __init__(self, conhecidos=None):
        self.conhecidos = conhecidos
        self.forcados = []

    def forcar(self, chave):
        if self.conhecidos is not None and chave not in self.conhecidos:
            return None
        self.forcados.append(chave)
        return {"key": chave, "name": chave.upper(), "ends_at": 0}


# --------------------------------------------------------------------------
# Erros
# --------------------------------------------------------------------------


async def test_rota_desconhecida_e_404(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.get("/nao_existe_isso")

    await c.estado.fechar()
    assert resposta.status_code == 404


async def test_metodo_errado_e_405(tmp_path):
    c = await montar(tmp_path)

    resposta = await c.delete("/api/estado")

    await c.estado.fechar()
    assert resposta.status_code == 405


# --------------------------------------------------------------------------
# O estado do jogo
# --------------------------------------------------------------------------


async def test_abrir_duas_vezes_nao_quebra(tmp_path):
    c = await montar(tmp_path)

    await c.estado.abrir()
    await c.estado.abrir()

    await c.estado.fechar()


async def test_o_canvas_sobrevive_a_um_reinicio(tmp_path):
    """Persistencia e obrigatoria: o desenho nao pode sumir ao reiniciar."""
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")
    await c.estado.fechar()

    de_novo = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "app.db", modo_teste=True, seed=7
    )
    await de_novo.abrir()

    celula = de_novo.canvas.celula(7, 5)
    preenchidas = de_novo.canvas.preenchidas()
    await de_novo.fechar()

    assert celula.pintada is True
    assert celula.owner_id == "joao"
    assert preenchidas == 1


async def test_o_ranking_sobrevive_a_um_reinicio(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")
    await c.estado.fechar()

    de_novo = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "app.db", modo_teste=True, seed=7
    )
    await de_novo.abrir()
    entrada = de_novo.ranking.entrada("joao")
    await de_novo.fechar()

    assert entrada is not None
    assert entrada.pixels == 1


async def test_processar_pendentes_sem_evento_nao_faz_nada(tmp_path):
    c = await montar(tmp_path)

    await c.estado.processar_pendentes()

    await c.estado.fechar()
    assert c.estado.canvas.preenchidas() == 0


async def test_processar_pendentes_nao_repete_o_mesmo_evento(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.post(
        "/api/simular",
        json={"type": "comentario", "user": "joao", "text": "H5"},
    )

    await c.estado.processar_pendentes()
    await c.estado.processar_pendentes()

    saldo = c.estado.inventario.saldo("joao")
    await c.estado.fechar()
    assert saldo == 9


async def test_o_estado_e_serializavel_em_json(tmp_path):
    c = await montar(tmp_path)
    await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
    await c.simular(tipo="comentario", user="joao", text="H5")

    texto = json.dumps((await c.get("/api/estado")).json())

    await c.estado.fechar()
    assert "joao" in texto


# --------------------------------------------------------------------------
# API de controle — limpar o quadro
# --------------------------------------------------------------------------


async def test_limpar_apaga_todo_o_canvas(tmp_path):
    """O botao LIMPAR do painel: uma chamada, o quadro inteiro em branco."""
    c = await montar(tmp_path)
    try:
        await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
        await c.simular(tipo="comentario", user="joao", text="H5")
        assert c.estado.canvas.preenchidas() == 1

        resposta = await c.delete("/api/canvas")

        assert resposta.status_code == 200
        assert resposta.json()["ok"] is True
        assert c.estado.canvas.preenchidas() == 0
        assert c.estado.canvas.celulas_pintadas() == []
    finally:
        await c.cliente.aclose()
        await c.estado.fechar()


async def test_limpar_apaga_o_canvas_no_disco_tambem(tmp_path):
    """Limpar so na memoria faria o desenho REAPARECER no proximo reinicio.

    O canvas e a unica coisa que sobrevive a um restart. Um LIMPAR que nao
    chega ao banco e uma mentira que so se descobre no dia seguinte, com a
    LIVE ja no ar.
    """
    c = await montar(tmp_path)
    try:
        await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
        await c.simular(tipo="comentario", user="joao", text="H5")

        await c.delete("/api/canvas")

        assert await c.estado.db.carregar_canvas() == []
    finally:
        await c.cliente.aclose()
        await c.estado.fechar()


async def test_limpar_publica_o_aviso_para_a_tela(tmp_path):
    """A tela do OBS so sabe limpar se alguem contar para ela.

    Sem esta mensagem o quadro do servidor fica vazio e o da transmissao
    continua cheio — a pior das divergencias, porque as duas telas parecem
    certas e quem olha o painel acha que o LIMPAR nao funcionou.
    """
    estado = EstadoJogo(
        cfg_teste(), db_path=tmp_path / "limpar.db", modo_teste=True, seed=1
    )
    app = criar_app(estado)

    with TestClient(app) as cliente:
        with cliente.websocket_connect("/ws") as ws:
            ws.receive_json()  # hello

            cliente.post("/api/inventario", json={"user": "joao", "pixels": 10})
            cliente.post(
                "/api/simular",
                json={"type": "comentario", "user": "joao", "text": "H5"},
            )
            cliente.delete("/api/canvas")

            achou = None
            for _ in range(30):
                pacote = _receber(ws)
                itens = pacote["items"] if pacote["type"] == "pixels" else [pacote]
                for item in itens:
                    if item["type"] == "grid_cleared":
                        achou = item
                        break
                if achou:
                    break

    assert achou is not None, "a tela nunca soube que o quadro foi limpo"


async def test_depois_de_limpar_o_quadro_aceita_pintura_de_novo(tmp_path):
    """LIMPAR nao pode deixar o jogo num estado de onde ele nao volta.

    E o risco real de um botao destrutivo: se ele travar a pintura, o
    streamer limpa o quadro no ar e a LIVE morre ali — sem erro nenhum na
    tela, so ninguem mais conseguindo pintar.
    """
    c = await montar(tmp_path)
    try:
        await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
        await c.simular(tipo="comentario", user="joao", text="H5")

        # A resposta e conferida ANTES do resto: sem esta linha o teste passa
        # mesmo com a rota faltando (o DELETE vira um 404 silencioso, o quadro
        # nunca e limpo, e a pintura seguinte "funciona" porque nao havia o
        # que apagar). Foi assim que este teste passou no RED.
        limpeza = await c.delete("/api/canvas")
        assert limpeza.status_code == 200, limpeza.text
        assert c.estado.canvas.preenchidas() == 0, "nao limpou antes de repintar"

        await c.simular(tipo="comentario", user="joao", text="H5")

        assert c.estado.canvas.preenchidas() == 1
        assert c.estado.canvas.celula(7, 5).color is not None
    finally:
        await c.cliente.aclose()
        await c.estado.fechar()


async def test_limpar_nao_apaga_o_ranking(tmp_path):
    """A decisao que este botao NAO toma.

    Limpar o quadro e apagar o DESENHO. Apagar o ranking seria apagar a
    participacao de quem mandou rosa a LIVE inteira — ninguem pediu isso, e
    nao tem volta. O placar fica de pe enquanto o quadro fica em branco.
    """
    c = await montar(tmp_path)
    try:
        await c.post("/api/inventario", json={"user": "joao", "pixels": 10})
        await c.simular(tipo="comentario", user="joao", text="H5")
        assert c.estado.ranking.total() >= 1
        quem_pintou = c.estado.canvas.celula(7, 5).owner_id

        limpeza = await c.delete("/api/canvas")
        assert limpeza.status_code == 200, limpeza.text

        assert c.estado.canvas.preenchidas() == 0, "o teste nao limpou nada"
        ranking = c.estado.ranking.top_para_dict()
        assert any(linha.get("user") == f"@{quem_pintou}" for linha in ranking), (
            "o placar perdeu quem pintou: o LIMPAR levou a participacao junto"
        )
    finally:
        await c.cliente.aclose()
        await c.estado.fechar()
