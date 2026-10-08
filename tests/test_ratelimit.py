"""Anti-spam em camadas.

Sem isso, uma pessoa segurando a tecla de comentario derruba a LIVE. O relogio
e injetado: nenhum teste dorme.
"""

from core.ratelimit import RateLimiter


class Relogio:
    """Relogio falso. Avanca so quando o teste manda."""

    def __init__(self):
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


def test_regra_com_cooldown_bloqueia_dentro_da_janela():
    relogio = Relogio()
    rl = RateLimiter(now_fn=relogio)

    assert rl.allow_rule("pintar", cooldown=2.0, actor="joao", per_user_cooldown=0) is True
    assert rl.allow_rule("pintar", cooldown=2.0, actor="maria", per_user_cooldown=0) is False


def test_regra_libera_depois_do_cooldown():
    relogio = Relogio()
    rl = RateLimiter(now_fn=relogio)

    rl.allow_rule("pintar", cooldown=2.0, actor="joao", per_user_cooldown=0)
    relogio.avancar(2.1)

    assert rl.allow_rule("pintar", cooldown=2.0, actor="maria", per_user_cooldown=0) is True


def test_cooldown_por_usuario_bloqueia_o_mesmo_autor():
    relogio = Relogio()
    rl = RateLimiter(now_fn=relogio)

    assert rl.allow_rule("pintar", cooldown=0, actor="joao", per_user_cooldown=2.0) is True
    assert rl.allow_rule("pintar", cooldown=0, actor="joao", per_user_cooldown=2.0) is False


def test_cooldown_por_usuario_nao_afeta_outro_autor():
    relogio = Relogio()
    rl = RateLimiter(now_fn=relogio)

    rl.allow_rule("pintar", cooldown=0, actor="joao", per_user_cooldown=2.0)

    assert rl.allow_rule("pintar", cooldown=0, actor="maria", per_user_cooldown=2.0) is True


def test_ator_sem_nome_nao_e_punido_nem_pune_outros():
    """O TikTok manda likes sem `user` depois de ~10-20 curtidas do mesmo
    usuario. Sem identificacao, o cooldown por usuario nao se aplica — senao
    um unico anonimo silenciaria a sala inteira."""
    relogio = Relogio()
    rl = RateLimiter(now_fn=relogio)

    assert rl.allow_rule("curtir", cooldown=0, actor="", per_user_cooldown=5.0) is True
    assert rl.allow_rule("curtir", cooldown=0, actor="", per_user_cooldown=5.0) is True
    assert rl.allow_rule("curtir", cooldown=0, actor="", per_user_cooldown=5.0) is True


def test_acao_sem_orcamento_configurado_sempre_passa():
    rl = RateLimiter(action_budget={})

    for _ in range(100):
        assert rl.allow_action("qualquer") is True


def test_orcamento_global_limita_a_janela():
    relogio = Relogio()
    rl = RateLimiter(action_budget={"pintar": 3.0}, now_fn=relogio)

    assert rl.allow_action("pintar") is True
    assert rl.allow_action("pintar") is True
    assert rl.allow_action("pintar") is True
    assert rl.allow_action("pintar") is False


def test_orcamento_volta_depois_da_janela_de_um_segundo():
    relogio = Relogio()
    rl = RateLimiter(action_budget={"pintar": 2.0}, now_fn=relogio)

    rl.allow_action("pintar")
    rl.allow_action("pintar")
    assert rl.allow_action("pintar") is False

    relogio.avancar(1.01)

    assert rl.allow_action("pintar") is True


def test_orcamentos_de_acoes_diferentes_nao_se_misturam():
    relogio = Relogio()
    rl = RateLimiter(action_budget={"pintar": 0.5}, now_fn=relogio)

    assert rl.allow_action("pintar") is True
    assert rl.allow_action("outra") is True
