"""Quanto cada pessoa tem para gastar.

O inventario e o unico lugar do jogo onde a economia vive. Ele e deliberadamente
burro: guarda saldos, credita, debita, e nunca decide nada sozinho. Quem sabe
quanto custa uma pintura e o `ServicoPintura`.

Em memoria de proposito. O saldo e reconstruivel a partir dos presentes e das
pinturas registradas no banco; o que NAO e aceitavel e uma pintura esperar o
disco para saber se pode acontecer. Ao vivo, isso aparece como travamento.
"""

from collections import defaultdict


class Inventario:
    """Saldos de pixels por usuario."""

    def __init__(self) -> None:
        self._saldos: dict[str, int] = defaultdict(int)

    @staticmethod
    def _chave(usuario: str) -> str:
        """O handle e a identidade. '@Joao' e 'joao' sao a mesma pessoa."""
        return (usuario or "").strip().lstrip("@").lower()

    def adicionar(self, usuario: str, quantos: int = 1) -> int:
        """Credita pixels. Devolve o novo saldo."""
        if quantos < 0:
            raise ValueError("Nao da para creditar pixels negativos.")
        chave = self._chave(usuario)
        self._saldos[chave] += quantos
        return self._saldos[chave]

    def definir(self, usuario: str, quantos: int) -> int:
        """Crava o saldo no valor dito. Devolve o saldo resultante.

        Isto e o painel de teste, nao o jogo: o jogo so CREDITA (`adicionar`).
        A diferenca entre as duas aparece no segundo clique — definir duas
        vezes 50 deixa 50; adicionar duas vezes 50 deixaria 100, e o streamer
        nao teria como repetir um teste sem reiniciar.
        """
        if quantos < 0:
            raise ValueError("Nao da para cravar um saldo negativo.")
        chave = self._chave(usuario)
        self._saldos[chave] = quantos
        return quantos

    def saldo(self, usuario: str) -> int:
        return self._saldos.get(self._chave(usuario), 0)

    def gastar(self, usuario: str, quantos: int) -> bool:
        """Debita tudo ou nada. False significa que nada foi cobrado.

        Nunca deixa o saldo negativo e nunca cobra parcial: uma cobranca
        parcial por uma pintura que nao aconteceu e dinheiro sumindo do
        bolso de alguem ao vivo, na frente de todo mundo.
        """
        if quantos <= 0:
            return True

        chave = self._chave(usuario)
        if self._saldos.get(chave, 0) < quantos:
            return False

        self._saldos[chave] -= quantos
        return True

    def instantaneo(self) -> dict[str, int]:
        """Copia dos saldos, para o painel de teste e para o HUD."""
        return dict(self._saldos)
