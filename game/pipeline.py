"""De um evento do TikTok ate uma pintura na tela.

O pipeline e a costura entre a camada de conexao e as regras do jogo. Ele
recebe um `LiveEvent` ja traduzido pelo adapter e decide o que aquilo
significa: presente credita, comentario com coordenada pinta, conversa comum
nao faz nada.

Ele NAO implementa regra nenhuma. Quem sabe o preco, quem sabe o saldo e quem
sabe se a coordenada existe sao `ServicoPintura` e `parse_pedido`. Aqui so se
decide a ORDEM das coisas e se montam as mensagens que vao para a tela.

Tres decisoes que valem explicacao:

- **Evento sem autor nao faz nada.** A biblioteca do TikTok omite o campo
  `user` quando alguem curte demais. Deixar passar criaria um usuario fantasma
  no ranking. A checagem e a primeira coisa, antes de qualquer efeito.
- **Recusa e sempre visivel.** Quem tentou pintar e nao conseguiu recebe um
  aviso na tela. Falha silenciosa aqui e a pior falha possivel do jogo: a
  pessoa manda rosa, escreve a coordenada, nada acontece, e ela vai embora.
- **Conversa comum nao gera aviso.** So quem *tentou* pintar recebe resposta.
  Um feed cheio de "nao entendi" ensina a audiencia a ignorar o jogo.
"""

import logging
from datetime import datetime
from typing import Callable

from backend.database import Database
from core.events import EventType, LiveEvent
from game.canvas import CanvasModel
from game.colors import (
    COR_PADRAO,
    Cor,
    cor_automatica,
    cores_do_config,
    lista_da_paleta,
    separar_cor,
)
from game.coordinates import Pedido, parse_pedido, parece_pintura
from game.inventory import Inventario
from game.narrador import Narrador
from game.painting import MOTIVO_SALDO, ServicoPintura, motivo_legivel
from game.ranking import Ranking
from game.rewards import AcumuladorCurtidas, pixels_do_evento

logger = logging.getLogger(__name__)

MAX_POR_EVENTO_PADRAO = 400

# O teto de uma lista num comentario so. Existe pela TELA e pelo banco, nao
# pelo dinheiro: cada celula pinta e ainda escreve quatro linhas no banco, e um
# comentario colado com as 2550 celulas do quadro deixaria a LIVE travada
# atendendo uma pessoa. Cem e ~4% do quadro — o tamanho de um desenho, nao de
# uma tomada de terreno.
MAX_POR_COMENTARIO_PADRAO = 100

TEXTO_NAO_ENTENDI = "NAO ENTENDI — ESCREVA LETRA + NUMERO, EX: H5"

COMANDO_PONTOS = "/pontos"


def _eh_comando_pontos(texto: str) -> bool:
    """O comentario INTEIRO e o comando `/pontos`, ou nada.

    Comentario que so COMECA com o comando nao vale: "/pontos pra mim" e uma
    frase no meio da conversa, e responder seria o jogo falando por cima da
    pessoa. A pontuacao do fim cai junto ("/pontos!", "/pontos.") — ninguem
    digita comando caprichado.

    A comparacao e feita aqui e nao no parser de coordenadas porque `/pontos`
    nao pede nada do quadro: ele so pergunta um numero que o inventario ja
    sabe. Mandar isso para o parser de pintura faria o comando depender do
    tamanho do canvas, e um comando de leitura nao tem nada a ver com a grade.
    """
    limpo = (texto or "").strip().lower().rstrip("!?.,")
    return limpo == COMANDO_PONTOS


def _pecas_ilegiveis(invalidas: list[str]) -> str:
    """As pecas que nao deram para ler, do jeito que a pessoa escreveu.

    Tres bastam para ela reconhecer o proprio erro, e o resto vira contagem —
    um aviso do tamanho do comentario nao caberia na tela nem seria lido.
    """
    mostradas = [p if len(p) <= 14 else p[:11] + "..." for p in invalidas[:3]]
    texto = ", ".join(mostradas)
    if len(invalidas) > 3:
        texto += f" (+{len(invalidas) - 3})"
    return texto


