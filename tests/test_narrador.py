"""A voz do jogo: presente, chegada e evento — sorteio de frases, fila e o
ciclo gerar-tocar-apagar.

O motor de verdade (edge-tts e MCI) fica fora do teste de proposito —
internet e placa de som nao existem num pytest. `gerar` e `tocar` sao
injetaveis exatamente por isso: aqui se prova a REGRA (o que faz falar, o
que faz calar, o que a frase diz) e o ciclo de vida do arquivo, nao a
sintese. A sintese de verdade e provada a ouvido, no `.verif/smoke_audio.py`.
"""

import time
from pathlib import Path

from game.falas import ABERTURA_DE_EVENTO, BOAS_VINDAS, FALAS, FIM_DE_EVENTO
from game.narrador import (
    ABERTURA_PADRAO,
    BOAS_VINDAS_PADRAO,
    FALA_PADRAO,
    FILA_MAXIMA,
    VOZ_PADRAO,
    Narrador,
)


def test_a_frase_sai_do_sorteio_das_frases_do_jogo():
    narrador = Narrador({})

    texto = narrador.texto_do_presente("ana", 3, "Rose")

    possiveis = [
        frase.format(nome="ana", quantidade="3x ", presente="Rose") for frase in FALAS
    ]
    assert texto in possiveis


def test_um_presente_so_nao_vira_um_x():
    """O `{quantidade}` chega vazio para um presente so: "1x" nao se fala."""
    narrador = Narrador({"tts": {"falas": ["{nome}: {quantidade}{presente}"]}})

    assert narrador.texto_do_presente("ana", 1, "Rose") == "ana: Rose"
    assert narrador.texto_do_presente("ana", 4, "Rose") == "ana: 4x Rose"


def test_o_arroba_nao_se_pronuncia():
    narrador = Narrador({"tts": {"falas": ["{nome}!"]}})

    assert narrador.texto_do_presente("@ana", 1, "Rose") == "ana!"


def test_frase_quebrada_cai_na_padrao():
    """Um `{placeholder}` invalido nao pode deixar a live muda."""
    narrador = Narrador({"tts": {"falas": ["oi {nao_existe}"]}})

    assert narrador.texto_do_presente("ana", 2, "Rose") == FALA_PADRAO.format(
        nome="ana", quantidade="2x ", presente="Rose"
    )


def test_desligado_ou_abaixo_do_minimo_nao_fala():
    desligado = Narrador({"tts": {"active": False}})
    assert desligado.anunciar_presente("ana", 1, "Rose", 1) is None

    exigente = Narrador({"tts": {"min_pixels": 5}})
    assert exigente.anunciar_presente("ana", 1, "Rose", 4) is None
    assert exigente.anunciar_presente("ana", 1, "Rose", 5) is not None


def test_a_fila_nao_estoura_na_chuva_de_rosas():
    """Fila cheia descarta a fala mais antiga, nunca a de agora."""
    narrador = Narrador({"tts": {"falas": ["{nome}"]}})
    for i in range(FILA_MAXIMA + 5):
        narrador.anunciar_presente(f"u{i}", 1, "Rose", 1)

    assert narrador.pendentes() == FILA_MAXIMA
    # As cinco primeiras sairam da fila; a sexta e agora a mais antiga.
    assert narrador._fila.queue[0] == "u5"


# --------------------------------------------------------------------------
# Boas-vindas
# --------------------------------------------------------------------------


def test_a_fala_de_entrada_sai_do_sorteio_das_boas_vindas():
    narrador = Narrador({})

    texto = narrador.texto_de_entrada("ana")

    possiveis = [frase.format(nome="ana") for frase in BOAS_VINDAS]
    assert texto in possiveis


def test_toda_boa_vinda_chama_pelo_nome():
    """O nome e o motivo da fala existir: uma frase sem ele seria generica."""
    for frase in BOAS_VINDAS:
        assert "{nome}" in frase, frase


def test_a_entrada_tambem_tira_o_arroba():
    narrador = Narrador({"tts": {"boas_vindas": ["chegou {nome}"]}})

    assert narrador.texto_de_entrada("@ana") == "chegou ana"


def test_boas_vindas_quebradas_caem_na_padrao():
    """Um `{placeholder}` invalido nao pode deixar a chegada muda."""
    narrador = Narrador({"tts": {"boas_vindas": ["oi {nao_existe}"]}})

    assert narrador.texto_de_entrada("ana") == BOAS_VINDAS_PADRAO.format(nome="ana")


def test_boas_vindas_do_config_substituem_as_do_jogo():
    narrador = Narrador({"tts": {"boas_vindas": ["e aí, {nome}!"]}})

    assert narrador.anunciar_entrada("ana") == "e aí, ana!"


def test_entrada_com_a_voz_desligada_fica_muda():
    narrador = Narrador({"tts": {"active": False}})

    assert narrador.anunciar_entrada("ana") is None


# --------------------------------------------------------------------------
# As vozes
# --------------------------------------------------------------------------


def test_sem_lista_de_vozes_tudo_sai_na_voz_de_sempre():
    """O contrato de quem nao mexeu no config: uma voz so, sempre ela."""
    narrador = Narrador({})
    assert {narrador._proxima_voz() for _ in range(5)} == {VOZ_PADRAO}

    com_voz = Narrador({"tts": {"voz": "pt-BR-AntonioNeural"}})
    assert com_voz._proxima_voz() == "pt-BR-AntonioNeural"


