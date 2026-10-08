"""O canvas em memoria.

E a fonte de verdade para renderizacao. O SQLite e write-behind: a pintura e
aplicada aqui, transmitida na hora, e persistida depois. Um disco lento nunca
aparece na tela.

O canvas NAO assume 26x51 em lugar nenhum. A expansao do mapa (26x51 -> 50x100
-> 100x100) e uma mudanca de config mais uma migracao de schema, nao uma
reescrita — e essa promessa so vale enquanto todo acesso passar por aqui.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from game.coordinates import indice_de, rotulo_de


def agora_iso() -> str:
    """Instante atual em ISO 8601, UTC."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(slots=True)
class Celula:
    """Um quadrado do canvas.

    Uma celula sem `color` nunca foi pintada. `owner_id` e o identificador
    estavel do autor (o @ sem arroba, minusculo), nao o nome de exibicao.
    """

    x: int
    y: int
    color: str | None = None
    owner_id: str | None = None
    painted_at: str | None = None
    effect: str | None = None

    @property
    def pintada(self) -> bool:
        return self.color is not None

    @property
    def rotulo(self) -> str:
        return rotulo_de(self.x, self.y)

    def para_dict(self) -> dict:
        """Forma de fio, com os nomes do spec §12. Curta de proposito: isto
        viaja a cada pintura, e as chaves sao as mesmas que `pixel_painted`
        usa, para que a tela leia uma celula do `hello` e um pixel recebido
        ao vivo com o mesmo codigo."""
        return {
            "x": self.x,
            "y": self.y,
            "coordinate": self.rotulo,
            "color": self.color,
            "user": f"@{self.owner_id}" if self.owner_id else None,
            "ts": self.painted_at,
            "effect": self.effect,
        }


class CanvasModel:
    """Grade de celulas, com acesso por (x, y)."""

    def __init__(self, cols: int, rows: int):
        if cols < 1 or rows < 1:
            raise ValueError(f"Canvas precisa de pelo menos 1x1 (recebi {cols}x{rows}).")

        self.cols = cols
        self.rows = rows
        self.total = cols * rows
        self._celulas: list[Celula] = [
            Celula(x=i % cols, y=i // cols) for i in range(self.total)
        ]

    # ------------------------------------------------------------------
    # Coordenada -> celula
    # ------------------------------------------------------------------

    def _dentro(self, x: int, y: int) -> bool:
        return 0 <= x < self.cols and 0 <= y < self.rows

    def _indice(self, x: int, y: int) -> int:
        if not self._dentro(x, y):
            raise IndexError(
                f"Coordenada fora do canvas {self.cols}x{self.rows}: ({x}, {y})."
            )
        return indice_de(x, y, self.cols)

    def celula(self, x: int, y: int) -> Celula | None:
        """A celula, ou None se estiver fora do canvas.

        Consultar fora do canvas nao e erro — o HUD varre regioes o tempo
        todo. So PINTAR fora e erro.
        """
        if not self._dentro(x, y):
            return None
        return self._celulas[indice_de(x, y, self.cols)]

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def pintar(
        self,
        x: int,
        y: int,
        color: str,
        owner_id: str,
        efeito: str | None = None,
    ) -> Celula:
        celula = self._celulas[self._indice(x, y)]
        celula.color = color
        celula.owner_id = owner_id
        celula.painted_at = agora_iso()
        celula.effect = efeito
        return celula

    def apagar(self, x: int, y: int) -> Celula:
        """Devolve a celula ao estado virgem. So o painel do streamer faz isso."""
        celula = self._celulas[self._indice(x, y)]
        celula.color = None
        celula.owner_id = None
        celula.painted_at = None
        celula.effect = None
        return celula

    def limpar(self) -> None:
        """Devolve o quadro INTEIRO ao estado virgem.

        E a operacao mais destrutiva do jogo e nao tem desfazer: o desenho que
        a comunidade levou a LIVE inteira para fazer some num clique. Ela
        existe porque o streamer precisa poder recomeçar — ensaio, teste de
        layout, um desenho que virou bagunça — e sem um botao para isso a
        unica saida seria apagar o banco com o servidor parado.

        Nao mexe em `cols`/`rows`: a grade e a mesma, o que fica em branco e a
        tinta. E nao mexe no ranking tampouco — quem pintou, pintou.
        """
        for celula in self._celulas:
            if celula.color is None and celula.owner_id is None:
                continue
            celula.color = None
            celula.owner_id = None
            celula.painted_at = None
            celula.effect = None

    def carregar(self, celulas: Iterable[Celula]) -> None:
        """Repovoa a partir do banco, descartando o estado anterior.

        Celulas fora do canvas atual sao ignoradas: um banco de um mapa maior
        nao pode derrubar um mapa menor.
        """
        for celula in self._celulas:
            celula.color = None
            celula.owner_id = None
            celula.painted_at = None
            celula.effect = None

        for origem in celulas:
            if not self._dentro(origem.x, origem.y):
                continue
            destino = self._celulas[indice_de(origem.x, origem.y, self.cols)]
            destino.color = origem.color
            destino.owner_id = origem.owner_id
            destino.painted_at = origem.painted_at
            destino.effect = origem.effect

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def preenchidas(self) -> int:
        return sum(1 for c in self._celulas if c.pintada)

    def percentual(self) -> float:
        if self.total == 0:
            return 0.0
        return round(100.0 * self.preenchidas() / self.total, 1)

    def celulas_pintadas(self) -> list[Celula]:
        return [c for c in self._celulas if c.pintada]

    def donos(self) -> set[str]:
        return {c.owner_id for c in self._celulas if c.owner_id}

    def para_dict(self) -> dict:
        """Estado completo, pronto para JSON.

        Manda so as celulas pintadas: num canvas vazio isso e uma lista vazia,
        e num canvas cheio e o mesmo tamanho do canvas. O que nunca acontece e
        mandar 1326 celulas vazias para dizer "nada aqui".
        """
        return {
            "cols": self.cols,
            "rows": self.rows,
            "total": self.total,
            "filled": self.preenchidas(),
            "percent": self.percentual(),
            "cells": [c.para_dict() for c in self._celulas if c.pintada],
        }
