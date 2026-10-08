"""Coordenadas do canvas: "H5", "h 5", "/pintar H5".

A coluna e uma letra (ou letras, quando o canvas cresce): A=0, Z=25, AA=26,
AB=27. E a mesma numeracao de planilha, e NAO `ord() - ord('A')`, senao "AA"
quebraria no dia em que o canvas passar de 26 colunas.

O parser e estrito de proposito. Ele aceita as variacoes que uma pessoa
realmente digita — espaco, minuscula, traco, barra, prefixo de comando — e
recusa todo o resto. Nao existe "quase certo": um pixel pintado no lugar
errado e pior que um erro visivel, porque a pessoa nao entende o que houve.

Estrito, porem, e a PEÇA, nunca o pedido. Um comentario com a lista de um
desenho inteiro ("A2, B2, C3") pinta tudo que da para ler e devolve o que nao
deu em `parse_pedido` — assim a tela denuncia o pedaco ilegivel em vez de
jogar fora 72 celulas boas por causa de duas coladas.
"""

import re
from dataclasses import dataclass

LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Prefixos que autorizam pintar. A barra sozinha tambem vale ("/H5").
PREFIXOS_PINTURA = frozenset({"", "p", "pixel", "pintar"})

_FORMATO = re.compile(r"^([A-Za-z]+)(\d+)$")
_ESPACOS = re.compile(r"\s+")

# A quebra de linha esta aqui porque a receita de um desenho tem varias linhas
# e o painel tem um campo de varias linhas: o texto chega com "\n" no meio.
_SEPARADORES = re.compile(r"[,;\r\n]+")


@dataclass(frozen=True, slots=True)
class Coordenada:
    """Uma celula resolvida do canvas."""

    x: int
    y: int
    rotulo: str


@dataclass(frozen=True, slots=True)
class Pedido:
    """O que um comentario pediu, com o que nao deu para ler separado.

    `invalidas` guarda as pecas cruas, do jeito que a pessoa escreveu. Elas
    existem para serem DENUNCIADAS na tela: quem colou 74 celulas e viu 72
    quadrados precisa saber qual pedaco nao entrou, senao vai procurar o
    defeito no lugar errado.
    """

    coordenadas: list[Coordenada]
    invalidas: list[str]


def letra_para_indice(letras: str) -> int:
    """Converte a parte alfabetica em indice de coluna, base 26 estilo planilha."""
    valor = 0
    for caractere in letras.upper():
        posicao = LETRAS.find(caractere)
        if posicao < 0:
            return -1
        valor = valor * 26 + (posicao + 1)
    return valor - 1


def indice_para_letra(x: int) -> str:
    """Inverso de `letra_para_indice`."""
    if x < 0:
        raise ValueError(f"Indice de coluna negativo: {x}")

    saida = ""
    resto = x + 1
    while resto > 0:
        resto, posicao = divmod(resto - 1, 26)
        saida = LETRAS[posicao] + saida
    return saida


def rotulo_de(x: int, y: int) -> str:
    """Rotulo legivel de uma celula: (7, 5) -> "H5"."""
    return f"{indice_para_letra(x)}{y}"


def indice_de(x: int, y: int, cols: int) -> int:
    """Posicao linear da celula. Depende da largura, entao nunca a assuma."""
    return y * cols + x


def _sem_separadores(texto: str) -> str | None:
    """Remove espacos e um unico traco. Dois tracos nao sao separador."""
    limpo = _ESPACOS.sub("", texto)
    if "-" in limpo:
        if limpo.count("-") != 1:
            return None
        limpo = limpo.replace("-", "")
    return limpo


def _parse_puro(texto: str, cols: int, rows: int) -> Coordenada | None:
    limpo = _sem_separadores(texto)
    if not limpo:
        return None

    casado = _FORMATO.match(limpo)
    if casado is None:
        return None

    x = letra_para_indice(casado.group(1))
    if x < 0 or x >= cols:
        return None

    y = int(casado.group(2))
    if y < 0 or y >= rows:
        return None

    return Coordenada(x=x, y=y, rotulo=rotulo_de(x, y))


def parse_coordenada(texto, cols: int, rows: int) -> Coordenada | None:
    """Traduz o que a audiencia digitou numa celula, ou None.

    Aceita:  H5  h5  H 5  h 5  H-5  /H5  /pixel H5  /pintar H5  /p H5
    Recusa:  A51  AA5 (em canvas de 26)  1H  ABC  H  ""  H5extra  H5 legal!
    """
    if not isinstance(texto, str):
        return None

    texto = texto.strip()
    if not texto:
        return None

    if not texto.startswith("/"):
        return _parse_puro(texto, cols, rows)

    # Comando: "/pintar H5". O prefixo autoriza, o argumento e que e a pintura.
    corpo = texto[1:].strip()
    direto = _parse_puro(corpo, cols, rows)
    if direto is not None:
        return direto

    partes = corpo.split()
    if len(partes) != 2:
        return None
    if partes[0].lower() not in PREFIXOS_PINTURA:
        return None
    return _parse_puro(partes[1], cols, rows)


