"""A API do painel de controle.

Este e o unico caminho pelo qual uma pessoa (o streamer) mexe no jogo a mao.
Ele existe por tres motivos, e os tres sao de operacao ao vivo:

1. **Ensaiar sem LIVE.** O painel simula comentario, presente, curtida,
   seguidor e compartilhamento. O evento entra pela MESMA fila que a fonte
   real usa, entao o que se testa aqui e o jogo de verdade — nao um caminho
   paralelo que so existe no teste (spec §14).
2. **Consertar ao vivo.** Apagar um pixel que alguem pintou de zoeira, dar
   pixels para quem mandou presente e o sistema perdeu, ou esvaziar o quadro
   inteiro (`DELETE /api/canvas`) quando o desenho virou bagunça.
3. **Medir.** `/api/estado` e o que o painel le para mostrar ranking, feed e
   o status da conexao com o TikTok.

O corpo das requisicoes fala o vocabulario do spec §12 (`type`, `user`,
`text`, `gift`, `quantity`, `count`, `key`) mesmo com os nomes internos em
portugues: a fronteira de rede e uma so no projeto inteiro, e ter duas
seria pior do que ter uma em ingles.
"""

import logging

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from game.ranking import normalizar
from tiktok.simulado import SimuladorLive

logger = logging.getLogger(__name__)

# Os botoes do painel, como o streamer os le. Sao rotulos de operacao, nao
# os valores de `EventType` — a traducao entre os dois e o que este modulo faz.
TIPOS_DE_SIMULACAO = frozenset(
    {"comentario", "presente", "curtida", "seguir", "compartilhar", "entrar"}
)

TETO_DA_RAJADA = 5000
LIMITE_DO_HISTORICO = 20

TEXTO_SEM_SIMULADOR = (
    "A fonte conectada e a LIVE de verdade — nao da para inventar evento nela."
)


# --------------------------------------------------------------------------
# Corpos das requisicoes
# --------------------------------------------------------------------------


class PedidoSimular(BaseModel):
    """Um evento falso, com a forma de um evento de verdade."""

    tipo: str = Field(alias="type")
    usuario: str = Field(alias="user")
    texto: str | None = Field(default=None, alias="text")
    presente: str = Field(default="Rose", alias="gift")
    quantidade: int = Field(default=1, alias="quantity")

    @field_validator("tipo")
    @classmethod
    def _tipo_conhecido(cls, valor: str) -> str:
        chave = (valor or "").strip().lower()
        if chave not in TIPOS_DE_SIMULACAO:
            raise ValueError(
                f"tipo desconhecido: {valor!r}. Use um de {sorted(TIPOS_DE_SIMULACAO)}."
            )
        return chave

    @field_validator("usuario")
    @classmethod
    def _usuario_com_nome(cls, valor: str) -> str:
        limpo = (valor or "").strip()
        if not limpo:
            # Sem autor nao ha a quem creditar. O pipeline tambem descarta
            # eventos sem autor, mas aqui a recusa precisa ser VISIVEL: quem
            # digitou errado no painel tem que ver o erro.
            raise ValueError("usuario vazio")
        return limpo

    @model_validator(mode="after")
    def _comentario_precisa_de_texto(self):
        if self.tipo == "comentario" and not (self.texto or "").strip():
            raise ValueError("comentario sem texto: nao ha o que o parser leia")
        return self


class PedidoInventario(BaseModel):
    usuario: str = Field(alias="user")
    pixels: int = Field(ge=0)


class PedidoRajada(BaseModel):
    quantos: int = Field(alias="count", ge=0, le=TETO_DA_RAJADA)


class PedidoEvento(BaseModel):
    chave: str = Field(alias="key")


# --------------------------------------------------------------------------
# Rotas
# --------------------------------------------------------------------------


def _exigir_simulador(estado) -> SimuladorLive:
    """A simulacao so existe no MODO TESTE.

    Fora dele a resposta e um 409 explicando, nao um 500: o streamer que
    abre o painel com a LIVE no ar precisa entender por que o botao nao
    funciona, e nao ver um erro de servidor.
    """
    fonte = estado.fonte
    if not isinstance(fonte, SimuladorLive):
        raise HTTPException(status_code=409, detail=TEXTO_SEM_SIMULADOR)
    return fonte


