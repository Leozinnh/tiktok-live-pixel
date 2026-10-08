"""Carregamento e validacao da configuracao.

Toda a afinacao do jogo vive em config.json e nada mais. Este modulo carrega,
mescla com os padroes e RECUSA subir com valor invalido: um jogo configurado
errado que sobe e pior que um que nao sobe, porque o erro so aparece no ar.

As mensagens de erro sempre citam a chave completa (ex: `canvas.cols`), porque
quem edita o arquivo precisa saber exatamente qual linha corrigir.
"""

import copy
import json
from pathlib import Path
from typing import Any

PLACEHOLDER_USERNAME = "@SEU_USUARIO"

# Colunas vao de A ate ZZ: 26 + 26*26 = 702. Alem disso o rotulo deixa de ser
# algo que uma pessoa consegue digitar sem errar.
MAX_COLUNAS = 702


class ConfigError(Exception):
    """Configuracao ausente, malformada ou invalida."""


PADROES: dict[str, Any] = {
    "app": {
        "titulo": "PIXEL WORLD",
        "subtitulo": "VOCE CONTROLA A ARTE",
        "log_dir": "logs",
        "db_path": "pixelworld.db",
        "feed_size": 6,
        "events_per_frame": 400,
    },
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
        "frame_ms": 50,
    },
    "canvas": {
        # 50 colunas usam a largura do quadro 1080x1920 por inteiro: com 26 a
        # grade ficava uma tira estreita no meio, com duas faixas mortas de
        # ~200px de cada lado. O alfabeto vai de A a Z e depois continua em
        # AA..AX, a mesma indexacao de planilha que o parser ja entendia.
        "cols": 50,
        "rows": 51,
        "paleta": {
            "vermelho": "#FF3B5C",
            "laranja": "#FF8A3D",
            "amarelo": "#FFD93D",
            "verde": "#3DFF8A",
            "azul": "#3D9BFF",
            "roxo": "#A855F7",
            "rosa": "#FF6FD8",
            "branco": "#EEF2FF",
        },
        "especiais": {},
    },
    "tiktok": {
        "username": PLACEHOLDER_USERNAME,
        "reconnect_seconds": 5,
        "reconnect_max_seconds": 60,
        "fetch_gift_info": True,
        "cooldown_pintura": 2.0,
    },
    "rewards": {
        "pixel_custo": 1,
        "sobrescrita_custo": 2,
        "presente_desconhecido": 1,
        # O quanto um STREAK multiplica. Dez rosas valem dez pixels; cem rosas
        # param aqui. Sem esta chave no arquivo, o codigo cai no padrao 10 e o
        # teto vale em silencio — foi o que aconteceu ate agora.
        "max_multiplicador": 100,
        "gifts": {"Rose": 1},
        "like": {"curtidas_por_pixel": 20, "max_pixels": 10},
        "follow": {"pixels": 5},
        "share": {"pixels": 3},
    },
    "xp": {
        "por_pixel": 10,
        "por_sobrescrita": 15,
        "base_por_nivel": 100,
        "passo_por_nivel": 25,
    },
    # O catalogo vazio e proposital: os eventos do spec vivem em
    # `game/events.py:CATALOGO_PADRAO`, e o config.json traz a copia explicita
    # para quem quiser mexer. Duas listas iguais em dois arquivos divergem —
    # entao so a do codigo e a fonte, e a do arquivo e a que o streamer edita.
    "events": {
        "active": True,
        "interval": 180,
        "first_after": 75,
        "catalog": [],
    },
    "limits": {
        "queue_max_size": 5000,
        "max_pixels_por_evento": 400,
        "max_pixels_por_comentario": 100,
        "action_budget": {"pintar": 40.0},
    },
}


def _mesclar(base: dict, por_cima: dict) -> dict:
    """Mescla profunda: o que o usuario definiu ganha, o resto vem do padrao."""
    saida = copy.deepcopy(base)
    for chave, valor in por_cima.items():
        if isinstance(valor, dict) and isinstance(saida.get(chave), dict):
            saida[chave] = _mesclar(saida[chave], valor)
        else:
            saida[chave] = copy.deepcopy(valor)
    return saida


