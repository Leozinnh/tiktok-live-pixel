"""Persistencia em SQLite.

O canvas nao pode ser perdido ao reiniciar — a arte de dias atras e o motivo
de a pessoa voltar amanha. Por isso o banco guarda tres coisas com propositos
diferentes:

- `pixels` — a linha ATUAL de cada celula. E o que o canvas carrega no boot.
  Uma linha por coordenada.
- `pixel_history` — APPEND-ONLY. Toda pintura que ja aconteceu naquela celula.
  E a memoria do projeto e o que permite responder "quem ja pintou aqui?" muito
  depois. Nenhum caminho deste modulo apaga uma linha daqui.
- `users` — a ficha de cada pessoa: cor, XP, pixels pintados, perdidos.

WAL + synchronous=NORMAL: escrita nao bloqueia leitura, e o custo de fsync cai
sem risco real (perder os ultimos milissegundos de um jogo ao vivo e aceitavel;
travar a tela nao e).
"""

import json
import logging
from pathlib import Path
from typing import Any, Iterable

import aiosqlite

from game.canvas import Celula, agora_iso

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    handle            TEXT PRIMARY KEY,
    display_name      TEXT,
    color             TEXT,
    effect            TEXT,
    xp                INTEGER NOT NULL DEFAULT 0,
    level             INTEGER NOT NULL DEFAULT 1,
    pixels_painted    INTEGER NOT NULL DEFAULT 0,
    pixels_overwritten INTEGER NOT NULL DEFAULT 0,
    pixels_lost       INTEGER NOT NULL DEFAULT 0,
    gifts_received    INTEGER NOT NULL DEFAULT 0,
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL,
    streak_days       INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pixels (
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    color      TEXT NOT NULL,
    owner_id   TEXT NOT NULL,
    painted_at TEXT NOT NULL,
    effect     TEXT,
    PRIMARY KEY (x, y)
);

CREATE TABLE IF NOT EXISTS pixel_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    color      TEXT NOT NULL,
    owner_id   TEXT NOT NULL,
    painted_at TEXT NOT NULL,
    effect     TEXT
);
CREATE INDEX IF NOT EXISTS idx_historico_coordenada
    ON pixel_history (x, y, id DESC);

CREATE TABLE IF NOT EXISTS paint_actions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    handle     TEXT,
    x          INTEGER,
    y          INTEGER,
    color      TEXT,
    cost       INTEGER NOT NULL DEFAULT 0,
    overwrite  INTEGER NOT NULL DEFAULT 0,
    result     TEXT NOT NULL,
    reason     TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_acoes_handle ON paint_actions (handle, id DESC);

CREATE TABLE IF NOT EXISTS gifts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    handle       TEXT NOT NULL,
    gift_name    TEXT NOT NULL,
    gift_id      TEXT,
    quantity     INTEGER NOT NULL DEFAULT 1,
    pixel_reward INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    chave      TEXT NOT NULL,
    nome       TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    payload    TEXT
);

CREATE TABLE IF NOT EXISTS achievements (
    handle          TEXT NOT NULL,
    achievement_key TEXT NOT NULL,
    unlocked_at     TEXT NOT NULL,
    PRIMARY KEY (handle, achievement_key)
);

