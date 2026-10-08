"""Traducao dos eventos do TikTok para o formato interno.

Nada aqui toca a rede. As funcoes de traducao sao puras de proposito: a
biblioteca `TikTokLive` e engenharia reversa do Webcast interno, nao e API
oficial, e quebra sem aviso. Quando quebrar, o defeito tem que estar
localizavel aqui — num teste que roda em milissegundos — e nao no meio de uma
LIVE ao vivo.

O caso que mais importa e o STREAK. Quando alguem segura o botao e manda 40
rosas, a biblioteca emite um evento por rosa, todos com `streaking=True`, e so
o ULTIMO chega com `repeat_count=40` e `streaking=False`. Sem filtrar os
intermediarios, uma sequencia de 40 rosas vira 200 pixels em vez de 40 — e a
economia do jogo inteiro desanda.
"""

import asyncio
from types import SimpleNamespace

import pytest

from core.event_queue import EventQueue
from core.events import EventType
from game.rewards import AcumuladorCurtidas, pixels_do_evento
from tiktok.adapter import (
    TikTokLiveAdapter,
    _display_name,
    _user_id,
    evento_de_comentario,
    evento_de_like,
    evento_de_presente,
)


def cfg_tiktok(**over) -> dict:
    base = {"tiktok": {"username": "@criador", "reconnect_seconds": 5.0, "reconnect_max_seconds": 60.0}}
    base["tiktok"].update(over)
    return base


def cfg_premios(max_multiplicador: int = 10) -> dict:
    return {
        "rewards": {
            "presente_desconhecido": 1,
            "max_multiplicador": max_multiplicador,
            "gifts": {"Rose": 1, "Galaxy": 60},
            "like": {"curtidas_por_pixel": 20, "max_pixels": 10},
            "follow": {"pixels": 5},
            "share": {"pixels": 3},
        }
    }


def usuario(unique_id="joao", nickname="Joao"):
    return SimpleNamespace(unique_id=unique_id, nickname=nickname)


# --------------------------------------------------------------------------
# Nomes
# --------------------------------------------------------------------------


def test_user_id_le_o_unique_id():
    assert _user_id(usuario()) == "joao"


def test_user_id_cai_para_o_display_id():
    assert _user_id(SimpleNamespace(unique_id=None, display_id="joao2")) == "joao2"


def test_user_id_sem_usuario_e_vazio():
    assert _user_id(None) == ""


def test_display_name_usa_o_nickname():
    assert _display_name(usuario()) == "Joao"


def test_display_name_cai_para_o_nome_do_arroba():
    assert _display_name(SimpleNamespace(unique_id="joao", nickname=None)) == "joao"


def test_display_name_sem_usuario_e_vazio():
    assert _display_name(None) == ""


# --------------------------------------------------------------------------
# Comentarios
# --------------------------------------------------------------------------


def test_comentario_le_o_campo_content():
    evento = evento_de_comentario(SimpleNamespace(user=usuario(), content="H5"))

    assert evento.type == EventType.COMMENT
    assert evento.text == "H5"
    assert evento.username == "joao"
    assert evento.display_name == "Joao"


def test_comentario_aceita_o_alias_antigo_comment():
    """A v3 renomeou para `content`; LIVE antiga ainda manda `comment`."""
    evento = evento_de_comentario(SimpleNamespace(user=usuario(), comment="H5"))

    assert evento.text == "H5"


def test_comentario_sem_texto_vira_string_vazia():
    evento = evento_de_comentario(SimpleNamespace(user=usuario()))

    assert evento.text == ""


def test_comentario_sem_usuario_nao_tem_autor():
    evento = evento_de_comentario(SimpleNamespace(content="H5"))

    assert evento.username == ""
    assert evento.handle() == ""


def test_comentario_guarda_o_objeto_bruto():
    bruto = SimpleNamespace(user=usuario(), content="H5")

    assert evento_de_comentario(bruto).raw is bruto


# --------------------------------------------------------------------------
# Presentes: o caso do streak
# --------------------------------------------------------------------------


def presente(streaking=True, repeat_count=1, nome="Rose"):
    return SimpleNamespace(
        user=usuario(),
        streaking=streaking,
        repeat_count=repeat_count,
        gift=SimpleNamespace(id=5655, name=nome),
    )


def test_presente_simples_e_traduzido():
    evento = evento_de_presente(presente(streaking=False, repeat_count=1))

    assert evento.type == EventType.GIFT
    assert evento.gift_name == "Rose"
    assert evento.gift_id == "5655"
    assert evento.quantity == 1


def test_evento_intermediario_de_streak_e_ignorado():
    assert evento_de_presente(presente(streaking=True, repeat_count=3)) is None


def test_evento_final_do_streak_chega_com_a_quantidade_consolidada():
    evento = evento_de_presente(presente(streaking=False, repeat_count=40))

    assert evento is not None
    assert evento.quantity == 40


