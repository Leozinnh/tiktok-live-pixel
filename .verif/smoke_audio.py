"""Prova o motor de audio de ponta a ponta, sem o jogo no meio.

Sorteia uma frase do jogo, gera de verdade com o edge-tts, toca pelo MCI do
Windows (o mesmo caminho que o Narrador usa no ar) e apaga — cronometrando
cada passo. O
cronometro e o que prova que o audio tocou ATE O FIM: abrir sem erro nao
prova nada, mas um "tocou em 3.x s" com a mesma ordem de grandeza do audio
so acontece quando o MCI chega ao fim da reproducao.

Uso:  python .verif/smoke_audio.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.narrador import Narrador  # noqa: E402

narrador = Narrador({"tts": {"active": True}})
fala = narrador.texto_do_presente("Fulano", 5, "Perfume")
print(f"frase sorteada: {fala!r}", flush=True)

print("gerando com o edge-tts...", flush=True)
inicio = time.monotonic()
caminho = narrador._gerar_edge(fala)
print(f"gerou em {time.monotonic() - inicio:.1f}s: {caminho}")
print(f"tamanho: {os.path.getsize(caminho)} bytes")

print("tocando (o som deve sair AGORA)...", flush=True)
inicio = time.monotonic()
narrador._tocar_mci(caminho)
print(f"tocou em {time.monotonic() - inicio:.1f}s")

narrador._apagar(caminho)
print("apagou:", "sim" if not os.path.exists(caminho) else "NAO")