CREATE TABLE IF NOT EXISTS user_stats (
    handle     TEXT PRIMARY KEY,
    cores_usadas INTEGER NOT NULL DEFAULT 0,
    participacoes INTEGER NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS canvas_settings (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS challenges (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    nome         TEXT NOT NULL,
    meta         INTEGER NOT NULL,
    progresso    INTEGER NOT NULL DEFAULT 0,
    concluida_em TEXT,
    created_at   TEXT NOT NULL
);
"""


class Database:
    """Acesso async ao SQLite. Uma conexao, uso serializado."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    async def abrir(self) -> None:
        if self.caminho.parent and str(self.caminho.parent) not in ("", "."):
            self.caminho.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.caminho)
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

        logger.info("Banco aberto em %s", self.caminho)

    async def fechar(self) -> None:
        if self._conn is not None:
            await self._conn.commit()
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("O banco nao foi aberto. Chame `abrir()` antes.")
        return self._conn

    async def tabelas(self) -> list[str]:
        async with self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cursor:
            linhas = await cursor.fetchall()
        return [linha["name"] for linha in linhas]

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------

    async def salvar_pixel(
        self,
        x: int,
        y: int,
        color: str,
        owner_id: str,
        efeito: str | None = None,
        painted_at: str | None = None,
    ) -> None:
        """Grava a linha ATUAL da celula. Uma linha por coordenada."""
        await self.conn.execute(
            """
            INSERT INTO pixels (x, y, color, owner_id, painted_at, effect)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(x, y) DO UPDATE SET
                color = excluded.color,
                owner_id = excluded.owner_id,
                painted_at = excluded.painted_at,
                effect = excluded.effect
            """,
            (x, y, color, owner_id, painted_at or agora_iso(), efeito),
        )
        await self.conn.commit()

    async def registrar_historico(
        self,
        x: int,
        y: int,
        color: str,
        owner_id: str,
        efeito: str | None = None,
        painted_at: str | None = None,
    ) -> None:
        """Acrescenta uma linha ao historico. Nada aqui apaga, nunca."""
        await self.conn.execute(
            """
            INSERT INTO pixel_history (x, y, color, owner_id, painted_at, effect)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (x, y, color, owner_id, painted_at or agora_iso(), efeito),
        )
        await self.conn.commit()

    async def carregar_canvas(self) -> list[Celula]:
        async with self.conn.execute(
            "SELECT x, y, color, owner_id, painted_at, effect FROM pixels"
        ) as cursor:
            linhas = await cursor.fetchall()

        return [
            Celula(
                x=linha["x"],
                y=linha["y"],
                color=linha["color"],
                owner_id=linha["owner_id"],
                painted_at=linha["painted_at"],
                effect=linha["effect"],
            )
            for linha in linhas
        ]

    async def historico_pixel(self, x: int, y: int, limite: int = 20) -> list[dict]:
        """Do mais novo para o mais antigo."""
        async with self.conn.execute(
            """
            SELECT x, y, color, owner_id, painted_at, effect
            FROM pixel_history
            WHERE x = ? AND y = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (x, y, max(0, limite)),
        ) as cursor:
            linhas = await cursor.fetchall()

        return [dict(linha) for linha in linhas]

    async def apagar_pixel(self, x: int, y: int) -> None:
        """Remove a celula do mapa atual. O historico permanece."""
        await self.conn.execute("DELETE FROM pixels WHERE x = ? AND y = ?", (x, y))
        await self.conn.commit()

    async def limpar_canvas(self) -> int:
        """Esvazia o mapa inteiro. O historico e o ranking permanecem.

        O canvas e a UNICA coisa que sobrevive a um reinicio do servidor. Se
        o LIMPAR do painel so limpasse a memoria, o desenho voltaria inteiro
        no proximo boot — e o streamer so descobriria isso com a LIVE ja no
        ar, olhando um quadro que ele tinha certeza de ter apagado.

        Devolve quantas celulas sairam, para o painel poder dizer.
        """
        cursor = await self.conn.execute("DELETE FROM pixels")
        await self.conn.commit()
        return max(0, int(cursor.rowcount or 0))

    # ------------------------------------------------------------------
    # Usuarios
    # ------------------------------------------------------------------

    async def upsert_usuario(
        self,
        handle: str,
        display_name: str | None = None,
        color: str | None = None,
        effect: str | None = None,
    ) -> None:
        """Cria ou atualiza. Campo nao informado NAO apaga o que ja existia.

        Sem isso, um comentario sem cor definida apagaria a cor que a pessoa
        escolheu ontem.
        """
        agora = agora_iso()
        await self.conn.execute(
            """
            INSERT INTO users (handle, display_name, color, effect, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET
                display_name = COALESCE(excluded.display_name, users.display_name),
                color        = COALESCE(excluded.color, users.color),
                effect       = COALESCE(excluded.effect, users.effect),
                last_seen    = excluded.last_seen
            """,
            (handle, display_name, color, effect, agora, agora),
        )
        await self.conn.commit()

    async def usuario(self, handle: str) -> dict | None:
        async with self.conn.execute(
            "SELECT * FROM users WHERE handle = ?", (handle,)
        ) as cursor:
            linha = await cursor.fetchone()
        return dict(linha) if linha is not None else None

    async def contar_usuarios(self) -> int:
        async with self.conn.execute("SELECT COUNT(*) AS n FROM users") as cursor:
            linha = await cursor.fetchone()
        return int(linha["n"])

    async def contabilizar_pintura(
        self, handle: str, pixels: int, sobrescrita: bool, xp: int = 0
    ) -> None:
        """Soma os contadores de quem pintou."""
        agora = agora_iso()
        await self.conn.execute(
            """
            INSERT INTO users (handle, first_seen, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (handle, agora, agora),
        )
        await self.conn.execute(
            """
            UPDATE users
               SET pixels_painted      = pixels_painted + ?,
                   pixels_overwritten  = pixels_overwritten + ?,
                   xp                  = xp + ?,
                   last_seen           = ?
             WHERE handle = ?
            """,
            (pixels, 1 if sobrescrita else 0, xp, agora, handle),
        )
        await self.conn.commit()

    async def registrar_perda(self, handle: str) -> None:
        """Alguem pintou por cima deste usuario. A perda e registrada.

        A arte pode ser disputada; a historia de quem pintou nao e apagada.
        """
        agora = agora_iso()
        await self.conn.execute(
            """
            INSERT INTO users (handle, first_seen, last_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (handle, agora, agora),
        )
        await self.conn.execute(
            "UPDATE users SET pixels_lost = pixels_lost + 1 WHERE handle = ?", (handle,)
        )
        await self.conn.commit()

    async def registrar_presente(
        self,
        handle: str,
        gift_name: str,
        gift_id: str | None,
        quantity: int,
        pixel_reward: int,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO gifts (handle, gift_name, gift_id, quantity, pixel_reward, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (handle, gift_name, gift_id, quantity, pixel_reward, agora_iso()),
        )
        await self.conn.execute(
            "UPDATE users SET gifts_received = gifts_received + 1 WHERE handle = ?",
            (handle,),
        )
        await self.conn.commit()

    async def registrar_acao(
        self,
        handle: str,
        x: int | None,
        y: int | None,
        color: str | None,
        cost: int,
        overwrite: bool,
        result: str,
        reason: str | None = None,
    ) -> None:
        """Log de TODA tentativa de pintura, inclusive as recusadas.

        Serve para responder "por que meu pixel nao apareceu?" sem adivinhar.
        """
        await self.conn.execute(
            """
            INSERT INTO paint_actions
                (handle, x, y, color, cost, overwrite, result, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                handle,
                x,
                y,
                color,
                cost,
                1 if overwrite else 0,
                result,
                reason,
                agora_iso(),
            ),
        )
        await self.conn.commit()

    async def top_pintores(self, limite: int = 5) -> list[dict]:
        """Ranking duravel. Lido no boot para aquecer o ranking em memoria."""
        async with self.conn.execute(
            """
            SELECT handle, display_name, color, xp, level,
                   pixels_painted, pixels_overwritten, pixels_lost
              FROM users
             WHERE pixels_painted > 0
             ORDER BY pixels_painted DESC, first_seen ASC
             LIMIT ?
            """,
            (max(0, limite),),
        ) as cursor:
            linhas = await cursor.fetchall()
        return [dict(linha) for linha in linhas]

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    async def salvar_settings(self, dados: dict[str, Any]) -> None:
        """Grava chave a chave: o que nao for informado permanece."""
        await self.conn.executemany(
            """
            INSERT INTO canvas_settings (chave, valor)
            VALUES (?, ?)
            ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor
            """,
            [(chave, json.dumps(valor)) for chave, valor in dados.items()],
        )
        await self.conn.commit()

    async def carregar_settings(self) -> dict[str, Any]:
        async with self.conn.execute("SELECT chave, valor FROM canvas_settings") as cursor:
            linhas = await cursor.fetchall()

        saida: dict[str, Any] = {}
        for linha in linhas:
            try:
                saida[linha["chave"]] = json.loads(linha["valor"])
            except json.JSONDecodeError:
                logger.warning("Setting ilegivel ignorado: %s", linha["chave"])
        return saida

    async def registrar_evento(
        self, chave: str, nome: str, payload: dict | None = None
    ) -> int:
        cursor = await self.conn.execute(
            """
            INSERT INTO events (chave, nome, started_at, payload)
            VALUES (?, ?, ?, ?)
            """,
            (chave, nome, agora_iso(), json.dumps(payload) if payload else None),
        )
        await self.conn.commit()
        return int(cursor.lastrowid or 0)

    async def encerrar_evento(self, evento_id: int) -> None:
        await self.conn.execute(
            "UPDATE events SET ended_at = ? WHERE id = ?", (agora_iso(), evento_id)
        )
        await self.conn.commit()

    async def registrar_gifts_em_lote(self, linhas: Iterable[tuple]) -> None:
        """Insere varios presentes numa transacao so."""
        await self.conn.executemany(
            """
            INSERT INTO gifts (handle, gift_name, gift_id, quantity, pixel_reward, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            list(linhas),
        )
        await self.conn.commit()