def _timestamp(painted_at: str | None) -> int:
    """ISO 8601 -> segundos unix, que e o que o navegador espera."""
    if not painted_at:
        return int(datetime.now().timestamp())
    try:
        return int(datetime.fromisoformat(painted_at).timestamp())
    except ValueError:
        return int(datetime.now().timestamp())


class Pipeline:
    """Traduz eventos da LIVE em pinturas, creditos e mensagens de tela."""

    def __init__(
        self,
        cfg: dict,
        servico: ServicoPintura,
        inventario: Inventario,
        db: Database,
        ranking: Ranking | None = None,
        multiplicador_fn: Callable[[], float] | None = None,
        curtidas: AcumuladorCurtidas | None = None,
        narrador: Narrador | None = None,
    ):
        self.cfg = cfg
        self.servico = servico
        self.inventario = inventario
        self.db = db
        self.ranking = ranking
        self.narrador = narrador

        self.canvas: CanvasModel = servico.canvas
        self.cols = self.canvas.cols
        self.rows = self.canvas.rows

        # O multiplicador vem de fora (o agendador de eventos, na Task 11) para
        # que o pipeline nao dependa de um modulo que ainda nao existe.
        self._multiplicador = multiplicador_fn or (lambda: 1.0)
        self._curtidas = curtidas or AcumuladorCurtidas.do_config(cfg)

        limites = cfg.get("limits") or {}
        self.max_por_evento = max(
            1, int(limites.get("max_pixels_por_evento") or MAX_POR_EVENTO_PADRAO)
        )
        self.max_por_comentario = max(
            1,
            int(
                limites.get("max_pixels_por_comentario") or MAX_POR_COMENTARIO_PADRAO
            ),
        )

        self.paleta, self.especiais = cores_do_config(cfg)
        self.lista_paleta = lista_da_paleta(self.paleta)

        # Quem ja foi saudado nesta execucao. Ver `_boas_vindas`.
        self._vindos: set[str] = set()

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------

    async def processar(self, evento: LiveEvent) -> list[dict]:
        """Processa um evento e devolve as mensagens de WebSocket a emitir."""
        handle = evento.handle()
        if not handle:
            # Sem autor nao ha a quem creditar nem em nome de quem pintar.
            return []

        try:
            return await self._processar(evento, handle)
        except Exception:
            # Um evento estranho nao pode derrubar a LIVE. A biblioteca do
            # TikTok reflete o JSON da plataforma, e o formato muda sem aviso.
            logger.exception("Falha ao processar evento %s de %s", evento.type, handle)
            return []

    async def _processar(self, evento: LiveEvent, handle: str) -> list[dict]:
        mensagens: list[dict] = []

        pixels = pixels_do_evento(evento, self.cfg, self._curtidas)
        if pixels > 0:
            # O multiplicador e dos EVENTOS ao vivo (ARCO-IRIS, PIXEL TURBO).
            # Ele vale para o que a audiencia manda durante a janela, nunca
            # para o preco de pintar.
            pixels = int(pixels * self._multiplicador())
            pixels = min(pixels, self.max_por_evento)
            if pixels > 0:
                mensagens += await self._creditar(evento, handle, pixels)

        if evento.type == EventType.COMMENT:
            mensagens += await self._comentar(evento, handle)

        if evento.type == EventType.JOIN:
            # Entrar nao paga pixel (`pixels_do_evento` ja devolveu zero). O
            # que a chegada vale e o oi pelo nome — a unica resposta que o
            # jogo da a quem ainda nao fez nada.
            mensagens += self._boas_vindas(evento, handle)

        return mensagens

    # ------------------------------------------------------------------
    # Credito
    # ------------------------------------------------------------------

    async def _creditar(self, evento: LiveEvent, handle: str, pixels: int) -> list[dict]:
        self.inventario.adicionar(handle, pixels)

        if self.ranking is not None:
            self.ranking.registrar(handle, nome=evento.actor())

        if evento.type == EventType.GIFT:
            nome = evento.gift_name or "desconhecido"
            quantidade = int(evento.quantity or 1)

            # O upsert vem ANTES: `registrar_presente` incrementa uma coluna da
            # linha que ja precisa existir, e um UPDATE que nao casa nada
            # perderia o presente em silencio.
            await self.db.upsert_usuario(handle, display_name=evento.actor())
            await self.db.registrar_presente(
                handle, nome, evento.gift_id, quantidade, pixels
            )

            # O console e o unico canal de quem esta transmitindo: a tela vive
            # numa cena do OBS e o painel em outra janela, nenhum dos dois na
            # frente de quem esta ao vivo. Sem esta linha, uma rosa chega,
            # credita e nao aparece em lugar nenhum.
            logger.info(
                "Presente: %s mandou %dx %s -> %d pixel(s) (saldo %d)",
                evento.actor(),
                quantidade,
                nome,
                pixels,
                self.inventario.saldo(handle),
            )

            if self.narrador is not None:
                # A voz e assincrona de proposito: o credito e o aviso no
                # telao saem agora; a fala entra na fila do Narrador e sai
                # quando der, sem segurar o evento.
                self.narrador.anunciar_presente(
                    evento.actor(), quantidade, nome, pixels
                )

        unidade = "PIXEL" if pixels == 1 else "PIXELS"
        return [
            {
                "type": "toast",
                "kind": "reward",
                "text": self._texto_do_credito(evento, pixels, unidade),
            },
            {
                "type": "inventario",
                "handle": handle,
                "saldo": self.inventario.saldo(handle),
            },
            self._atividade(evento, handle, pixels),
        ]

    def _texto_do_credito(self, evento: LiveEvent, pixels: int, unidade: str) -> str:
        """O aviso de quem ganhou pixel, com a CARA do que pagou por ele.

        O texto era um so para todo credito, com um 🌹 fixo — e por isso a
        curtida que virava pixel chegava na tela com cara de rosa: quem curtiu
        nao se reconhecia no aviso, e quem so assistia lia tudo como presente.
        Cada tipo diz o proprio verbo, e o emoji e o que separa um do outro
        num relance: ❤️ e curtida, ➕ e seguidor, 🔁 e compartilhamento.
        """
        nome = evento.actor()

        if evento.type == EventType.GIFT:
            quantidade = int(evento.quantity or 1)
            presente = evento.gift_name or "presente"
            return f"🌹 {nome} mandou {quantidade}x {presente} e ganhou {pixels} {unidade}!"

        if evento.type == EventType.LIKE:
            return f"❤️ {nome} curtiu e ganhou {pixels} {unidade}!"

        if evento.type == EventType.FOLLOW:
            return f"➕ {nome} seguiu e ganhou {pixels} {unidade}!"

        return f"🔁 {nome} compartilhou e ganhou {pixels} {unidade}!"

    # ------------------------------------------------------------------
    # Comentario
    # ------------------------------------------------------------------

    async def _comentar(self, evento: LiveEvent, handle: str) -> list[dict]:
        texto = evento.text or ""

        # A cor pode ABRIR o comentario, sozinha ("/cor roxo") ou colada na
        # coordenada ("/vermelho W1,X1,..."). Quem esta pintando um desenho
        # inteiro de uma cor escreve a cor primeiro; sem esta leitura a lista
        # sairia na cor ANTIGA e a cor pedida viraria "peca ilegivel" — foi
        # exatamente o que aconteceu, com "NAO ENTENDI: vermelho" na tela.
        #
        # Cor sem coordenada nenhuma depois e so a troca; com coordenada, a
        # mensagem inteira e UMA jogada. Cor seguida de conversa ("vermelho e
        # minha cor favorita") nao e comando nenhum e cai no fluxo normal,
        # calada, como qualquer conversa.
        achado = separar_cor(texto, self.paleta, self.especiais)
        if achado is not None:
            cor, resto = achado
            if not resto:
                return await self._trocar_cor(evento, handle, cor)

            pedido = parse_pedido(resto, self.cols, self.rows)
            if pedido.coordenadas:
                trocou = await self._trocar_cor(evento, handle, cor, pintando=True)
                return trocou + await self._pintar(evento, handle, pedido)

        # Sem cor no comeco, o que resta e a coordenada: pintar e o que a
        # pessoa veio fazer. Pode ser UMA celula ou a lista inteira — quem
        # decide e o parser, e o pipeline nao precisa saber a diferenca.
        #
        # O pedido entra desde que UMA celula tenha dado para ler. Derrubar a
        # lista toda por causa de uma peca ruim custa o desenho inteiro: a
        # receita colada em tres linhas num campo de uma linha so chega com as
        # celulas da quebra grudadas, e ninguem merece perder 72 pixels por
        # causa de duas pecas coladas.
        pedido = parse_pedido(texto, self.cols, self.rows)
        if pedido.coordenadas:
            return await self._pintar(evento, handle, pedido)

        # O `/pontos` vem ANTES do "nao entendi" porque comeca com barra — o
        # mesmo sinal que faz `parece_pintura` achar que alguem tentou pintar.
        # Sem esta linha, quem pedisse o saldo receberia "NAO ENTENDI: ESCREVA
        # LETRA + NUMERO", que e a resposta errada para uma pergunta certa.
        if _eh_comando_pontos(texto):
            return [self._responder_pontos(handle)]

        if parece_pintura(texto):
            return [self._erro(TEXTO_NAO_ENTENDI)]

        return []

    async def _pintar(
        self, evento: LiveEvent, handle: str, pedido: Pedido
    ) -> list[dict]:
        """Pinta a lista inteira e conta o que aconteceu.

        A lista e UMA jogada. O ranking sobe uma vez, no fim, com o total — em
        vez de uma passada por celula, que faria o `pixels=1` da versao antiga
        aparecer dez vezes no mesmo lugar da tabela.

        `pedidas` conta so as celulas legiveis. As pecas que nao deram para ler
        nao entram nessa conta porque nao sao pintura que faltou: elas tem
        aviso proprio, com o texto delas, logo abaixo.
        """
        cor = self._cor_de(handle)

        pedidas = len(pedido.coordenadas)
        coordenadas = pedido.coordenadas[: self.max_por_comentario]

        resultados = await self.servico.pintar_lote(
            handle, coordenadas, cor.hex, cor.efeito
        )

        autor = f"@{handle}"
        mensagens: list[dict] = []
        pintados = 0
        xp = 0
        sobrescritos = 0
        ultima = None
        motivo_parada = None

        for resultado in resultados:
            if not resultado.ok:
                # Guarda o PRIMEIRO motivo: e ele que explica por que a lista
                # parou. O resto e consequencia.
                motivo_parada = motivo_parada or resultado.motivo
                continue

            celula = resultado.celula
            pintados += 1
            xp += resultado.xp
            sobrescritos += 1 if resultado.sobrescrita else 0
            ultima = celula

            mensagens.append(
                {
                    "type": "pixel_painted",
                    "x": celula.x,
                    "y": celula.y,
                    "coordinate": celula.rotulo,
                    "color": celula.color,
                    "user": autor,
                    "effect": celula.effect,
                    "cost": resultado.custo,
                    "ts": _timestamp(celula.painted_at),
                }
            )
            mensagens.append(
                {
                    "type": "feed",
                    "user": autor,
                    "coordinate": celula.rotulo,
                    "color": celula.color,
                }
            )

        if pintados and self.ranking is not None:
            self.ranking.registrar(
                handle,
                nome=evento.actor(),
                cor=cor.hex,
                efeito=cor.efeito,
                pixels=pintados,
                sobrescritos=sobrescritos,
                xp=xp,
                cor_pintada=ultima.color,
            )

        # O aviso e sempre sobre o que FALTOU, e sempre com o numero. Quem
        # escreveu dez coordenadas e viu cinco quadrados precisa saber que
        # foram cinco, e nao que o jogo quebrou ou que ela escreveu errado.
        if pintados < pedidas:
            if not pintados:
                # Nada entrou. "0 DE 10" so repetiria, com menos clareza, o que
                # a propria recusa ja diz.
                texto = self._aviso_de_parada(motivo_parada or MOTIVO_SALDO, autor)
            elif motivo_parada is None:
                # Entrou tudo que coube no teto: o resto nao foi recusado por
                # regra nenhuma, foi adiado.
                texto = (
                    f"SO CABEM {self.max_por_comentario} POR VEZ — "
                    f"{pintados} DE {pedidas} PINTADOS"
                )
            else:
                texto = (
                    f"{self._aviso_de_parada(motivo_parada, autor)} "
                    f"({pintados} DE {pedidas})"
                )
            mensagens.append(self._erro(texto))

        # O aviso das pecas ilegiveis nao fala de pintura de proposito: ele vale
        # igual quando o desenho entrou inteiro e quando o saldo acabou no meio,
        # e prometer "o resto entrou" seria mentira no segundo caso.
        if pedido.invalidas:
            mensagens.append(
                self._erro(f"NAO ENTENDI: {_pecas_ilegiveis(pedido.invalidas)}")
            )

        return mensagens

    async def _trocar_cor(
        self, evento: LiveEvent, handle: str, cor: Cor, pintando: bool = False
    ) -> list[dict]:
        if self.ranking is not None:
            self.ranking.registrar(
                handle, nome=evento.actor(), cor=cor.hex, efeito=cor.efeito
            )

        await self.db.upsert_usuario(
            handle, display_name=evento.actor(), color=cor.hex, effect=cor.efeito
        )

        # O aviso termina com o PROXIMO PASSO, nao com a cor. Trocar a cor nao
        # pinta nada: quem manda so `/cor vermelho` no painel le "agora pinta
        # de VERMELHO", olha a grid intacta e acha que travou. O aviso e o
        # unico retorno que essa pessoa recebe, e o exemplo concreto e o que a
        # ensina a terminar a jogada.
        #
        # Com as coordenadas no MESMO comentario nao falta passo nenhum — a
        # jogada ja terminou, e pedir a coordenada de novo seria pedir o que a
        # pessoa acabou de escrever.
        texto = f"🎨 {evento.actor()} agora pinta de {self._rotulo_da_cor(cor)}!"
        if not pintando:
            texto += " Falta a rosa e a coordenada (ex: H5)"

        return [{"type": "toast", "kind": "cor", "text": texto}]

    # ------------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------------

    def _aviso_de_parada(self, motivo: str, autor: str) -> str:
        """O texto do motivo que parou o pedido.

        O SALDO e o unico que chama a pessoa pelo nome. O toast aparece no
        telao para a live inteira, e "SEM PIXELS" sem nome parece recado de
        ninguem: quem mandou o desenho fica sem saber que a resposta e para
        ela — e o nome e o que transforma o aviso em resposta.
        """
        if motivo != MOTIVO_SALDO:
            return motivo_legivel(motivo)
        return f"SEM PIXELS — {autor}, {self._caminho_gratis()}"

    def _caminho_gratis(self) -> str:
        """Como conseguir pixel sem mandar presente nenhum.

        A curtida tambem rende (`rewards.like.curtidas_por_pixel`), e quem
        chegou ao fim do saldo — ou nunca teve nenhum — precisa ouvir isso do
        jogo, nao adivinhar. Fica numa funcao so porque DOIS avisos usam a
        mesma frase: o de quem nao conseguiu pintar e o do `/pontos` de saldo
        zero. Duas copias divergiriam na primeira vez que o numero mudasse.
        """
        return f"MANDE UMA ROSA 🌹 OU CURTA {self._curtidas.por_pixel}x"

    def _responder_pontos(self, handle: str) -> dict:
        """A resposta do `/pontos`: o saldo de quem perguntou.

        O saldo e o numero que a audiencia pergunta de verdade no chat — e a
        pergunta chega no chat, nao no jogo, entao a resposta sai no telao para
        quem perguntou (e para quem tiver a mesma duvida logo depois).

        Quem tem ZERO ouve o caminho gratis junto: este e o unico momento em
        que essa pessoa olha para o proprio saldo, e "0 PIXELS" sozinho nao
        ensina como sair do zero.
        """
        saldo = self.inventario.saldo(handle)
        unidade = "PIXEL" if saldo == 1 else "PIXELS"
        texto = f"⭐ @{handle} TEM {saldo} {unidade}"
        if saldo <= 0:
            texto += f" — {self._caminho_gratis()}"
        return {"type": "toast", "kind": "info", "text": texto}

    def _atividade(self, evento: LiveEvent, handle: str, pixels: int) -> dict:
        """A linha do cartao "Atividade" do painel: quem ganhou, e como.

        E o log que o streamer le ao vivo — presente, combo de curtidas,
        seguidor, compartilhamento —, e por isso ele vai estruturado, com o
        numero cru de cada tipo: a quantidade do presente, o total de curtidas
        da SALA (`like_total`, o mesmo contador que a LIVE mostra — num combo
        de uma pessoa so ele anda no ritmo dela), e o que aquilo virou em
        pixels. Quem monta a frase e o painel, que e quem sabe que emoji e que
        verbo usar.
        """
        if evento.type == EventType.GIFT:
            kind, amount = "gift", int(evento.quantity or 1)
        elif evento.type == EventType.LIKE:
            kind, amount = "like", int(evento.like_total or evento.like_delta or 0)
        elif evento.type == EventType.FOLLOW:
            kind, amount = "follow", 1
        else:
            kind, amount = "share", 1

        return {
            "type": "credito",
            "kind": kind,
            "user": f"@{handle}",
            "gift": evento.gift_name or "",
            "amount": amount,
            "pixels": pixels,
            "saldo": self.inventario.saldo(handle),
        }

    def _boas_vindas(self, evento: LiveEvent, handle: str) -> list[dict]:
        """O oi de quem ACABOU de chegar, pelo nome.

        Entrar e o unico momento em que a pessoa esta olhando para a tela sem
        estar no meio de outra coisa. Ver o proprio nome no telao segundos
        depois de entrar e o que separa "mais uma LIVE" de "aqui tem alguem do
        outro lado" — e o convite para pintar vai junto, porque quem chegou
        ainda nao sabe o que a tela espera dela.

        Cada handle e saudado UMA vez por execucao: queda de rede faz o
        proprio TikTok reentregar a chegada, e "ENTROU" repetido vira ruido
        no telao — justamente para quem ja estava prestando atencao.
        """
        if handle in self._vindos:
            return []

        self._vindos.add(handle)

        if self.narrador is not None:
            # A voz entra na mesma fila do presente e sai quando der, sem
            # segurar o evento. O dedupe e o mesmo do aviso: quem reentra nao
            # ouve o proprio nome de novo.
            self.narrador.anunciar_entrada(evento.actor())

        return [
            {
                "type": "toast",
                "kind": "info",
                "text": f"👋 {evento.actor()} ENTROU — pinte seu primeiro pixel!",
            }
        ]

    def _cor_de(self, handle: str) -> Cor:
        """A cor (e o efeito) com que esta pessoa pinta agora."""
        if self.ranking is None:
            return Cor(hex=cor_automatica(handle, self.lista_paleta))

        entrada = self.ranking.entrada(handle)
        if entrada is None:
            entrada = self.ranking.registrar(handle)

        return Cor(hex=entrada.cor or COR_PADRAO, efeito=entrada.efeito)

    def _rotulo_da_cor(self, cor: Cor) -> str:
        """O nome que a pessoa reconhece — "ROXO", "FOGO" — nao o hex."""
        if cor.efeito:
            definicao = self.especiais.get(cor.efeito) or {}
            rotulo = definicao.get("rotulo")
            if rotulo:
                return str(rotulo).upper()

        for nome, valor in self.paleta.items():
            if str(valor).upper() == cor.hex.upper():
                return nome.upper()

        return cor.hex.upper()

    @staticmethod
    def _erro(texto: str) -> dict:
        return {"type": "toast", "kind": "error", "text": texto}
