"""A voz do jogo: presente, chegada e evento viram fala no ar.

O pedido que criou este modulo: "quando alguem doar algo, gere um audio igual
ao tts.py, da play no audio e logo em seguida apaga". A chegada de alguem na
LIVE e os eventos (HORA DO PIXEL, CAOS...) ganharam o mesmo tratamento
depois: mesma fila, mesmo ciclo gerar-tocar-apagar — o que muda e a lista de
onde a frase e sorteada.

O Narrador e uma thread com fila, pelo mesmo motivo da thread do TikTok:
gerar a voz e conversar com o servico de sintese leva segundos, e o loop de
eventos do jogo nao pode esperar por isso. Quem presenteia ganha o credito e
o aviso no telao NA HORA; a fala entra na fila e sai quando der.

As frases sao SORTEADAS de `game/falas.py` — a lista inteira mora la, fora
deste modulo, porque conteudo e codigo envelhecem em ritmos diferentes:
trocar o texto da live nao deveria ser um commit no motor da voz.

A VOZ tambem varia: `tts.vozes` e a lista de vozes por onde as falas rodiziam
(vazia = sempre a `tts.voz` de sempre). Uma LIVE inteira numa voz so soa como
um robo lendo avisos; o rodizio faz cada fala soar como alguem diferente
chamando na tela.

Falha aqui nunca derruba o jogo: sem internet, sem a biblioteca, sem placa de
som — o que acontece e um log, e o jogo segue em frente. A reproducao usa o
MCI do proprio Windows (via ctypes, biblioteca padrao): nao ha binario
externo nem pacote de audio para instalar. O arquivo e gerado num arquivo
temporario e apagado assim que termina de tocar, como pedido.
"""

from __future__ import annotations

import itertools
import logging
import os
import queue
import random
import tempfile
import threading
import time
from typing import Callable

from game.falas import ABERTURA_DE_EVENTO, BOAS_VINDAS, FALAS, FIM_DE_EVENTO

logger = logging.getLogger(__name__)

VOZ_PADRAO = "pt-BR-FranciscaNeural"

# As vozes pt-BR que a edge-tts oferece HOJE (conferidas por `list_voices`):
# so estas tres — as mais antigas (Brenda, Donato, Giovanna...) sairam do
# servico. Com mais de uma em `tts.vozes`, as falas saem em rodizio; com a
# lista vazia, tudo sai na `tts.voz` de sempre:
#   "pt-BR-FranciscaNeural" (feminina), "pt-BR-AntonioNeural" (masculina),
#   "pt-BR-ThalitaMultilingualNeural" (feminina, multilingue).
RATE_PADRAO = "+8%"
PITCH_PADRAO = "+3Hz"

# O `{quantidade}` vira "5x " (com espaco) quando ha mais de um, e vazio
# quando e um so: "1x Perfume" nao existe na lingua falada — e "mandou
# Perfume" e como uma pessoa diria.
#
# A fala padrao e a primeira da lista de proposito: se uma frase do config
# vier quebrada (um `{placeholder}` que nao existe), o plano B e uma frase
# de verdade, e nao uma segunda copia que pode envelhecer.
FALA_PADRAO = FALAS[0]

# Mesmo plano B para a chegada e para os eventos, com a mesma ancora: a
# primeira frase de verdade da lista.
BOAS_VINDAS_PADRAO = BOAS_VINDAS[0]
ABERTURA_PADRAO = ABERTURA_DE_EVENTO[0]
FIM_PADRAO = FIM_DE_EVENTO[0]

# O teto da fila. Numa chuva de rosas, falas atrasadas viram ruido: e melhor
# calar o presente antigo do que narrar o que ja passou.
FILA_MAXIMA = 20

_ALIASES = itertools.count(1)
_WINMM = None


def _frases_do_config(valor, padrao: tuple[str, ...]) -> list[str]:
    """A lista de frases do config, limpa; vazia ou ausente usa a do jogo.

    Lista vazia e "usa as frases do jogo" de proposito: um `[]` no config
    nao pode deixar a live muda — e o mesmo contrato de `tts.falas`.
    """
    if isinstance(valor, list):
        limpas = [frase.strip() for frase in map(str, valor) if frase.strip()]
        if limpas:
            return limpas
    return list(padrao)