def montar_controle(app: FastAPI, estado) -> None:
    """Registra as rotas do painel. Chamado por `criar_app`."""
    router = APIRouter(prefix="/api")

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    @router.get("/estado")
    async def ler_estado() -> dict:
        return estado.snapshot()

    @router.get("/pixel/{x}/{y}")
    async def ler_pixel(x: int, y: int) -> dict:
        celula = estado.canvas.celula(x, y)
        if celula is None:
            raise HTTPException(
                status_code=404,
                detail=f"Coordenada fora do canvas {estado.canvas.cols}x{estado.canvas.rows}.",
            )

        dados = celula.para_dict()
        dados["history"] = [
            {
                "x": linha.get("x"),
                "y": linha.get("y"),
                "color": linha.get("color"),
                "effect": linha.get("effect"),
                # O banco chama estas colunas de `owner_id` e `painted_at`.
                # Quem le e o painel, que procura `user` e `timestamp` — os
                # nomes do spec §12, iguais aos do resto do que trafega. Sem
                # esta traducao o historico aparecia com as amostras de cor e
                # as duas colunas em branco, e ninguem descobria por que.
                "user": linha.get("owner_id"),
                "timestamp": linha.get("painted_at"),
            }
            for linha in await estado.db.historico_pixel(x, y, LIMITE_DO_HISTORICO)
        ]
        return dados

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    @router.post("/simular")
    async def simular(pedido: PedidoSimular) -> dict:
        """Enfileira um evento falso. O jogo o trata como qualquer outro."""
        fonte = _exigir_simulador(estado)
        usuario = normalizar(pedido.usuario)

        if pedido.tipo == "comentario":
            fonte.comentar(usuario, pedido.texto or "")
        elif pedido.tipo == "presente":
            fonte.presentear(usuario, pedido.presente, pedido.quantidade)
        elif pedido.tipo == "curtida":
            fonte.curtir(usuario, pedido.quantidade)
        elif pedido.tipo == "seguir":
            fonte.seguir(usuario)
        elif pedido.tipo == "entrar":
            fonte.entrar(usuario)
        else:
            fonte.compartilhar(usuario)

        return {"ok": True, "type": pedido.tipo, "queued": estado.fila.size()}

    @router.post("/inventario")
    async def inventario(pedido: PedidoInventario) -> dict:
        """Crava o saldo de alguem. Nao e credito: e o valor dito.

        O jogo so CREDITA (`adicionar`). Aqui e DEFINIR, porque o painel e
        usado para repetir um teste — clicar duas vezes "50" tem que dar 50.
        """
        saldo = estado.inventario.definir(pedido.usuario, pedido.pixels)
        return {"ok": True, "user": normalizar(pedido.usuario), "balance": saldo}

    @router.post("/burst")
    async def rajada(pedido: PedidoRajada) -> dict:
        """Uma rajada de eventos de uma vez, para medir carga."""
        fonte = _exigir_simulador(estado)
        eventos = fonte.rajada(pedido.quantos)
        return {"ok": True, "queued": len(eventos)}

    @router.delete("/pixel/{x}/{y}")
    async def apagar_pixel(x: int, y: int) -> dict:
        """Devolve a celula ao estado virgem. O historico permanece."""
        if estado.canvas.celula(x, y) is None:
            # `canvas.apagar` LEVANTA fora dos limites. Sem esta guarda, um
            # dedo escorregado no painel viraria um 500 no meio da LIVE.
            raise HTTPException(
                status_code=404,
                detail=f"Coordenada fora do canvas {estado.canvas.cols}x{estado.canvas.rows}.",
            )

        estado.canvas.apagar(x, y)
        await estado.db.apagar_pixel(x, y)

        estado.hub.publicar({"type": "pixel_cleared", "x": x, "y": y})
        estado.publicar_estado()
        return {"ok": True, "x": x, "y": y}

    @router.delete("/canvas")
    async def limpar_canvas() -> dict:
        """Esvazia o quadro inteiro e mata as animacoes na tela.

        O botao LIMPAR do painel. E a operacao mais destrutiva do jogo — nao
        tem desfazer, o desenho da comunidade some — e por isso ela faz as
        duas metades numa chamada so:

        1. **O jogo**: memoria e banco. Limpar so a memoria faria o desenho
           voltar inteiro no proximo reinicio do servidor.
        2. **A tela**: o aviso `grid_cleared`. As faiscas e as ondas de uma
           pintura vivem ate um segundo DEPOIS da pintura; sem este aviso
           elas continuariam estourando num quadro que ja nao tem aquele
           pixel, e o streamer veria explosao saindo do nada.

        O RANKING nao e tocado. Limpar o quadro e apagar o desenho; apagar o
        placar seria apagar a participacao de quem mandou rosa a LIVE inteira,
        e ninguem pediu isso.

        `DELETE` e nao `POST`: a rota apaga, e o metodo diz isso antes de o
        corpo ser lido.
        """
        quantas = estado.canvas.preenchidas()
        estado.canvas.limpar()
        await estado.db.limpar_canvas()

        # O feed tambem sai. Ele lista coordenadas que acabaram de deixar de
        # existir: manter "joao pintou H5" numa tela onde H5 esta em branco
        # faz o painel parecer quebrado.
        estado.feed.clear()

        estado.hub.publicar({"type": "grid_cleared"})
        estado.publicar_estado()
        logger.info("Quadro limpo pelo painel: %d celulas apagadas", quantas)

        return {"ok": True, "cleared": quantas}

    @router.post("/evento")
    async def forcar_evento(pedido: PedidoEvento) -> dict:
        """Dispara um evento da LIVE (ARCO-IRIS, TURBO) na hora.

        O agendador chega na Task 11; ate la o painel recebe 503 e sabe que
        o botao ainda nao tem para onde ir.
        """
        if estado.scheduler is None:
            raise HTTPException(
                status_code=503, detail="Nenhum agendador de eventos ativo."
            )

        resultado = estado.scheduler.forcar(pedido.chave)
        if resultado is None:
            raise HTTPException(
                status_code=404, detail=f"Evento desconhecido: {pedido.chave}"
            )
        return resultado

    app.include_router(router)
