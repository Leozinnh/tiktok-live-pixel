"""PIXEL WORLD — o ponto de entrada.

    python main.py --test            # ensaia tudo sem LIVE
    python main.py                   # conecta na LIVE de verdade
    python main.py --burst 2000      # mede o teto do quadro

Este arquivo so Faz a coisa certa na ordem certa: le a config, monta o estado,
sobe o servidor. Nada de regra de jogo mora aqui — se uma linha deste arquivo
precisasse de teste, ela estaria no lugar errado.

O `--test` e o modo mais importante do projeto. Ele troca a fonte de eventos
pelo simulador e apaga a exigencia do `@usuario`, o que deixa ensaiar o jogo
inteiro — pintura, fila, ranking, eventos automaticos — sem estar ao vivo e
sem gastar um presente de verdade.
"""

import argparse
import asyncio
import logging
import sys
import webbrowser
from pathlib import Path

import uvicorn

from backend.app import criar_app
from backend.estado import EstadoJogo
from core.config import ConfigError, carregar

RAIZ = Path(__file__).resolve().parent
CONFIG_PADRAO = RAIZ / "config.json"

logger = logging.getLogger("pixelworld")


def _preparar_saida() -> None:
    """Garante que o console aguente os emojis do banner.

    O terminal do Windows abre em cp1252, e um `print("🎨")` ali levanta
    `UnicodeEncodeError` — o programa morreria na PRIMEIRA linha por causa de
    decoracao. `errors="replace"` degrada o emoji para "?" em vez de derrubar.
    """
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def _configurar_log(cfg: dict) -> None:
    pasta = RAIZ / str(cfg.get("app", {}).get("log_dir") or "logs")
    pasta.mkdir(parents=True, exist_ok=True)

    formato = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

    # Log em arquivo e o que sobra quando a LIVE da errado as 23h e nao ha
    # mais console para ler. O console fica em INFO, o arquivo em DEBUG.
    arquivo = logging.FileHandler(pasta / "pixelworld.log", encoding="utf-8")
    arquivo.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)

    logging.basicConfig(
        level=logging.DEBUG,
        format=formato,
        handlers=[console, arquivo],
        force=True,
    )

    # O uvicorn fala demais em DEBUG e afoga o log do jogo.
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def _argumentos(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pixelworld",
        description="PIXEL WORLD — pixel art coletiva para TikTok LIVE.",
    )
    parser.add_argument(
        "--config",
        default=str(CONFIG_PADRAO),
        help="caminho do config.json (padrao: %(default)s)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="MODO TESTE: simulador no lugar da LIVE, sem exigir @usuario",
    )
    parser.add_argument(
        "--porta",
        type=int,
        default=None,
        help="sobrepoe server.port do config",
    )
    parser.add_argument(
        "--burst",
        type=int,
        default=0,
        metavar="N",
        help="enfileira N eventos falsos na largada (so faz sentido com --test)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="nao abre o navegador",
    )
    return parser.parse_args(argv)


def _banner(endereco: str, modo_teste: bool, canvas_cfg: dict) -> None:
    cols = int(canvas_cfg.get("cols") or 0)
    rows = int(canvas_cfg.get("rows") or 0)

    modo = "MODO TESTE — nada disto esta no ar" if modo_teste else "AO VIVO"

    print()
    print("  ██  PIXEL WORLD")
    print(f"  {modo}")
    print()
    print(f"  Tela (OBS, 1080x1920)   {endereco}/")
    print(f"  Painel de controle      {endereco}/control")
    print(f"  Canvas                  {cols} x {rows} = {cols * rows} pixels")
    print()
    if modo_teste:
        print("  No painel: simule uma rosa e comente a coordenada (ex: H5).")
    else:
        print("  No OBS: adicione uma Fonte de Navegador com a URL da tela,")
        print("  largura 1080, altura 1920, e marque 'Desligar o audio'.")
    print()


async def _servir(app, host: str, porta: int) -> None:
    servidor = uvicorn.Server(
        uvicorn.Config(
            app,
            host=host,
            port=porta,
            # A tela usa `ws:`; sem `ws_max_size` padrao o hub ja trabalha bem,
            # mas o ping de 20s do cliente precisa que o timeout seja maior.
            ws_ping_interval=25,
            ws_ping_timeout=25,
            log_config=None,
            access_log=False,
        )
    )
    await servidor.serve()


def principal(argv=None) -> int:
    _preparar_saida()
    args = _argumentos(argv)

    try:
        cfg = carregar(args.config, exigir_username=not args.test)
    except ConfigError as erro:
        # Configuracao errada NAO sobe. Um jogo que sobe torto so mostra o
        # problema no ar, com a audiencia olhando.
        print(f"\n  ERRO DE CONFIGURACAO\n\n  {erro}\n", file=sys.stderr)
        return 2

    if args.porta:
        cfg.setdefault("server", {})["port"] = int(args.porta)

    _configurar_log(cfg)

    host = str(cfg.get("server", {}).get("host") or "127.0.0.1")
    porta = int(cfg.get("server", {}).get("port") or 8000)
    db_path = RAIZ / str(cfg.get("app", {}).get("db_path") or "pixelworld.db")

    estado = EstadoJogo(cfg, db_path=db_path, modo_teste=args.test)

    if args.burst:
        if not args.test:
            print(
                "\n  --burst so funciona com --test: nao da para inventar "
                "evento numa LIVE de verdade.\n",
                file=sys.stderr,
            )
            return 2

        # A rajada entra na fila ANTES do servidor subir. O laco do jogo so
        # comeca a drenar quando o lifespan roda, entao o primeiro quadro ja
        # encontra tudo esperando — que e exatamente a carga que se quer medir.
        quantos = max(0, min(5000, args.burst))
        eventos = estado.fonte.rajada(quantos)
        logger.info("Rajada de largada: %d eventos enfileirados", len(eventos))

    app = criar_app(estado)
    endereco = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{porta}"

    _banner(endereco, args.test, cfg.get("canvas", {}))

    if not args.headless:
        # O streamer abre o painel quase sempre; a tela ele abre no OBS.
        webbrowser.open(f"{endereco}/control")

    try:
        asyncio.run(_servir(app, host, porta))
    except KeyboardInterrupt:
        print("\n  Ate a proxima LIVE.\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
