"""Progressao: XP vira nivel, nivel vira titulo.

A curva e linear nos degraus: o nivel N+1 custa `base + passo * (N - 1)`, e o
custo de alcancar um nivel e a soma de todos os degraus ate ele. Com os valores
do `config.json` (base 100, passo 25) isso da:

    nivel 2  ->    100 XP  (10 pixels virgens)
    nivel 5  ->    550 XP  "Pintor"
    nivel 10 ->  1.800 XP  "Artista"
    nivel 20 ->  6.175 XP  "Mestre"
    nivel 30 -> 13.050 XP  "Pixel Master"  (~um canvas inteiro)
    nivel 50 -> 34.300 XP  "Lenda"

O nivel 30 cair exatamente em cima de pintar o canvas todo nao e coincidencia:
e o trofeu de quem participou da obra completa.

Duas direcoes, uma verdade. `nivel_para_xp` e a conta exata; `xp_para_nivel` e
a inversa. As duas precisam concordar em TODA fronteira — se discordarem, o HUD
anuncia "faltam 0 XP" e o nivel nunca sobe. Por isso a inversa usa uma
estimativa por forma fechada seguida de correcao com a conta inteira: rapida
como uma formula, exata como um laco.
"""

import math

BASE_POR_NIVEL = 100
PASSO_POR_NIVEL = 25

# Os seis marcos do spec, em ordem. Entre dois marcos vale o de baixo.
TITULOS: tuple[tuple[int, str], ...] = (
    (1, "Novato"),
    (5, "Pintor"),
    (10, "Artista"),
    (20, "Mestre"),
    (30, "Pixel Master"),
    (50, "Lenda"),
)


def _acumulado(degraus: int, base: int, passo: int) -> int:
    """XP total para subir `degraus` niveis a partir do nivel 1.

    `degraus = nivel - 1`. E a soma da progressao aritmetica dos custos.
    """
    if degraus <= 0:
        return 0
    return base * degraus + passo * degraus * (degraus - 1) // 2


def nivel_para_xp(nivel: int, base: int = BASE_POR_NIVEL, passo: int = PASSO_POR_NIVEL) -> int:
    """Quanto XP acumulado e preciso para ESTAR no nivel informado."""
    return _acumulado(int(nivel) - 1, base, passo)


def xp_para_nivel(xp: int, base: int = BASE_POR_NIVEL, passo: int = PASSO_POR_NIVEL) -> int:
    """Em que nivel esta quem tem este XP."""
    if xp <= 0:
        return 1

    if passo <= 0:
        # Curva de degrau unico: a inversa e uma divisao.
        return int(xp) // base + 1

    # Inversa da quadratica: passo/2 * m^2 + (base - passo/2) * m - xp <= 0.
    a = base - passo / 2
    estimativa = int((-a + math.sqrt(a * a + 2 * passo * xp)) / passo)
    degraus = max(0, estimativa - 2)

    # A forma fechada sozinha erra por um ou dois em fronteiras exatas por
    # causa do ponto flutuante. A conta inteira decide.
    while _acumulado(degraus + 1, base, passo) <= xp:
        degraus += 1
    return degraus + 1


def titulo_de(nivel: int) -> str:
    """O nome que vai para a tela. Nunca vazio."""
    titulo = TITULOS[0][1]
    for marco, nome in TITULOS:
        if nivel >= marco:
            titulo = nome
        else:
            break
    return titulo


def progresso_nivel(
    xp: int, base: int = BASE_POR_NIVEL, passo: int = PASSO_POR_NIVEL
) -> dict:
    """Tudo o que a barra de progresso do HUD precisa, numa chamada so."""
    nivel = xp_para_nivel(xp, base, passo)
    inicio = nivel_para_xp(nivel, base, passo)
    fim = nivel_para_xp(nivel + 1, base, passo)
    faixa = fim - inicio

    fracao = 0.0 if faixa <= 0 else (xp - inicio) / faixa

    return {
        "xp": int(xp),
        "nivel": nivel,
        "titulo": titulo_de(nivel),
        "xp_no_nivel": max(0, int(xp) - inicio),
        "xp_do_nivel": faixa,
        "faltam": max(0, fim - int(xp)),
        "proximo_nivel": nivel + 1,
        "fracao": min(1.0, max(0.0, fracao)),
    }
