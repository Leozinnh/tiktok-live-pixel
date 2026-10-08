"""O ranking, em memoria.

O ranking aparece na tela a cada pintura. Consultar o banco toda vez seria uma
ida ao disco por pixel pintado, num jogo onde a graca e a resposta instantanea.
Entao o banco continua sendo a verdade, mas so e lido UMA vez, no boot, para
aquecer este objeto — depois disso o ranking vive na memoria e o disco nunca
aparece no caminho quente.

Ele guarda todo mundo, nao so os cinco da tela. `/rank` precisa responder a
posicao de quem esta em 40o lugar, e essa e justamente a pessoa que mais quer
saber.
"""

from dataclasses import dataclass, field

from game.colors import COR_PADRAO, cor_automatica

# Sentinela para distinguir "nao mexe no efeito" de "apaga o efeito".
# Escolher /cor verde tem que APAGAR o fogo de quem era fogo; ja um comentario
# qualquer nao pode tirar o fogo de ninguem. `None` sozinho nao conta essa
# diferenca.
MANTER = object()


def normalizar(handle: str) -> str:
    """'@Joao ', 'joao' e 'JOAO' sao a mesma pessoa no ranking."""
    return (handle or "").strip().lstrip("@").lower()


@dataclass
class EntradaRanking:
    """A ficha de uma pessoa no ranking."""

    handle: str
    nome: str = ""
    cor: str = ""
    efeito: str | None = None
    pixels: int = 0
    sobrescritos: int = 0
    xp: int = 0
    cores: set[str] = field(default_factory=set)
    ordem: int = 0

    @property
    def nivel(self) -> int:
        from game.xp import xp_para_nivel

        return xp_para_nivel(self.xp)

    @property
    def titulo(self) -> str:
        from game.xp import titulo_de

        return titulo_de(self.nivel)

    @property
    def cores_usadas(self) -> int:
        return len(self.cores)

    def para_dict(self) -> dict:
        """Forma de fio, com os nomes que o spec §12 define.

        Os nomes internos sao nossos e em portugues; esta e a fronteira onde
        eles viram o contrato que a tela le. Um contrato que nao casa com o
        proprio spec e pior que um idioma misto — quem for ler o spec e o
        codigo lado a lado precisa encontrar as mesmas palavras.

        `user` leva o arroba porque e assim que `pixel_painted` ja manda, e
        `colors` sai como numero: a tela nao quer a lista de cores.
        """
        return {
            "user": f"@{self.handle}",
            "handle": self.handle,
            "name": self.nome or self.handle,
            "color": self.cor or COR_PADRAO,
            "effect": self.efeito,
            "pixels": self.pixels,
            "overwritten": self.sobrescritos,
            "colors": self.cores_usadas,
            "xp": self.xp,
            "level": self.nivel,
            "title": self.titulo,
        }


class Ranking:
    """Quem pintou mais, em memoria."""

    def __init__(self, paleta: list[str] | None = None, tamanho: int = 5):
        self.paleta = list(paleta or [])
        self.tamanho = tamanho
        self._entradas: dict[str, EntradaRanking] = {}
        self._proximo = 0

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def registrar(
        self,
        handle: str,
        *,
        nome: str | None = None,
        cor: str | None = None,
        efeito=MANTER,
        pixels: int = 0,
        sobrescritos: int = 0,
        xp: int = 0,
        cor_pintada: str | None = None,
    ) -> EntradaRanking:
        """Soma o que aconteceu a ficha de quem fez.

        Campo nao informado NAO apaga o que ja estava la: um comentario sem
        nome nao pode apagar o nome que a pessoa usa.
        """
        chave = normalizar(handle)
        entrada = self._entradas.get(chave)

        if entrada is None:
            entrada = EntradaRanking(handle=chave, ordem=self._proximo)
            self._proximo += 1
            self._entradas[chave] = entrada

        if nome:
            entrada.nome = nome

        if cor:
            entrada.cor = cor
        elif not entrada.cor:
            entrada.cor = cor_automatica(chave, self.paleta)

        if efeito is not MANTER:
            entrada.efeito = efeito

        entrada.pixels += pixels
        entrada.sobrescritos += sobrescritos
        entrada.xp += xp

        if cor_pintada:
            entrada.cores.add(cor_pintada)

        return entrada

    def carregar(self, linhas: list[dict]) -> None:
        """Substitui o ranking pelas linhas do banco. Usado uma vez, no boot."""
        self._entradas.clear()
        self._proximo = 0

        for linha in linhas:
            handle = linha.get("handle")
            if not handle:
                continue

            chave = normalizar(handle)
            entrada = EntradaRanking(
                handle=chave,
                nome=linha.get("display_name") or "",
                cor=linha.get("color") or cor_automatica(chave, self.paleta),
                efeito=linha.get("effect"),
                pixels=int(linha.get("pixels_painted") or 0),
                sobrescritos=int(linha.get("pixels_overwritten") or 0),
                xp=int(linha.get("xp") or 0),
                ordem=self._proximo,
            )
            self._proximo += 1
            self._entradas[chave] = entrada

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def entrada(self, handle: str) -> EntradaRanking | None:
        return self._entradas.get(normalizar(handle))

    def ordenadas(self) -> list[EntradaRanking]:
        """Do maior para o menor. Empate desempata por quem chegou antes."""
        return sorted(self._entradas.values(), key=lambda e: (-e.pixels, e.ordem))

    def top(self, quantos: int | None = None) -> list[EntradaRanking]:
        limite = self.tamanho if quantos is None else quantos
        return self.ordenadas()[: max(0, limite)]

    def top_para_dict(self, quantos: int | None = None) -> list[dict]:
        """O que o WebSocket manda. A posicao vai junto porque a tela mostra."""
        saida = []
        for posicao, entrada in enumerate(self.top(quantos), start=1):
            item = entrada.para_dict()
            item["position"] = posicao
            saida.append(item)
        return saida

    def posicao(self, handle: str) -> int:
        """Posicao 1-based, ou 0 para quem nao esta no ranking."""
        chave = normalizar(handle)
        for posicao, entrada in enumerate(self.ordenadas(), start=1):
            if entrada.handle == chave:
                return posicao
        return 0

    def total(self) -> int:
        return len(self._entradas)
