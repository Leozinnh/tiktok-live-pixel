"""O ranking em memoria.

Ele existe porque o ranking aparece na tela a cada pintura. Ir ao banco toda
vez seria uma consulta por pixel pintado, num jogo onde a graca e a resposta
instantanea. O banco continua sendo a verdade — ele so e lido uma vez, no
boot, para aquecer este objeto.

O ranking guarda TODO MUNDO, nao so os cinco da tela: `/rank` precisa
responder a posicao de quem esta em 40o lugar, e essa pessoa e justamente
quem mais quer saber.
"""

import pytest

from game.ranking import EntradaRanking, Ranking

PALETA = ["#FF3B5C", "#3DFF8A", "#3D9BFF", "#FFD93D"]


def criar() -> Ranking:
    return Ranking(paleta=PALETA, tamanho=5)


# --------------------------------------------------------------------------
# Registro
# --------------------------------------------------------------------------


def test_registrar_cria_a_entrada():
    r = criar()

    entrada = r.registrar("joao", nome="Joao")

    assert entrada.handle == "joao"
    assert entrada.nome == "Joao"


def test_pintura_acumula_celulas_e_xp():
    r = criar()
    r.registrar("joao", pixels=1, xp=10)
    r.registrar("joao", pixels=1, xp=15)

    entrada = r.registrar("joao", pixels=1, xp=10)

    assert entrada.pixels == 3
    assert entrada.xp == 35


def test_handle_e_normalizado():
    """'@Joao' e 'joao' sao a mesma pessoa — senao o ranking duplica gente."""
    r = criar()
    r.registrar("@Joao", pixels=1)
    r.registrar("joao", pixels=1)

    assert r.total() == 1
    assert r.entrada("JOAO").pixels == 2


def test_registrar_sem_args_so_cria():
    r = criar()

    entrada = r.registrar("joao")

    assert entrada.pixels == 0
    assert entrada.xp == 0


# --------------------------------------------------------------------------
# Nivel e titulo saem do XP
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "xp, nivel, titulo",
    [
        (0, 1, "Novato"),
        (100, 2, "Novato"),
        (550, 5, "Pintor"),
        (1800, 10, "Artista"),
        (6175, 20, "Mestre"),
        (13050, 30, "Pixel Master"),
        (34300, 50, "Lenda"),
    ],
)
def test_nivel_e_titulo_seguem_o_xp(xp, nivel, titulo):
    r = criar()
    entrada = r.registrar("joao", xp=xp)

    assert entrada.nivel == nivel
    assert entrada.titulo == titulo


def test_nivel_sobe_conforme_o_xp_entra():
    r = criar()
    r.registrar("joao", xp=95)
    assert r.entrada("joao").nivel == 1

    entrada = r.registrar("joao", xp=10)

    assert entrada.nivel == 2


# --------------------------------------------------------------------------
# Ordem
# --------------------------------------------------------------------------


def test_top_ordena_por_pixels():
    r = criar()
    r.registrar("joao", pixels=10)
    r.registrar("maria", pixels=30)
    r.registrar("pedro", pixels=20)

    top = r.top()

    assert [e.handle for e in top] == ["maria", "pedro", "joao"]


def test_empate_desempata_por_quem_chegou_primeiro():
    """Quem chegou antes fica na frente. Ordem estavel, nao sorteada."""
    r = criar()
    r.registrar("joao", pixels=10)
    r.registrar("maria", pixels=10)
    r.registrar("pedro", pixels=10)

    top = r.top()

    assert [e.handle for e in top] == ["joao", "maria", "pedro"]


def test_top_respeita_o_tamanho():
    r = criar()
    for i in range(10):
        r.registrar(f"user{i}", pixels=i + 1)

    assert len(r.top()) == 5


def test_top_aceita_tamanho_proprio():
    r = criar()
    for i in range(10):
        r.registrar(f"user{i}", pixels=i + 1)

    assert len(r.top(3)) == 3


def test_top_em_ranking_vazio():
    assert criar().top() == []


def test_top_devolve_copias_da_ordem():
    """Mexer no top nao pode reordenar o ranking de verdade."""
    r = criar()
    r.registrar("joao", pixels=10)
    r.registrar("maria", pixels=30)

    top = r.top()
    top.reverse()

    assert [e.handle for e in r.top()] == ["maria", "joao"]


# --------------------------------------------------------------------------
# Posicao: o que /rank responde
# --------------------------------------------------------------------------


