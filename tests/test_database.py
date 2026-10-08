"""Persistencia.

O canvas nao pode ser perdido ao reiniciar: a arte de dias atras e o motivo de
a pessoa voltar. O teste central aqui e o round-trip — pintar, FECHAR, reabrir,
e conferir que tudo voltou identico, dono por dono.

`pixel_history` e append-only. Nenhum caminho do codigo apaga linhas dessa
tabela, nunca: ela e a memoria do projeto.
"""

import pytest

from game.canvas import Celula

from backend.database import Database

TABELAS = {
    "users",
    "pixels",
    "pixel_history",
    "paint_actions",
    "gifts",
    "events",
    "achievements",
    "user_stats",
    "canvas_settings",
    "challenges",
}


async def abrir(tmp_path, nome: str = "teste.db") -> Database:
    db = Database(tmp_path / nome)
    await db.abrir()
    return db


# --------------------------------------------------------------------------
# Abertura e schema
# --------------------------------------------------------------------------


async def test_abrir_cria_o_arquivo(tmp_path):
    db = await abrir(tmp_path)
    await db.fechar()

    assert (tmp_path / "teste.db").exists()


async def test_schema_cria_as_dez_tabelas(tmp_path):
    db = await abrir(tmp_path)

    nomes = await db.tabelas()

    await db.fechar()
    assert TABELAS.issubset(set(nomes))


async def test_abrir_e_idempotente(tmp_path):
    db = await abrir(tmp_path)
    await db.fechar()

    db2 = Database(tmp_path / "teste.db")
    await db2.abrir()
    nomes = await db2.tabelas()
    await db2.fechar()

    assert TABELAS.issubset(set(nomes))


# --------------------------------------------------------------------------
# Round-trip: o teste que prova que a arte sobrevive ao restart
# --------------------------------------------------------------------------


async def test_round_trip_preserva_o_canvas_inteiro(tmp_path):
    db = await abrir(tmp_path)
    await db.salvar_pixel(7, 5, "#FF0055", "joao")
    await db.salvar_pixel(0, 0, "#00FF00", "maria")
    await db.salvar_pixel(25, 50, "#0000FF", "pedro", efeito="fogo")
    await db.fechar()

    db2 = Database(tmp_path / "teste.db")
    await db2.abrir()
    celulas = await db2.carregar_canvas()
    await db2.fechar()

    por_coordenada = {(c.x, c.y): c for c in celulas}

    assert len(por_coordenada) == 3
    assert por_coordenada[(7, 5)].color == "#FF0055"
    assert por_coordenada[(7, 5)].owner_id == "joao"
    assert por_coordenada[(0, 0)].owner_id == "maria"
    assert por_coordenada[(25, 50)].effect == "fogo"


async def test_round_trip_preserva_o_historico(tmp_path):
    db = await abrir(tmp_path)
    await db.registrar_historico(7, 5, "#FF0055", "joao")
    await db.registrar_historico(7, 5, "#00FF00", "maria")
    await db.fechar()

    db2 = Database(tmp_path / "teste.db")
    await db2.abrir()
    historico = await db2.historico_pixel(7, 5)
    await db2.fechar()

    assert len(historico) == 2


async def test_carregar_canvas_vazio_devolve_lista_vazia(tmp_path):
    db = await abrir(tmp_path)

    celulas = await db.carregar_canvas()

    await db.fechar()
    assert celulas == []


async def test_carregar_canvas_devolve_celulas_do_modelo(tmp_path):
    db = await abrir(tmp_path)
    await db.salvar_pixel(7, 5, "#FF0055", "joao")

    celulas = await db.carregar_canvas()

    await db.fechar()
    assert all(isinstance(c, Celula) for c in celulas)


# --------------------------------------------------------------------------
# Tabela pixels: linha atual, uma por coordenada
# --------------------------------------------------------------------------


async def test_salvar_pixel_duas_vezes_nao_duplica_a_linha(tmp_path):
    db = await abrir(tmp_path)

    await db.salvar_pixel(7, 5, "#FF0055", "joao")
    await db.salvar_pixel(7, 5, "#00FF00", "maria")

    celulas = await db.carregar_canvas()
    await db.fechar()

    assert len(celulas) == 1
    assert celulas[0].owner_id == "maria"