def test_a_lista_de_vozes_limpa_espacos_e_entradas_vazias():
    narrador = Narrador({"tts": {"vozes": [" pt-BR-AntonioNeural ", "", "  "]}})
    assert narrador.vozes == ["pt-BR-AntonioNeural"]


def test_o_rodizio_de_vozes_passa_por_todas_e_volta():
    """Com mais de uma voz, cada fala sai numa — em rodizio, na ordem fixa.

    Ordem fixa e nao sorteio: da para prever, testar, e quem acompanha ouve a
    fila de vozes em vez de um caos.
    """
    narrador = Narrador(
        {"tts": {"vozes": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"]}}
    )

    assert [narrador._proxima_voz() for _ in range(4)] == [
        "pt-BR-FranciscaNeural",
        "pt-BR-AntonioNeural",
        "pt-BR-FranciscaNeural",
        "pt-BR-AntonioNeural",
    ]


# --------------------------------------------------------------------------
# Eventos
# --------------------------------------------------------------------------


def test_o_anuncio_de_evento_sai_do_sorteio_das_aberturas():
    narrador = Narrador({})

    texto = narrador.texto_de_evento("PIXEL TURBO")

    possiveis = [frase.format(nome="PIXEL TURBO") for frase in ABERTURA_DE_EVENTO]
    assert texto in possiveis


def test_o_fim_de_evento_sai_do_sorteio_dos_fins():
    narrador = Narrador({})

    texto = narrador.texto_do_fim_de_evento("CAOS")

    possiveis = [frase.format(nome="CAOS") for frase in FIM_DE_EVENTO]
    assert texto in possiveis


def test_toda_frase_de_evento_tem_o_nome():
    """Aqui o `{nome}` e do EVENTO ("PIXEL TURBO"), nunca o de uma pessoa —
    e uma frase sem ele nao diz de que evento se trata."""
    for frase in ABERTURA_DE_EVENTO + FIM_DE_EVENTO:
        assert "{nome}" in frase, frase


def test_frases_de_evento_do_config_substituem_as_do_jogo():
    narrador = Narrador(
        {"tts": {"eventos": ["começou {nome}!"], "eventos_fim": ["acabou {nome}!"]}}
    )

    assert narrador.anunciar_evento("CAOS") == "começou CAOS!"
    assert narrador.anunciar_fim_de_evento("CAOS") == "acabou CAOS!"


def test_evento_quebrado_cai_na_padrao():
    """Um `{placeholder}` invalido nao pode deixar o evento mudo."""
    narrador = Narrador({"tts": {"eventos": ["oi {nao_existe}"]}})

    assert narrador.texto_de_evento("CAOS") == ABERTURA_PADRAO.format(nome="CAOS")


def test_evento_sem_nome_nao_vira_buraco_na_frase():
    """O nome chega de fora (o `event_start`/`event_end` do agendador); se
    vier vazio, a frase ainda sai inteira, com "evento" no lugar."""
    narrador = Narrador({"tts": {"eventos": ["começou {nome}!"]}})

    assert narrador.texto_de_evento("") == "começou evento!"


def test_evento_com_a_voz_desligada_fica_mudo():
    narrador = Narrador({"tts": {"active": False}})

    assert narrador.anunciar_evento("CAOS") is None
    assert narrador.anunciar_fim_de_evento("CAOS") is None


def test_a_thread_gera_toca_e_apaga(tmp_path):
    """O pedido literal: tocou, apagou. A thread faz o ciclo inteiro."""
    caminho = tmp_path / "fala.mp3"
    tocados: list[tuple[str, str]] = []

    def gerar(texto: str) -> str:
        caminho.write_text(texto, encoding="utf-8")
        return str(caminho)

    def tocar(caminho_do_audio: str) -> None:
        tocados.append(
            (caminho_do_audio, Path(caminho_do_audio).read_text(encoding="utf-8"))
        )

    narrador = Narrador(
        {"tts": {"falas": ["presente de {nome}"]}}, gerar=gerar, tocar=tocar
    )
    narrador.ligar()
    try:
        narrador.anunciar_presente("ana", 1, "Rose", 1)

        limite = time.monotonic() + 5
        while not tocados and time.monotonic() < limite:
            time.sleep(0.01)
        assert tocados == [(str(caminho), "presente de ana")]

        limite = time.monotonic() + 5
        while caminho.exists() and time.monotonic() < limite:
            time.sleep(0.01)
    finally:
        narrador.parar()

    assert not caminho.exists()


def test_a_chegada_faz_o_mesmo_ciclo_do_presente(tmp_path):
    """O pedido e o mesmo da chegada: toca e logo em seguida apaga."""
    caminho = tmp_path / "oi.mp3"
    tocados: list[str] = []

    def gerar(texto: str) -> str:
        caminho.write_text(texto, encoding="utf-8")
        return str(caminho)

    def tocar(caminho_do_audio: str) -> None:
        tocados.append(Path(caminho_do_audio).read_text(encoding="utf-8"))

    narrador = Narrador(
        {"tts": {"boas_vindas": ["bem-vindo, {nome}!"]}}, gerar=gerar, tocar=tocar
    )
    narrador.ligar()
    try:
        narrador.anunciar_entrada("ana")

        limite = time.monotonic() + 5
        while not tocados and time.monotonic() < limite:
            time.sleep(0.01)
        assert tocados == ["bem-vindo, ana!"]

        limite = time.monotonic() + 5
        while caminho.exists() and time.monotonic() < limite:
            time.sleep(0.01)
    finally:
        narrador.parar()

    assert not caminho.exists()