def test_posicao_comeca_em_um():
    r = criar()
    r.registrar("maria", pixels=30)
    r.registrar("joao", pixels=10)

    assert r.posicao("maria") == 1
    assert r.posicao("joao") == 2


def test_posicao_de_quem_esta_fora_do_top():
    """O ranking guarda todos; a tela mostra cinco."""
    r = criar()
    for i in range(20):
        r.registrar(f"user{i}", pixels=100 - i)

    assert r.posicao("user19") == 20


def test_posicao_de_desconhecido_e_zero():
    assert criar().posicao("ninguem") == 0


def test_posicao_ignora_caixa():
    r = criar()
    r.registrar("joao", pixels=10)

    assert r.posicao("@JOAO") == 1


def test_total_conta_todo_mundo():
    r = criar()
    for i in range(12):
        r.registrar(f"user{i}", pixels=1)

    assert r.total() == 12


# --------------------------------------------------------------------------
# Cores usadas
# --------------------------------------------------------------------------


def test_cores_usadas_conta_distintas():
    r = criar()
    r.registrar("joao", cor_pintada="#FF3B5C")
    r.registrar("joao", cor_pintada="#FF3B5C")
    r.registrar("joao", cor_pintada="#3DFF8A")

    assert r.entrada("joao").cores_usadas == 2
    assert r.entrada("joao").cores == {"#FF3B5C", "#3DFF8A"}


def test_cor_pintada_ausente_nao_conta():
    r = criar()
    r.registrar("joao", cor_pintada=None)

    assert r.entrada("joao").cores_usadas == 0


def test_cor_automatica_e_atribuida_a_quem_nao_tem():
    r = criar()

    entrada = r.registrar("joao")

    assert entrada.cor in PALETA


def test_cor_automatica_e_estavel_para_a_mesma_pessoa():
    r = criar()
    primeira = r.registrar("joao").cor

    assert r.registrar("joao").cor == primeira


def test_cor_escolhida_pelo_usuario_nao_e_sobrescrita():
    """Quem escolheu /cor roxo fica roxo, nao volta para a cor do hash."""
    r = criar()
    r.registrar("joao", cor="#A855F7")

    entrada = r.registrar("joao", pixels=1)

    assert entrada.cor == "#A855F7"


def test_nome_nao_e_apagado_quando_ausente():
    r = criar()
    r.registrar("joao", nome="Joao Silva")

    entrada = r.registrar("joao", pixels=1)

    assert entrada.nome == "Joao Silva"


def test_nome_atualiza_quando_informado():
    r = criar()
    r.registrar("joao", nome="Joao")
    entrada = r.registrar("joao", nome="Joao Silva")

    assert entrada.nome == "Joao Silva"


def test_entrada_de_desconhecido_e_none():
    assert criar().entrada("ninguem") is None


# --------------------------------------------------------------------------
# Serializacao para o WebSocket
# --------------------------------------------------------------------------


def test_para_dict_leva_o_que_a_tela_mostra():
    r = criar()
    r.registrar("joao", nome="Joao", pixels=7, sobrescritos=2, xp=100)

    d = r.registrar("joao", cor_pintada="#FF3B5C").para_dict()

    assert d["handle"] == "joao"
    assert d["name"] == "Joao"
    assert d["pixels"] == 7
    assert d["overwritten"] == 2
    assert d["xp"] == 100
    assert d["level"] == 2
    assert d["title"] == "Novato"
    assert d["colors"] == 1


def test_para_dict_segue_a_forma_do_spec_12():
    """O spec §12 e o contrato entre backend e tela. Os nomes internos sao
    nossos e em portugues; a fronteira de fio fala a lingua do spec — um
    contrato que nao casa com o proprio spec e pior que um idioma misto."""
    r = criar()
    r.registrar("joao", nome="Joao", pixels=427, xp=4300)

    d = r.registrar("joao").para_dict()

    for chave in ("user", "pixels", "level", "title"):
        assert chave in d, f"falta `{chave}` do spec §12"
    for antiga in ("nome", "nivel", "titulo", "sobrescritos"):
        assert antiga not in d, f"`{antiga}` e nome interno e nao vai para o fio"


def test_o_campo_user_leva_o_arroba():
    """`pixel_painted` ja manda `user` como "@joao"; o ranking tem que casar,
    senao a tela precisa de dois caminhos para a mesma coisa."""
    r = criar()
    r.registrar("joao", pixels=1)

    d = r.registrar("joao").para_dict()

    assert d["user"] == "@joao"
    assert d["handle"] == "joao"