def test_uma_sequencia_de_quarenta_rosas_vira_quarenta_pixels():
    """Review Focus: sem o filtro de streak isto viraria 200 (5 x 40)."""
    sequencia = [presente(streaking=True, repeat_count=n) for n in range(1, 40)]
    sequencia.append(presente(streaking=False, repeat_count=40))

    traduzidos = [evento_de_presente(obj) for obj in sequencia]
    validos = [e for e in traduzidos if e is not None]

    assert len(validos) == 1
    assert validos[0].quantity == 40

    # E do lado da economia: 40 x base 1, limitado pelo teto do streak.
    cedido = pixels_do_evento(validos[0], cfg_premios(max_multiplicador=100))
    limitado = pixels_do_evento(validos[0], cfg_premios(max_multiplicador=10))
    assert cedido == 40
    assert limitado == 10


def test_streak_de_presente_caro_tambem_e_consolidado():
    sequencia = [presente(streaking=True, repeat_count=n, nome="Galaxy") for n in range(1, 20)]
    sequencia.append(presente(streaking=False, repeat_count=20, nome="Galaxy"))

    validos = [e for e in (evento_de_presente(o) for o in sequencia) if e is not None]

    assert len(validos) == 1
    assert validos[0].quantity == 20


def test_presente_sem_streaking_nao_vira_nada():
    """`streaking=False` tambem e o valor de um presente nao-streakable."""
    evento = evento_de_presente(SimpleNamespace(user=usuario(), gift=None))

    assert evento is None


def test_presente_sem_quantidade_conta_como_um():
    evento = evento_de_presente(presente(streaking=False, repeat_count=0))

    assert evento.quantity == 1


def test_presente_sem_nome_fica_vazio():
    evento = evento_de_presente(
        SimpleNamespace(user=usuario(), streaking=False, repeat_count=1, gift=SimpleNamespace(id=1, name=None))
    )

    assert evento.gift_name == ""


# --------------------------------------------------------------------------
# Curtidas
# --------------------------------------------------------------------------


def curtida(count=5, total=100, user=usuario()):
    return SimpleNamespace(user=user, count=count, total=total)


def test_curtida_le_o_incremento_e_o_total():
    evento = evento_de_like(curtida(count=7, total=100))

    assert evento.type == EventType.LIKE
    assert evento.like_delta == 7
    assert evento.like_total == 100


def test_curtida_sem_autor_ainda_e_traduzida():
    """O TikTok para de mandar o autor depois de muitas curtidas seguidas."""
    evento = evento_de_like(curtida(user=None))

    assert evento is not None
    assert evento.username == ""
    assert evento.display_name == ""


def test_total_menor_que_o_anterior_e_descartado():
    """O total e monotono; um valor menor e ruido, nao uma retratacao."""
    evento = evento_de_like(curtida(count=9, total=50), total_anterior=100)

    assert evento.like_delta == 0
    assert evento.like_total == 100


def test_curtida_zerada_e_ignorada():
    assert evento_de_like(curtida(count=0, total=0), total_anterior=0) is None


def test_curtida_negativa_vira_zero():
    evento = evento_de_like(curtida(count=-5, total=100))

    assert evento.like_delta == 0


# --------------------------------------------------------------------------
# Ciclo de vida do adapter
# --------------------------------------------------------------------------


def test_adapter_aceita_username_com_arroba():
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok(username="@criador"))

    assert adapter.username == "criador"


def test_adapter_comeca_desconectado():
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    assert adapter.status.connected is False


def test_stop_sem_start_nao_quebra():
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    adapter.stop()


def test_stop_encerra_com_detalhe_explicito():
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    adapter.stop()

    assert adapter.status.connected is False
    assert adapter.status.detail == "encerrado"


# --------------------------------------------------------------------------
# O bug do event loop
# --------------------------------------------------------------------------


class ClienteFalso:
    """Cliente com a mesma armadilha do TikTokLive."""

    def __init__(self):
        self.desconectado = False
        self.fechado = False

    async def disconnect(self):
        self.desconectado = True

    async def close(self):
        self.fechado = True
        raise RuntimeError("This event loop is already running")


async def test_descarte_usa_disconnect_e_nunca_close():
    """Review Focus: `close()` chama `_clean_tasks()` ->
    `self._asyncio_loop.run_until_complete(...)`, e como esse loop ja esta
    rodando, levanta `RuntimeError: This event loop is already running`.
    `disconnect()` sozinho desliga o websocket sem passar por ali.
    """
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())
    cliente = ClienteFalso()

    await adapter._descartar(cliente)

    assert cliente.desconectado is True
    assert cliente.fechado is False


async def test_descarte_de_cliente_nulo_nao_quebra():
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    await adapter._descartar(None)


async def test_descarte_engole_falha_do_disconnect():
    """Uma tentativa que morreu nao pode derrubar o laco por causa da limpeza."""

    class ClienteRebelde:
        async def disconnect(self):
            raise RuntimeError("socket ja estava morto")

    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    await adapter._descartar(ClienteRebelde())


def test_backoff_cresce_e_tem_teto():
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    valores = [adapter._espera(min(60.0, 5.0 * 2**n), n) for n in range(12)]

    assert all(v <= 60.0 * 1.5 for v in valores)
    assert valores[-1] > valores[0]


def test_backoff_tem_jitter():
    """Sem jitter, todo mundo reconecta no mesmo instante e derruba de novo."""
    adapter = TikTokLiveAdapter(EventQueue(), cfg_tiktok())

    valores = {adapter._espera(30.0, 1) for _ in range(40)}

    assert len(valores) > 1