def _vozes_do_config(valor, padrao: str) -> list[str]:
    """A lista de vozes do config, limpa; vazia ou ausente usa a voz de sempre."""
    if isinstance(valor, list):
        limpas = [str(voz).strip() for voz in valor if str(voz).strip()]
        if limpas:
            return limpas
    return [padrao]


def _winmm():
    """O winmm.dll, carregado na primeira fala (nem todo mundo tem Windows)."""
    global _WINMM
    if _WINMM is None:
        import ctypes

        _WINMM = ctypes.WinDLL("winmm")
    return _WINMM


def _motivo_do_erro(codigo: int) -> str:
    import ctypes

    buffer = ctypes.create_unicode_buffer(256)
    _winmm().mciGetErrorStringW(codigo, buffer, 256)
    return buffer.value or f"codigo {codigo}"


def _enviar(comando: str, tamanho_resposta: int = 0) -> str:
    """Manda um comando de texto ao MCI e devolve a resposta (se pedida).

    O MCI e a API de midia mais antiga do Windows e continua a mais direta
    que toca mp3 sem instalar nada: tudo — abrir, tocar, consultar — e uma
    string de comando com resposta em texto.
    """
    import ctypes

    buffer = (
        ctypes.create_unicode_buffer(tamanho_resposta) if tamanho_resposta else None
    )
    erro = _winmm().mciSendStringW(comando, buffer, tamanho_resposta, None)
    if erro:
        raise OSError(f"MCI: {_motivo_do_erro(erro)} (comando: {comando})")
    return buffer.value if buffer is not None else ""