async def test_salvar_pixel_mesmo_dono_atualiza_a_cor(tmp_path):
    db = await abrir(tmp_path)

    await db.salvar_pixel(7, 5, "#FF0055", "joao")
    await db.salvar_pixel(7, 5, "#FFFFFF", "joao")

    celulas = await db.carregar_canvas()
    await db.fechar()

    assert celulas[0].color == "#FFFFFF"


# --------------------------------------------------------------------------
# Historico: append-only
# --------------------------------------------------------------------------


async def test_historico_guarda_todas_as_pinturas(tmp_path):
    db = await abrir(tmp_path)

    await db.registrar_historico(7, 5, "#FF0055", "joao")
    await db.registrar_historico(7, 5, "#00FF00", "maria")
    await db.registrar_historico(7, 5, "#0000FF", "pedro")

    historico = await db.historico_pixel(7, 5)
    await db.fechar()

    assert len(historico) == 3
    assert {h["owner_id"] for h in historico} == {"joao", "maria", "pedro"}


async def test_historico_vem_do_mais_novo_para_o_mais_antigo(tmp_path):
    db = await abrir(tmp_path)
    await db.registrar_historico(7, 5, "#FF0055", "joao")
    await db.registrar_historico(7, 5, "#00FF00", "maria")

    historico = await db.historico_pixel(7, 5)
    await db.fechar()

    assert historico[0]["owner_id"] == "maria"


async def test_historico_respeita_o_limite(tmp_path):
    db = await abrir(tmp_path)
    for i in range(10):
        await db.registrar_historico(7, 5, "#FF0055", f"user{i}")

    historico = await db.historico_pixel(7, 5, limite=3)
    await db.fechar()

    assert len(historico) == 3


async def test_historico_de_outra_coordenada_nao_se_mistura(tmp_path):
    db = await abrir(tmp_path)
    await db.registrar_historico(7, 5, "#FF0055", "joao")
    await db.registrar_historico(0, 0, "#00FF00", "maria")

    historico = await db.historico_pixel(7, 5)
    await db.fechar()

    assert len(historico) == 1
    assert historico[0]["owner_id"] == "joao"


# --------------------------------------------------------------------------
# Usuarios
# --------------------------------------------------------------------------


async def test_upsert_usuario_cria(tmp_path):
    db = await abrir(tmp_path)

    await db.upsert_usuario("joao", display_name="Joao", color="#FF0055")

    usuario = await db.usuario("joao")
    await db.fechar()

    assert usuario is not None
    assert usuario["color"] == "#FF0055"


async def test_upsert_usuario_nao_duplica(tmp_path):
    db = await abrir(tmp_path)

    await db.upsert_usuario("joao", display_name="Joao")
    await db.upsert_usuario("joao", display_name="Joao Silva")

    total = await db.contar_usuarios()
    usuario = await db.usuario("joao")
    await db.fechar()

    assert total == 1
    assert usuario["display_name"] == "Joao Silva"


async def test_upsert_usuario_preserva_a_cor_quando_nao_informada(tmp_path):
    db = await abrir(tmp_path)
    await db.upsert_usuario("joao", display_name="Joao", color="#FF0055")

    await db.upsert_usuario("joao", display_name="Joao")

    usuario = await db.usuario("joao")
    await db.fechar()

    assert usuario["color"] == "#FF0055"


async def test_usuario_inexistente_devolve_none(tmp_path):
    db = await abrir(tmp_path)

    assert await db.usuario("ninguem") is None
    await db.fechar()


async def test_contar_usuarios(tmp_path):
    db = await abrir(tmp_path)
    await db.upsert_usuario("joao")
    await db.upsert_usuario("maria")

    assert await db.contar_usuarios() == 2
    await db.fechar()


# --------------------------------------------------------------------------
# Ranking
# --------------------------------------------------------------------------


