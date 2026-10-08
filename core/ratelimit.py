import time
from collections import defaultdict, deque
from typing import Callable

JANELA_ORCAMENTO = 1.0


class RateLimiter:
    """Controle de spam em camadas.

    Camada 1: cooldown da regra        - rajada repetida da mesma regra.
    Camada 2: cooldown por usuario     - um usuario monopolizando a tela.
    Camada 3: orcamento global por acao - muitos usuarios na mesma acao.

    Uma quarta camada (teto de pixels por evento) vive no pipeline, porque
    depende do estado do jogo, nao do tempo.

    O relogio e injetavel para que os testes nao durmam.
    """

    def __init__(
        self,
        action_budget: dict[str, float] | None = None,
        now_fn: Callable[[], float] = time.monotonic,
    ):
        self._now = now_fn
        self._budget = dict(action_budget or {})
        self._regra: dict[str, float] = {}
        self._usuario: dict[tuple[str, str], float] = {}
        self._janelas: dict[str, deque[float]] = defaultdict(deque)

    def allow_rule(
        self,
        rule_key: str,
        cooldown: float,
        actor: str,
        per_user_cooldown: float,
    ) -> bool:
        """Camadas 1 e 2. Retorna True se a regra pode disparar agora."""
        agora = self._now()

        if cooldown > 0:
            ultimo = self._regra.get(rule_key)
            if ultimo is not None and agora - ultimo < cooldown:
                return False

        # Um ator sem nome nao pode ser punido nem pode silenciar outros
        # atores sem nome: o TikTok manda likes sem `user` quando o usuario
        # ja curtiu demais. Sem identificacao, o cooldown por usuario nao
        # se aplica.
        ator = actor.strip()
        if per_user_cooldown > 0 and ator:
            chave = (rule_key, ator)
            ultimo = self._usuario.get(chave)
            if ultimo is not None and agora - ultimo < per_user_cooldown:
                return False
            self._usuario[chave] = agora

        if cooldown > 0:
            self._regra[rule_key] = agora
        return True

    def allow_action(self, action: str) -> bool:
        """Camada 3. Janela deslizante de 1s por acao."""
        limite = self._budget.get(action)
        if limite is None:
            return True

        agora = self._now()
        janela = self._janelas[action]

        while janela and agora - janela[0] >= JANELA_ORCAMENTO:
            janela.popleft()

        if len(janela) >= limite:
            return False

        janela.append(agora)
        return True