def _pedacos(texto: str, cols: int, rows: int) -> list[str]:
    """As pecas do pedido, na ordem em que foram escritas.

    Dois niveis de separacao, e a ordem entre eles importa:

    1. Virgula, ponto-e-virgula e quebra de linha cortam sempre. Nenhuma
       coordenada valida contem qualquer um dos tres, entao nao ha risco.
    2. Espaco so corta DENTRO de um pedaco que nao fez sentido inteiro. "H 5" e
       UMA celula desde o primeiro dia — espaco entre a letra e o numero e o
       jeito mais comum de escrever coordenada. Se o espaco cortasse primeiro,
       "H 5" viraria as palavras "H" e "5", nenhuma delas uma coordenada, e
       quem escreve com espaco pararia de pintar de um dia para o outro.

    Virgula solta nao vira peca: e pontuacao, nao erro de quem escreveu.
    """
    if _SEPARADORES.search(texto):
        bruto = _SEPARADORES.split(texto)
    else:
        bruto = [texto]

    pecas: list[str] = []
    for pedaco in bruto:
        if not pedaco.strip():
            continue
        if _parse_puro(pedaco, cols, rows) is not None:
            pecas.append(pedaco)
            continue
        pecas.extend(pedaco.split())
    return pecas


def _ler_lista(texto: str, cols: int, rows: int) -> Pedido:
    """Uma coordenada, ou a lista inteira, com as pecas ilegiveis de fora."""
    unica = _parse_puro(texto, cols, rows)
    if unica is not None:
        return Pedido([unica], [])

    # A celula repetida conta UMA vez: "A2, A2" e um pedido, nao dois, e sem
    # isso colar a mesma lista duas vezes cobraria o dobro pelo mesmo pixel.
    vistas: dict[tuple[int, int], Coordenada] = {}
    invalidas: list[str] = []

    for peca in _pedacos(texto, cols, rows):
        coordenada = _parse_puro(peca, cols, rows)
        if coordenada is None:
            if peca not in invalidas:
                invalidas.append(peca)
            continue
        vistas.setdefault((coordenada.x, coordenada.y), coordenada)

    return Pedido(list(vistas.values()), invalidas)


def parse_pedido(texto, cols: int, rows: int) -> Pedido:
    """Traduz o comentario inteiro: o que da para pintar e o que nao deu.

    Aceita tudo que `parse_coordenada` aceita, mais a lista:

        "A2, B2, C3"      "A2,B2"      "A2; B2"      "A2 B2"
        "/pintar A2, B2"  "A2\nB2"     "/p A2 B2"

    Nunca adivinha: uma peca so entra se for coordenada exata. Mas tambem nao
    joga o desenho fora por causa de uma peca — `invalidas` viaja junto para a
    tela poder dizer QUAL pedaco nao entrou.

    Quem quer UMA celula continua chamando `parse_coordenada`, que segue
    estrito — `parse_pedido("H5 H6")` tem duas, `parse_coordenada` nao tem
    nenhuma.
    """
    if not isinstance(texto, str):
        return Pedido([], [])

    texto = texto.strip()
    if not texto:
        return Pedido([], [])

    if not texto.startswith("/"):
        return _ler_lista(texto, cols, rows)

    corpo = texto[1:].strip()

    # "/pintar A2, B2": a palavra de comando nao e coordenada, entao o prefixo
    # sai e o resto volta para o mesmo parser. `maxsplit=1` mantem a lista
    # inteira do lado direito, onde ela e lida.
    #
    # A ORDEM importa. Se o prefixo fosse tentado por ultimo, "/p A2" seria
    # lido primeiro como a celula "pA2" — e "PA" e uma coluna valida de verdade
    # (indice 416) num canvas largo o bastante. Nao existe canvas desses hoje, e
    # e exatamente por isso que a ambiguidade tem que morrer aqui: ela nao da
    # erro, da um pixel no lugar errado, que e o pior defeito possivel deste
    # arquivo.
    partes = corpo.split(maxsplit=1)
    if len(partes) == 2 and partes[0].lower() in PREFIXOS_PINTURA:
        return _ler_lista(partes[1], cols, rows)

    return _ler_lista(corpo, cols, rows)


def parse_coordenadas(texto, cols: int, rows: int) -> list[Coordenada]:
    """So as celulas do pedido. Vazia quando nada deu para ler."""
    return parse_pedido(texto, cols, rows).coordenadas


def parece_pintura(texto) -> bool:
    """Vale a pena responder "nao entendi" para isto?

    A LIVE tem gente conversando. Responder "coordenada invalida" para quem
    escreveu "oi" transforma o feed num painel de erros e ensina a audiencia a
    ignorar as mensagens do jogo. Mas quem TENTOU pintar e errou precisa saber,
    senao manda rosa, escreve a coordenada, nao acontece nada, e a conclusao
    razoavel e "o jogo quebrou".

    O criterio: tem um numero, ou comeca com barra. Isso separa "A51" e "1H" de
    "oi", "bom dia" e "hahaha".

    Ficam de fora, de proposito, os casos ambiguos — "H" sozinho e "ABC". Sao
    indistinguiveis de conversa, e o rodape da tela ja ensina o formato
    ("LETRA + NUMERO, EX: H5"). Errar calado nesses dois e melhor que acusar
    alguem de errar quando so estava conversando.
    """
    if not isinstance(texto, str):
        return False

    texto = texto.strip()
    if not texto:
        return False

    # Comando explicito sempre merece resposta: a pessoa quis falar com o jogo.
    if texto.startswith("/"):
        return True

    limpo = _sem_separadores(texto)
    if not limpo:
        return False

    return any(caractere.isdigit() for caractere in limpo)