async def test_top_pintores_ordena_por_pixels(tmp_path):
    db = await abrir(tmp_path)
    await db.contabilizar_pintura("joao", pixels=10, sobrescrita=False)
    await db.contabilizar_pintura("maria", pixels=30, sobrescrita=False)
    await db.contabilizar_pintura("pedro", pixels=20, sobrescrita=False)

    top = await db.top_pintores(3)
    await db.fechar()

    assert [u["handle"] for u in top] == ["maria", "pedro", "joao"]


async def test_top_pintores_respeita_o_limite(tmp_path):
    db = await abrir(tmp_path)
    for i in range(10):
        await db.contabilizar_pintura(f"user{i}", pixels=i + 1, sobrescrita=False)

    top = await db.top_pintores(3)
    await db.fechar()

    assert len(top) == 3


async def test_top_pintores_em_banco_vazio(tmp_path):
    db = await abrir(tmp_path)

    assert await db.top_pintores(5) == []
    await db.fechar()


async def test_sobrescrita_conta_separado(tmp_path):
    db = await abrir(tmp_path)

    await db.contabilizar_pintura("joao", pixels=1, sobrescrita=False)
    await db.contabilizar_pintura("joao", pixels=2, sobrescrita=True)

    usuario = await db.usuario("joao")
    await db.fechar()

    assert usuario["pixels_painted"] == 3
    assert usuario["pixels_overwritten"] == 1


async def test_quem_perdeu_o_pixel_registra_a_perda(tmp_path):
    """A arte pode ser disputada; a historia de quem pintou nao e apagada."""
    db = await abrir(tmp_path)
    await db.salvar_pixel(7, 5, "#FF0055", "joao")

    await db.registrar_perda("joao")

    usuario = await db.usuario("joao")
    await db.fechar()

    assert usuario["pixels_lost"] == 1


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


async def test_settings_round_trip(tmp_path):
    db = await abrir(tmp_path)

    await db.salvar_settings({"cols": 26, "rows": 51})

    assert await db.carregar_settings() == {"cols": 26, "rows": 51}
    await db.fechar()


async def test_settings_vazio_devolve_dict_vazio(tmp_path):
    db = await abrir(tmp_path)

    assert await db.carregar_settings() == {}
    await db.fechar()


async def test_settings_sobrescreve_a_chave(tmp_path):
    db = await abrir(tmp_path)
    await db.salvar_settings({"cols": 26})
    await db.salvar_settings({"cols": 50, "rows": 100})

    settings = await db.carregar_settings()
    await db.fechar()

    assert settings["cols"] == 50
    assert settings["rows"] == 100


async def test_limpar_canvas_esvazia_a_tabela_de_pixels(tmp_path):
    """O `DELETE` que o botao LIMPAR dispara.

    Sem ele o quadro voltaria em branco na tela e REAPARECERIA inteiro no
    proximo reinicio do servidor: a memoria foi limpa e o disco nao.
    """
    db = await abrir(tmp_path)
    await db.salvar_pixel(7, 5, "#FF0055", "joao")
    await db.salvar_pixel(0, 0, "#00FF00", "maria")

    quantas = await db.limpar_canvas()

    assert quantas == 2
    assert await db.carregar_canvas() == []
    await db.fechar()


async def test_limpar_canvas_preserva_o_historico(tmp_path):
    """O historico e a memoria do que aconteceu, nao o desenho.

    Quem pinta por cima do pixel de alguem continua registrado mesmo depois
    de o streamer limpar o quadro — e e a unica forma de responder "quem
    apagou o meu pixel?" no meio da LIVE.
    """
    db = await abrir(tmp_path)
    await db.salvar_pixel(7, 5, "#FF0055", "joao")
    await db.registrar_historico(7, 5, "#FF0055", "joao")

    await db.limpar_canvas()

    assert await db.carregar_canvas() == []
    historico = await db.historico_pixel(7, 5)
    assert len(historico) == 1
    assert historico[0]["owner_id"] == "joao"
    await db.fechar()


async def test_limpar_canvas_vazio_nao_quebra(tmp_path):
    db = await abrir(tmp_path)

    assert await db.limpar_canvas() == 0

    await db.fechar()