def test_top_vem_ordenado_e_com_posicao():
    r = criar()
    r.registrar("joao", pixels=10)
    r.registrar("maria", pixels=30)

    payload = r.top_para_dict()

    assert [e["handle"] for e in payload] == ["maria", "joao"]
    assert [e["position"] for e in payload] == [1, 2]


def test_para_dict_e_serializavel_em_json():
    import json

    r = criar()
    r.registrar("joao", nome="Joao", pixels=3, xp=30, cor_pintada="#FF3B5C")

    texto = json.dumps(r.top_para_dict())

    assert "joao" in texto


# --------------------------------------------------------------------------
# Aquecimento a partir do banco
# --------------------------------------------------------------------------


def test_carregar_repovoa_do_banco():
    """O boot le `top_pintores()` uma vez e o ranking nunca mais toca o disco."""
    r = criar()

    r.carregar(
        [
            {"handle": "maria", "display_name": "Maria", "color": "#FF3B5C",
             "pixels_painted": 30, "pixels_overwritten": 4, "xp": 400},
            {"handle": "joao", "display_name": "Joao", "color": None,
             "pixels_painted": 10, "pixels_overwritten": 0, "xp": 100},
        ]
    )

    assert [e.handle for e in r.top()] == ["maria", "joao"]
    assert r.entrada("maria").sobrescritos == 4
    assert r.entrada("maria").nivel == 4  # 375 <= 400 < 550


def test_carregar_sem_cor_atribui_a_automatica():
    r = criar()

    r.carregar([{"handle": "joao", "pixels_painted": 1, "display_name": None}])

    assert r.entrada("joao").cor in PALETA


def test_carregar_substitui_o_que_havia():
    """Aquecer duas vezes nao pode dobrar os numeros."""
    r = criar()
    r.registrar("joao", pixels=5)

    r.carregar([{"handle": "joao", "pixels_painted": 10}])

    assert r.entrada("joao").pixels == 10
    assert r.total() == 1


def test_carregar_aceita_linha_sem_campos_opcionais():
    r = criar()

    r.carregar([{"handle": "joao"}])

    assert r.total() == 1
    assert r.entrada("joao").pixels == 0


# --------------------------------------------------------------------------
# EntradaRanking isolada
# --------------------------------------------------------------------------


def test_entrada_e_mutavel_no_lugar():
    e = EntradaRanking(handle="joao")
    e.pixels += 3

    assert e.pixels == 3


def test_em_patamar_de_cores_compara_conjuntos():
    e = EntradaRanking(handle="joao", cores={"#FF3B5C", "#3DFF8A"})

    assert e.cores_usadas == 2


def test_paleta_vazia_nao_quebra():
    """Sem paleta configurada o ranking ainda precisa funcionar."""
    r = Ranking(paleta=[], tamanho=5)

    entrada = r.registrar("joao")

    assert entrada.cor


# --------------------------------------------------------------------------
# Efeito: a cor especial escolhida em /cor
# --------------------------------------------------------------------------


def test_efeito_fica_na_entrada():
    r = criar()
    entrada = r.registrar("joao", cor="#FF3B5C", efeito="fogo")

    assert entrada.efeito == "fogo"


def test_efeito_nao_e_apagado_quando_ausente():
    """Um comentario comum nao pode tirar o fogo de quem escolheu fogo."""
    r = criar()
    r.registrar("joao", efeito="fogo")

    entrada = r.registrar("joao", pixels=1)

    assert entrada.efeito == "fogo"


def test_efeito_troca_quando_informado():
    r = criar()
    r.registrar("joao", efeito="fogo")

    entrada = r.registrar("joao", efeito="neon")

    assert entrada.efeito == "neon"


def test_efeito_explicito_none_limpa():
    """Escolher /cor verde precisa APAGAR o fogo de quem era fogo."""
    r = criar()
    r.registrar("joao", efeito="fogo")

    entrada = r.registrar("joao", efeito=None, cor="#3DFF8A")

    assert entrada.efeito is None
    assert entrada.cor == "#3DFF8A"


def test_carregar_le_o_efeito_do_banco():
    r = criar()

    r.carregar([{"handle": "joao", "color": "#FF3B5C", "effect": "fogo"}])

    assert r.entrada("joao").efeito == "fogo"


def test_para_dict_leva_o_efeito():
    r = criar()
    entrada = r.registrar("joao", efeito="neon")

    assert entrada.para_dict()["effect"] == "neon"