def _inteiro(valor: Any) -> bool:
    """`bool` e subclasse de `int` em Python; `true` nao e um numero valido."""
    return isinstance(valor, int) and not isinstance(valor, bool)


def _exigir_inteiro(cfg: dict, caminho: str, minimo: int, maximo: int | None = None) -> None:
    atual: Any = cfg
    for parte in caminho.split("."):
        if not isinstance(atual, dict) or parte not in atual:
            raise ConfigError(f"Falta a chave obrigatoria `{caminho}` na configuracao.")
        atual = atual[parte]

    if not _inteiro(atual):
        raise ConfigError(f"`{caminho}` precisa ser um numero inteiro (recebi {atual!r}).")

    if atual < minimo:
        raise ConfigError(f"`{caminho}` precisa ser >= {minimo} (recebi {atual}).")

    if maximo is not None and atual > maximo:
        raise ConfigError(f"`{caminho}` precisa ser <= {maximo} (recebi {atual}).")


def _validar_pixels_nao_negativos(no: Any, caminho: str) -> None:
    """Percorre a arvore de recompensas procurando qualquer chave `pixels`."""
    if not isinstance(no, dict):
        return
    for chave, valor in no.items():
        filho = f"{caminho}.{chave}"
        if chave == "pixels":
            if not _inteiro(valor) or valor < 0:
                raise ConfigError(f"`{filho}` precisa ser um inteiro >= 0 (recebi {valor!r}).")
        elif isinstance(valor, dict):
            _validar_pixels_nao_negativos(valor, filho)


def carregar(caminho: str | Path, exigir_username: bool = True) -> dict:
    """Le, mescla com os padroes e valida.

    `exigir_username=False` e o modo teste: o placeholder de usuario passa,
    porque nao ha LIVE para conectar.
    """
    caminho = Path(caminho)

    if not caminho.exists():
        raise ConfigError(
            f"Nao encontrei a configuracao em `{caminho}`. "
            f"Copie o config.json do projeto para esse caminho."
        )

    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as erro:
        raise ConfigError(f"Nao consegui ler `{caminho}`: {erro}") from erro

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError as erro:
        raise ConfigError(
            f"`{caminho}` nao e um JSON valido: {erro.msg} "
            f"(linha {erro.lineno}, coluna {erro.colno})."
        ) from erro

    if not isinstance(dados, dict):
        raise ConfigError(f"`{caminho}` precisa conter um objeto JSON na raiz.")

    cfg = _mesclar(PADROES, dados)

    _exigir_inteiro(cfg, "canvas.cols", 1, MAX_COLUNAS)
    _exigir_inteiro(cfg, "canvas.rows", 1)
    _exigir_inteiro(cfg, "server.port", 1, 65535)
    _exigir_inteiro(cfg, "limits.queue_max_size", 1)
    _exigir_inteiro(cfg, "limits.max_pixels_por_evento", 0)
    _exigir_inteiro(cfg, "limits.max_pixels_por_comentario", 1)
    _exigir_inteiro(cfg, "rewards.max_multiplicador", 1)

    # Sobrescrita de graca tornaria o vandalismo trivial: qualquer um apagaria
    # o desenho da comunidade inteira sem gastar nada.
    _exigir_inteiro(cfg, "rewards.sobrescrita_custo", 1)

    _validar_pixels_nao_negativos(cfg.get("rewards", {}), "rewards")

    username = str(cfg["tiktok"].get("username", "")).strip()
    if exigir_username and username == PLACEHOLDER_USERNAME:
        raise ConfigError(
            "`tiktok.username` ainda e o placeholder "
            f"`{PLACEHOLDER_USERNAME}`. Troque pelo @ do seu perfil, "
            "ou rode com --test para jogar sem LIVE."
        )

    return cfg


def paleta_para_lista(cfg: dict) -> list[tuple[str, str]]:
    """Paleta como lista ordenada de (nome, hex).

    A ordem do JSON e preservada, e e ela que define o indice usado pela cor
    automatica de cada usuario.
    """
    return [(nome, cor) for nome, cor in cfg["canvas"]["paleta"].items()]