class Narrador:
    """Fila de falas: gera o audio, toca e apaga, uma por vez.

    `gerar` e `tocar` sao injetaveis para o teste rodar sem internet e sem
    placa de som — o motor de verdade e o edge-tts (voz do tts.py) e o MCI.
    """

    def __init__(
        self,
        config: dict | None = None,
        gerar: Callable[[str], str] | None = None,
        tocar: Callable[[str], None] | None = None,
    ):
        cfg = (config or {}).get("tts") or {}
        self.ativo = bool(cfg.get("active", True))
        self.voz = str(cfg.get("voz") or VOZ_PADRAO)
        self.rate = str(cfg.get("rate") or RATE_PADRAO)
        self.pitch = str(cfg.get("pitch") or PITCH_PADRAO)
        self.min_pixels = max(0, int(cfg.get("min_pixels") or 0))

        # O rodizio de vozes (`tts.vozes`): com mais de uma, cada fala sai
        # numa voz — a LIVE para de soar como um robo so. A ordem e fixa (e
        # nao sorteada): da para prever, testar e ouvir a fila.
        self.vozes = _vozes_do_config(cfg.get("vozes"), self.voz)
        self._rodizio = itertools.cycle(self.vozes)

        # As frases do jogo vivem em `game/falas.py`; as chaves equivalentes
        # do config (`tts.falas`, `tts.boas_vindas`, `tts.eventos`,
        # `tts.eventos_fim`) substituem as listas inteiras para quem quiser
        # improvisar sem mexer no codigo.
        self.falas = _frases_do_config(cfg.get("falas"), FALAS)
        self.boas_vindas = _frases_do_config(cfg.get("boas_vindas"), BOAS_VINDAS)
        self.eventos = _frases_do_config(cfg.get("eventos"), ABERTURA_DE_EVENTO)
        self.eventos_fim = _frases_do_config(cfg.get("eventos_fim"), FIM_DE_EVENTO)

        self._gerar = gerar or self._gerar_edge
        self._tocar = tocar or self._tocar_mci
        self._fila: queue.Queue[str | None] = queue.Queue(maxsize=FILA_MAXIMA)
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def ligar(self) -> None:
        """Sobe a thread da voz. Idempotente, como o `start` do adapter."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._trabalhar, name="narrador", daemon=True
        )
        self._thread.start()

    def parar(self) -> None:
        """Encerra a thread. Uma fala no meio e cortada na hora."""
        self._parar.set()
        try:
            self._fila.put_nowait(None)  # acorda a thread, se ela estiver esperando
        except queue.Full:
            pass

    def pendentes(self) -> int:
        """Quantas falas esperam na fila."""
        return self._fila.qsize()

    # ------------------------------------------------------------------
    # A fala
    # ------------------------------------------------------------------

    def _sorteada(
        self, lista: list[str], padrao: str, valores: dict[str, str], o_que: str
    ) -> str:
        """Uma frase da lista, com os valores preenchidos.

        O sorteio e o que impede a voz de virar disco riscado: com dezenas
        de frases, a mesma fala demora a se repetir e a live soa viva.

        E as frases sao editaveis por quem quiser: um `{placeholder}`
        invalido em uma delas nao pode deixar a live muda — vira um aviso no
        log e a frase padrao entra no lugar (ver `FALA_PADRAO`).
        """
        modelo = random.choice(lista)
        try:
            return modelo.format(**valores)
        except (KeyError, IndexError, ValueError):
            logger.warning("%s com placeholder invalido: %r", o_que, modelo)
            return padrao.format(**valores)

    def texto_do_presente(self, nome: str, quantidade: int, presente: str) -> str:
        """A fala do presente, sorteada entre as frases do jogo.

        O arroba nao se pronuncia ("@ana" vira "ana").
        """
        return self._sorteada(
            self.falas,
            FALA_PADRAO,
            {
                "nome": (nome or "").strip().lstrip("@"),
                "quantidade": f"{int(quantidade)}x " if int(quantidade) > 1 else "",
                "presente": presente or "presente",
            },
            "Fala",
        )

    def texto_de_entrada(self, nome: str) -> str:
        """A fala de quem acabou de chegar, sorteada entre as do jogo.

        Sem `{quantidade}` nem `{presente}`: a chegada nao tem premio, tem
        so um nome — e e por ele que a voz chama.
        """
        return self._sorteada(
            self.boas_vindas,
            BOAS_VINDAS_PADRAO,
            {"nome": (nome or "").strip().lstrip("@")},
            "Boas-vindas",
        )

    def texto_de_evento(self, nome: str) -> str:
        """O anuncio de um evento que comecou.

        Atencao: aqui o `{nome}` das frases e o nome do EVENTO ("PIXEL
        TURBO"), nao o de uma pessoa.
        """
        return self._sorteada(
            self.eventos,
            ABERTURA_PADRAO,
            {"nome": (nome or "").strip() or "evento"},
            "Anuncio de evento",
        )

    def texto_do_fim_de_evento(self, nome: str) -> str:
        """O aviso de que o evento acabou. Mesmo `{nome}` de evento."""
        return self._sorteada(
            self.eventos_fim,
            FIM_PADRAO,
            {"nome": (nome or "").strip() or "evento"},
            "Fim de evento",
        )

    def anunciar_presente(
        self, nome: str, quantidade: int, presente: str, pixels: int
    ) -> str | None:
        """Enfileira a fala de um presente. Devolve o texto, ou None se calou.

        Nunca bloqueia: quem chama e o loop de eventos da live, e um presente
        nao pode esperar a voz do anterior para ser creditado.
        """
        if not self.ativo or pixels < self.min_pixels:
            return None

        return self._enfileirar(
            self.texto_do_presente(nome, quantidade, presente), nome
        )

    def anunciar_entrada(self, nome: str) -> str | None:
        """Enfileira o oi de quem chegou. Devolve o texto, ou None se calou.

        Mesma fila e mesmo ciclo do presente — a diferenca e so a lista de
        onde a frase sai. Sem `min_pixels`: chegar nao paga pixel, e o oi e
        justamente para quem ainda nao fez nada.
        """
        if not self.ativo:
            return None

        return self._enfileirar(self.texto_de_entrada(nome), nome)

    def anunciar_evento(self, nome: str) -> str | None:
        """Enfileira o anuncio de um evento que comecou.

        A voz e o segundo canal de aviso: o banner esta na tela, mas quem
        esta de costas para ela so fica sabendo pelo alto-falante. Mesma
        fila e mesmas regras das outras falas.
        """
        if not self.ativo:
            return None

        return self._enfileirar(
            self.texto_de_evento(nome), f"o evento {nome or '?'}"
        )

    def anunciar_fim_de_evento(self, nome: str) -> str | None:
        """Enfileira o aviso de que o evento acabou."""
        if not self.ativo:
            return None

        return self._enfileirar(
            self.texto_do_fim_de_evento(nome), f"o fim do evento {nome or '?'}"
        )

    def _enfileirar(self, texto: str, nome: str) -> str:
        """Po na fila sem bloquear. Cheia, a fala mais antiga sai.

        Num pico, narrar o que esta acontecendo agora vale mais do que o
        atrasado — e o aviso no log diz quem ficou sem voz.
        """
        try:
            self._fila.put_nowait(texto)
        except queue.Full:
            try:
                self._fila.get_nowait()
                self._fila.put_nowait(texto)
            except (queue.Empty, queue.Full):
                logger.warning("Fila de falas cheia; %s ficou sem voz", nome)
        return texto

    # ------------------------------------------------------------------
    # O trabalho da thread
    # ------------------------------------------------------------------

    def _trabalhar(self) -> None:
        while not self._parar.is_set():
            try:
                texto = self._fila.get(timeout=0.5)
            except queue.Empty:
                continue
            if texto is None:
                return

            caminho: str | None = None
            try:
                caminho = self._gerar(texto)
                self._tocar(caminho)
            except Exception as erro:
                # Audio e enfeite: um tropeco aqui (internet, codec, placa de
                # som) nao pode nem derrubar a thread nem parar o jogo.
                logger.warning("Nao consegui falar %r: %s", texto, erro)
            finally:
                if caminho:
                    self._apagar(caminho)

    # ------------------------------------------------------------------
    # Motores de verdade: edge-tts gera, MCI toca
    # ------------------------------------------------------------------

    def _proxima_voz(self) -> str:
        """A voz da proxima fala: o proximo nome do rodizio."""
        return next(self._rodizio)

    def _gerar_edge(self, texto: str) -> str:
        """Gera o mp3 da fala e devolve o caminho. Mesma voz do tts.py."""
        import asyncio

        import edge_tts  # import tardio: sem a lib o jogo so fica mudo

        descritor, caminho = tempfile.mkstemp(prefix="pixelworld_tts_", suffix=".mp3")
        os.close(descritor)

        async def salvar(voz_nome: str) -> None:
            voz = edge_tts.Communicate(
                text=texto, voice=voz_nome, rate=self.rate, pitch=self.pitch
            )
            await voz.save(caminho)

        escolhida = self._proxima_voz()
        try:
            asyncio.run(salvar(escolhida))
        except Exception:
            # Um nome de voz errado no config (ou uma voz aposentada pelo
            # servico, como aconteceu com as pt-BR antigas) nao pode deixar a
            # LIVE muda: a fala sai na voz padrao, que e a unica que a gente
            # sabe que existe.
            if escolhida == VOZ_PADRAO:
                raise
            logger.warning("A voz %s falhou; falando com %s", escolhida, VOZ_PADRAO)
            asyncio.run(salvar(VOZ_PADRAO))
        return caminho

    def _tocar_mci(self, caminho: str) -> None:
        """Toca o mp3 do inicio ao fim; so volta quando acabar.

        `play` sem `wait` + `status mode` em laco, em vez do `wait`
        bloqueante: assim uma fala no meio pode ser cortada quando o jogo
        esta encerrando, em vez de segurar o desligamento.
        """
        alias = f"pwtts{next(_ALIASES)}"
        _enviar(f'open "{caminho}" type mpegvideo alias {alias}')
        try:
            _enviar(f"play {alias}")
            limite = time.monotonic() + self._duracao(alias) + 2.0
            while time.monotonic() < limite:
                if self._parar.is_set():
                    _enviar(f"stop {alias}")
                    return
                if _enviar(f"status {alias} mode", 64) == "stopped":
                    return
                time.sleep(0.05)
            logger.warning("A fala passou do tempo do audio: %s", caminho)
        finally:
            _enviar(f"close {alias}")

    @staticmethod
    def _duracao(alias: str) -> float:
        """Duracao do audio em segundos; 10s de teto se o MCI nao souber."""
        try:
            milissegundos = int(_enviar(f"status {alias} length", 64) or 0)
        except (OSError, ValueError):
            milissegundos = 0
        return milissegundos / 1000.0 if milissegundos > 0 else 10.0

    @staticmethod
    def _apagar(caminho: str) -> None:
        """O pedido e literal: tocou, apagou.

        O Windows pode segurar o arquivo por um instante depois do close
        (antivirus, indexador); algumas tentativas e so entao um aviso.
        """
        for _ in range(10):
            try:
                os.remove(caminho)
                return
            except FileNotFoundError:
                return
            except OSError:
                time.sleep(0.05)
        logger.warning("Nao consegui apagar o audio: %s", caminho)
