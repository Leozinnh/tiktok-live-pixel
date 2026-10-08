"""Cores do jogo.

Duas origens, uma so forma de guardar:

- **Automatica**: todo mundo recebe uma cor ao aparecer, derivada do nome. A
  pessoa nao precisa escolher nada para participar — esse e o ponto. Quem
  quiser personaliza com `/cor`.
- **Escolhida**: `/cor vermelho` ou `/cor #FF0055`.

A cor automatica usa CRC32, e NAO `hash()`. O `hash()` de strings em Python e
aleatorizado por PYTHONHASHSEED a cada processo: o mesmo @joao apareceria
vermelho hoje e azul amanha, e a comunidade acharia que a arte mudou sozinha.
"""

import re
import unicodedata
import zlib
from dataclasses import dataclass
from typing import Sequence

PALETA_PADRAO: dict[str, str] = {
    "vermelho": "#FF3B5C",
    "laranja": "#FF8A3D",
    "amarelo": "#FFD93D",
    "verde": "#3DFF8A",
    "azul": "#3D9BFF",
    "roxo": "#A855F7",
    "rosa": "#FF6FD8",
    "branco": "#EEF2FF",
}

# Cor de partida de cada efeito especial. O efeito anima por cima dela; sem
# uma cor base, um pixel especial pintado num cliente que nao anima ficaria
# invisivel.
CORES_ESPECIAIS: dict[str, str] = {
    "arco_iris": "#FF00E5",
    "fogo": "#FF6A00",
    "eletrico": "#00E5FF",
    "galaxia": "#7B2FFF",
    "neon": "#39FF14",
    "diamante": "#7DF9FF",
}

COR_PADRAO = "#FFFFFF"

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COMANDO_COR = re.compile(r"^/?(?:cor|color)\s+", re.IGNORECASE)
_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class Cor:
    """Uma cor resolvida: o hex a pintar, e o efeito a animar por cima."""

    hex: str
    efeito: str | None = None


def achatar(texto: str) -> str:
    """Reduz a uma forma comparavel: sem acento, sem caixa, sem separador.

    "ARCO-ÍRIS", "arco iris" e "arco_iris" colapsam todos em "arcoiris", que e
    o que permite a pessoa escrever do jeito que ela lembra.
    """
    decomposto = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return _NAO_ALFANUMERICO.sub("", sem_acento.lower())


def cor_automatica(username: str, cores: Sequence[str]) -> str:
    """Cor estavel e deterministica para um nome.

    Determinismo importa mais que variedade: a mesma pessoa precisa ter a mesma
    cor em todo restart, sem que nada disso seja guardado no banco.
    """
    if not cores:
        return COR_PADRAO

    chave = (username or "").strip().lower().encode("utf-8")
    return cores[zlib.crc32(chave) % len(cores)]


def chave_especial(texto: str, especiais: dict[str, dict]) -> str | None:
    """Encontra a chave de uma cor especial, tolerando a grafia do usuario."""
    if not texto:
        return None

    alvo = achatar(texto)
    if not alvo:
        return None

    for chave in especiais:
        if achatar(chave) == alvo:
            return chave
    return None


def cor_do_especial(chave: str, especiais: dict[str, dict]) -> str:
    """Hex de partida de uma cor especial, com a config tendo a ultima palavra."""
    definicao = especiais.get(chave) or {}
    return definicao.get("hex") or CORES_ESPECIAIS.get(chave) or COR_PADRAO


def _por_nome(texto: str, paleta: dict[str, str]) -> str | None:
    alvo = achatar(texto)
    if not alvo:
        return None

    for nome, cor in paleta.items():
        if achatar(nome) == alvo:
            return cor
    return None


def parse_cor(texto, paleta: dict[str, str], especiais: dict[str, dict]) -> Cor | None:
    """Traduz o que a pessoa digitou numa cor, ou None.

    Aceita nome da paleta ("vermelho"), hex ("#FF0055") e cor especial
    ("arco-iris"), com ou sem o prefixo `/cor`.
    """
    if not isinstance(texto, str):
        return None

    limpo = _COMANDO_COR.sub("", texto.strip()).strip()
    if not limpo:
        return None

    if _HEX.match(limpo):
        return Cor(hex=limpo.upper())

    nomeado = _por_nome(limpo, paleta)
    if nomeado is not None:
        return Cor(hex=nomeado)

    especial = chave_especial(limpo, especiais)
    if especial is not None:
        return Cor(hex=cor_do_especial(especial, especiais), efeito=especial)

    return None


def cores_do_config(cfg: dict) -> tuple[dict[str, str], dict[str, dict]]:
    """Extrai (paleta, especiais) da configuracao."""
    canvas = cfg.get("canvas", {})
    return canvas.get("paleta", {}), canvas.get("especiais", {})


def lista_da_paleta(paleta: dict[str, str]) -> list[str]:
    """A paleta como lista, na ordem do JSON.

    A ordem define o indice que `cor_automatica` usa, entao ela e contrato:
    reordenar o config.json recolore a base inteira de usuarios.
    """
    return list(paleta.values())
