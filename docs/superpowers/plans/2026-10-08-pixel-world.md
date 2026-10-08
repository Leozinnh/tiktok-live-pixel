# PIXEL WORLD — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um canvas de pixel art coletiva 26×51 controlado pela audiência de uma LIVE do TikTok, renderizado em 1080×1920 para captura no OBS.

**Architecture:** Backend Python async (FastAPI + uvicorn) com o canvas em RAM como fonte de verdade e SQLite write-behind. O adapter TikTok roda numa thread própria e despeja numa fila thread-safe; o loop async drena, aplica as regras, e publica diffs no WebSocket. Frontend Canvas 2D sem build step, servido em `localhost`, consumido pelo OBS Browser Source.

**Tech Stack:** Python 3.14, FastAPI, uvicorn, aiosqlite, TikTokLive 7.0.1, pytest, HTML + Canvas 2D + ES modules.

**Spec:** `docs/superpowers/specs/2026-10-08-pixel-world-design.md`

## Global Constraints

- **Idioma:** comentários, docstrings, logs e mensagens de erro em **português (pt-BR)**, sem acentos em identificadores Python. O projeto antigo segue essa convenção e o plano a mantém.
- **Sem build step no frontend.** Nada de npm, bundler ou TypeScript. O streamer roda `python main.py` e abre o OBS.
- **O código nunca assume 26×51.** Toda validação de coordenada consulta a config.
- **O cliente WebSocket nunca pinta.** Pintura só nasce de evento TikTok ou do painel de controle.
- **Python 3.14** é o interpretador instalado. `TikTokLive` declara suporte a 3.10–3.13; instala e importa em 3.14 (verificado no projeto antigo).
- **Nunca instalar `pygame` junto de `pygame-ce`** — este projeto não usa nenhum dos dois.
- **`pixel_history` é append-only.** Nenhum código apaga linhas dessa tabela, nunca.

## Review Focus

Os cinco modos de falha que o spec implica mas nenhuma tarefa testa diretamente, e onde cada teste mora:

1. **Comentário que é coordenada válida mas o usuário não tem saldo** — precisa ser rejeitado **sem cobrar** e sem pintar (Task 5).
2. **Streak de presente** — os eventos intermediários não podem creditar pixels, senão 1 presente vira 40 (Task 8).
3. **Like sem autor** (`user=None`) — o TikTok para de mandar o autor depois de ~10-20 curtidas; creditar pixel a "desconhecido" polui o ranking (Task 7).
4. **Cliente WebSocket lento** — não pode travar o loop do jogo nem o broadcast pros outros (Task 9).
5. **Reiniciar o processo no meio de uma LIVE** — o canvas tem que voltar idêntico, incluindo o dono de cada pixel (Task 4).

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `config.json` | Toda a afinação: canvas, recompensas, eventos, limites |
| `core/config.py` | Carrega, valida e mescla com defaults. Recusa subir com erro legível |
| `core/events.py` | `LiveEvent` + `EventType` — formato interno, importado do projeto antigo |
| `core/event_queue.py` | Fila thread-safe que descarta o mais antigo sob enchente |
| `core/ratelimit.py` | Anti-spam em camadas |
| `core/logging_setup.py` | Log rotativo + journal JSONL de eventos da audiência |
| `game/coordinates.py` | Parser `H5` / `h 5` / `/pintar H5`. Rejeita o resto |
| `game/colors.py` | Paleta, cor automática por hash, cores especiais, parse de hex |
| `game/canvas.py` | `CanvasModel`: células, índice↔coordenada, expansível |
| `game/inventory.py` | Saldo de pixels por usuário |
| `game/painting.py` | Regras de pintura: custo, sobrescrita, resultado |
| `game/xp.py` | XP, níveis, títulos |
| `game/ranking.py` | Leaderboards |
| `game/rewards.py` | Presente/like/follow/share → quantidade de pixels |
| `game/events.py` | Scheduler de eventos automáticos da LIVE |
| `tiktok/adapter.py` | `TikTokLiveAdapter` — único arquivo que importa `TikTokLive` |
| `tiktok/parser.py` | Comentário → comando interno |
| `backend/database.py` | Schema SQLite + queries async |
| `backend/hub.py` | `WebSocketHub`: agrupamento em frames, broadcast |
| `backend/app.py` | FastAPI: rotas, WS, estáticos |
| `backend/control.py` | API do painel do streamer |
| `ui/index.html` + `ui/style.css` + `ui/js/*.js` | Tela 1080×1920 do OBS |
| `control/index.html` | Painel do streamer (não vai pro ar) |
| `main.py` | Entrypoint: monta tudo e sobe |
| `tests/*` | pytest |

**Reaproveitado do projeto antigo** (copiado, ajustado, com o comentário de origem preservado):
`core/events.py`, `core/event_queue.py`, `core/ratelimit.py` (na íntegra),
`adapters/tiktok_live.py` → `tiktok/adapter.py` (troca só os handlers),
`core/logging_setup.py`, e o padrão `publicar()` de `renderer_web/servidor.py`.

---

### Task 1: Fundação — config, eventos e fila

**Files:**
- Create: `config.json`, `core/__init__.py`, `core/config.py`, `core/events.py`, `core/event_queue.py`, `core/ratelimit.py`, `requirements.txt`, `pytest.ini`
- Test: `tests/test_config.py`, `tests/test_event_queue.py`, `tests/test_ratelimit.py`

**Interfaces:**
- Consumes: nada
- Produces: `config.carregar(caminho) -> dict` (levanta `ConfigError`); `EventType`; `LiveEvent`; `EventQueue.put/get_nowait/drain(limit)/size()/dropped/accepted`; `RateLimiter.allow_rule(rule_key, cooldown, actor, per_user_cooldown) -> bool`, `.allow_action(action) -> bool`

- [ ] **Step 1: Copiar `core/events.py`, `core/event_queue.py`, `core/ratelimit.py`** do projeto antigo sem alteração de comportamento. São agnósticos de jogo e já testados.
- [ ] **Step 2: Escrever `config.json`** com as seções `app`, `server`, `canvas`, `tiktok`, `rewards`, `events`, `limits`.
- [ ] **Step 3: Escrever `core/config.py`** com validação estrita. Regras: `canvas.cols` ∈ [1, 702] (A..ZZ), `canvas.rows` ≥ 1, toda `rewards.*.pixels` ≥ 0, `server.port` ∈ [1, 65535], `tiktok.username` não pode ser o placeholder `@SEU_USUARIO`.
- [ ] **Step 4: Testes** — config ausente levanta `ConfigError` com o caminho na mensagem; chave faltando é preenchida pelo default; valor inválido é recusado citando a chave; fila descarta o mais antigo e conta exato; rate limiter respeita as 3 camadas com clock injetado.
- [ ] **Step 5: Rodar** `python -m pytest tests/ -q` → tudo passa.
- [ ] **Step 6: Commit.** `feat: fundacao (config, eventos, fila, ratelimit)`

---

### Task 2: Parser de coordenadas

**Files:**
- Create: `game/__init__.py`, `game/coordinates.py`
- Test: `tests/test_coordinates.py`

**Interfaces:**
- Consumes: `config["canvas"]`
- Produces: `Coordenada` (dataclass `x:int, y:int, rotulo:str`); `parse_coordenada(texto, cols, rows) -> Coordenada | None`; `rotulo_de(x, y) -> str`; `indice_de(x, y, cols) -> int`

**Regras exatas:** aceita `H5`, `h5`, `H 5`, `h 5`, `H-5`, e os prefixos `/`, `/pixel`, `/pintar`, `/p`. Rejeita `A51` (linha fora), `AA5` quando cols<27, `1H`, `ABC`, `H` (sem linha), vazio, e `H5extra`.

- [ ] **Step 1: Teste que falha** — parametrizar os 5 aceitos e os 7 rejeitados acima, cada um com o motivo esperado.
- [ ] **Step 2: Rodar** → `ImportError: game.coordinates`.
- [ ] **Step 3: Implementar.** Converter letras para índice com `letra → valor` base-26 estilo planilha (`A`=0, `Z`=25, `AA`=26). **Não** usar `ord()` direto, senão `AA` quebra na expansão.
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: parser de coordenadas`

---

### Task 3: Cores

**Files:**
- Create: `game/colors.py`
- Test: `tests/test_colors.py`

**Interfaces:**
- Consumes: `config["canvas"]["paleta"]`
- Produces: `cor_automatica(username, paleta) -> str`; `parse_cor(texto, paleta, especiais) -> str | None`; `PALETA_PADRAO: dict[str, str]`; `ESPECIAIS: dict[str, dict]`

`cor_automatica` usa `zlib.crc32(username.lower().encode())` — **não** `hash()`, que é aleatorizado por `PYTHONHASHSEED` e daria cor diferente a cada restart.

- [ ] **Step 1: Teste que falha** — mesma entrada dá mesma cor em processos diferentes (subprocesso com `PYTHONHASHSEED` distinto); nomes diferentes tendem a cores diferentes; `/cor #FF0055` e `/cor vermelho` resolvem; `/cor roxo` num canvas cuja paleta não tem roxo é rejeitado.
- [ ] **Step 2: Rodar** → falha.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: sistema de cores`

---

### Task 4: Canvas e persistência

**Files:**
- Create: `game/canvas.py`, `backend/__init__.py`, `backend/database.py`
- Test: `tests/test_canvas.py`, `tests/test_database.py`

**Interfaces:**
- Consumes: `game.coordinates`
- Produces:
  - `Celula` (dataclass: `x, y, color, owner_id, painted_at, effect`, todos opcionais exceto x,y)
  - `CanvasModel(cols, rows)` com `.cols .rows .total`, `.celula(x,y) -> Celula | None`, `.pintar(x, y, color, owner_id, effect) -> Celula`, `.preenchidas() -> int`, `.para_dict() -> dict`, `.carregar(celulas) -> None`
  - `Database(caminho)` async: `.abrir()`, `.fechar()`, `.salvar_pixel(...)`, `.registrar_historico(...)`, `.carregar_canvas() -> list[Celula]`, `.upsert_usuario(...)`, `.top_pintores(n)`, `.historico_pixel(x, y, limite)`, `.salvar_settings(...)`

- [ ] **Step 1: Testes de canvas** — pintar célula nova retorna a célula; pintar fora do range levanta `IndexError`; `preenchidas()` conta só células com cor; `para_dict()` é JSON-serializável.
- [ ] **Step 2: Testes de banco** (tmp_path) — **round-trip completo**: pinta 3 pixels, fecha, reabre, `carregar_canvas()` devolve os mesmos donos e cores. Este é o teste do Review Focus #5.
- [ ] **Step 3: Rodar** → falha.
- [ ] **Step 4: Implementar.** Schema com as 10 tabelas do spec. `aiosqlite` com `PRAGMA journal_mode=WAL` e `synchronous=NORMAL` — escrita não pode bloquear leitura.
- [ ] **Step 5: Rodar** → passa.
- [ ] **Step 6: Commit.** `feat: canvas e persistencia sqlite`

---

### Task 5: Inventário e regras de pintura

**Files:**
- Create: `game/inventory.py`, `game/painting.py`
- Test: `tests/test_painting.py`

**Interfaces:**
- Consumes: `CanvasModel`, `Database`
- Produces: `Inventario` com `.adicionar(user, n)`, `.saldo(user) -> int`, `.gastar(user, n) -> bool`; `ResultadoPintura` (dataclass: `ok: bool, motivo: str, custo: int, celula: Celula | None`); `ServicoPintura(canvas, inventario, db)` com `.pintar(user, x, y, cor) -> ResultadoPintura`

**Motivos de recusa** (strings estáveis, o frontend decide o ícone por elas): `"saldo_insuficiente"`, `"coordenada_invalida"`, `"rate_limit"`.

- [ ] **Step 1: Testes que falham** — os três obrigatórios:
  - célula vazia custa 1
  - célula com dono custa 2
  - **saldo insuficiente não pinta E não cobra** (Review Focus #1): saldo 2, célula com dono → recusa, e `saldo` continua 2
  - pintar em si mesmo custa 1 (não é sobrescrita)
  - `pixels_lost` do dono anterior é incrementado
- [ ] **Step 2: Rodar** → falha.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: inventario e regras de pintura`

---

### Task 6: XP, níveis e ranking

**Files:**
- Create: `game/xp.py`, `game/ranking.py`
- Test: `tests/test_xp.py`, `tests/test_ranking.py`

**Interfaces:**
- Produces: `xp_para_nivel(n) -> int` (curva configurável); `nivel_para_xp(xp, cfg) -> int`; `titulo_de(nivel) -> str`; `Ranking` com `.registrar(user, pixels)`, `.top(n) -> list[dict]`, `.posicao(user) -> int`

Títulos: 1 Novato, 5 Pintor, 10 Artista, 20 Mestre, 30 Pixel Master, 50 Lenda. `titulo_de` devolve o **maior** título cujo nível ≤ o nível dado.

- [ ] **Step 1: Testes** — curva 100/125/150; nível 1 = 0 xp; nível 5 = "Pintor"; nível 49 = "Pixel Master"; nível 900 = "Lenda"; ranking ordena estável com empate (desempate por quem chegou antes).
- [ ] **Step 2: Rodar** → falha. **Step 3: Implementar.** **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: xp, niveis e ranking`

---

### Task 7: Recompensas e pipeline de eventos

**Files:**
- Create: `game/rewards.py`, `game/pipeline.py`
- Test: `tests/test_rewards.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `LiveEvent`, `EventQueue`, `ServicoPintura`, `Inventario`
- Produces: `pixels_do_evento(evento, cfg) -> int`; `Pipeline` com `.processar(evento) -> list[dict]` (devolve as mensagens WS a emitir)

`pixels_do_evento`: presente = `pixels_base × min(quantity, max_multiplier)`; like = 1 pixel a cada N curtidas; follow/share = valor fixo. Comentário = 0 (comentário só pinta, não credita).

- [ ] **Step 1: Testes** — like **sem autor** não credita pixel (Review Focus #3); presente com `quantity=10` credita 10× o base, mas `max_multiplier` corta; comentário com coordenada válida e saldo pinta; comentário com coordenada válida e **sem saldo** devolve recusa e não credita; evento SYSTEM é ignorado.
- [ ] **Step 2: Rodar** → falha. **Step 3: Implementar.** **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: recompensas e pipeline`

---

### Task 8: Adapter TikTok

**Files:**
- Create: `tiktok/__init__.py`, `tiktok/adapter.py`, `tiktok/base.py`, `tiktok/simulado.py`
- Test: `tests/test_tiktok_mapping.py`

**Interfaces:**
- Produces: `AdapterStatus`; `TikTokLiveAdapter(queue, config)`; `evento_de_comentario(obj) -> LiveEvent`; `evento_de_presente(obj) -> LiveEvent | None`; `evento_de_like(obj, total_anterior) -> LiveEvent | None`; `AdaptadorSimulado` com `.enviar(tipo, username, **campos)` para o painel de teste

Portar `adapters/tiktok_live.py` **preservando integralmente**: o retorno `None` em `streaking=True`, o descarte de `total` não-monotônico, a tolerância a `user=None`, o cliente novo por tentativa, o backoff com jitter, e `await client.disconnect()` no teardown (nunca `close()`).

- [ ] **Step 1: Portar os testes** de `tests/test_tiktok_mapping.py` com os fakes duck-typed.
- [ ] **Step 2: Teste do Review Focus #2** — alimentar 5 eventos de streak onde 4 têm `streaking=True` e o último tem `repeat_count=40`; afirmar que os 4 primeiros devolvem `None` e o último devolve `quantity=40` — ou seja, **exatamente 40 pixels creditados, não 200**.
- [ ] **Step 3: Implementar** portando o adapter.
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: adapter tiktok`

---

### Task 9: Hub WebSocket com agrupamento

**Files:**
- Create: `backend/hub.py`
- Test: `tests/test_hub.py`

**Interfaces:**
- Produces: `WebSocketHub(intervalo=0.05)` com `.publicar(msg: dict)` (não-bloqueante, lock-and-store), `.registrar(ws)` / `.desregistrar(ws)`, `.iniciar()` / `.parar()`, `.contar() -> int`

**Regra de agrupamento:** mensagens de pixel acumulam num lote e saem como uma única mensagem `{"type":"pixels","items":[...]}` a cada 50ms. Mensagens de estado (`ranking`, `stats`) substituem a anterior do mesmo tipo — só a última importa.

- [ ] **Step 1: Testes** — 1000 publicações em 50ms produzem **uma** chamada de envio (não 1000); `ranking` publicado 3× envia só o último; um cliente que levanta exceção no `send` é removido sem derrubar os outros (Review Focus #4); `publicar()` 10000× leva < 0.5s.
- [ ] **Step 2: Rodar** → falha. **Step 3: Implementar.** **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: hub websocket com agrupamento`

---

### Task 10: Servidor FastAPI

**Files:**
- Create: `backend/app.py`, `backend/control.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces: `criar_app(estado: EstadoJogo) -> FastAPI` com `GET /` (tela OBS), `GET /control` (painel), `WS /ws`, e a API de controle: `POST /api/simular`, `POST /api/evento`, `GET /api/estado`, `GET /api/pixel/{x}/{y}`, `DELETE /api/pixel/{x}/{y}`, `POST /api/inventario`, `POST /api/burst`

- [ ] **Step 1: Testes** (httpx `AsyncClient`) — `GET /` devolve 200 e o HTML; `GET /../config.json` devolve 404 (path traversal); o WS manda `hello` com o canvas ao conectar; `POST /api/simular` com comentário `H5` move o estado; rota de controle **não** é acessível pela página do OBS (CORS/rota separada).
- [ ] **Step 2: Rodar** → falha. **Step 3: Implementar** com `StaticFiles` para `ui/`.
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: servidor fastapi e api de controle`

---

### Task 11: Scheduler de eventos da LIVE

**Files:**
- Create: `game/events.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Consumes: `config["events"]`
- Produces: `SchedulerEventos(cfg, agora_fn)` com `.ativo() -> dict | None`, `.tick() -> list[dict]` (mensagens WS), `.forcar(chave) -> bool`, `.multiplicador_pixels() -> float`

- [ ] **Step 1: Testes com clock injetado** — o ciclo dispara na ordem do config; `HORA_DO_PIXEL` dá `multiplicador_pixels()==1.0` mas credita bônus; `PIXEL_TURBO` dá `2.0`; o evento termina exatamente em `duracao`; dois `tick()` no mesmo instante não disparam duas vezes; `forcar` de chave inexistente devolve `False`.
- [ ] **Step 2: Rodar** → falha. **Step 3: Implementar.** **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: scheduler de eventos da live`

---

### Task 12: Frontend — cliente WS e renderer

**Files:**
- Create: `ui/index.html`, `ui/style.css`, `ui/js/ws.js`, `ui/js/geometry.js`, `ui/js/renderer.js`
- Test: `ui/js/geometry.test.mjs` (rodado por `node --test`)

**Interfaces:**
- Produces: `conectar(url, aoMensagem, aoStatus)` com reconexão e backoff; `geometry.js` exporta `celulaParaTela(x, y, layout)` e `calcularLayout(cols, rows, largura, altura) -> {px, ox, oy, x, y}`; `Renderer` com `.aplicar(msg)`, `.desenhar(dt)`

**`geometry.js` é puro** (sem DOM, sem canvas) — é o que o torna testável no Node, mesmo truque do `camera.js` do projeto antigo.

- [ ] **Step 1: Testes Node** — `calcularLayout(26, 51, 1080, 900)` produz células quadradas (px inteiro), centralizado, e nunca estoura os limites; `celulaParaTela` é o inverso exato; o layout é **invariante** a 26×51 vs 50×100 (não assume nenhum dos dois).
- [ ] **Step 2: Rodar** `node --test ui/js/` → falha.
- [ ] **Step 3: Implementar** com `Math.floor` no tamanho da célula para pixels nítidos, e `imageSmoothingEnabled = false`.
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: cliente websocket e renderer do canvas`

---

### Task 13: Frontend — efeitos, HUD e layout

**Files:**
- Create: `ui/js/effects.js`, `ui/js/hud.js`, `ui/js/app.js`
- Modify: `ui/style.css`
- Test: verificação por screenshot headless

**Interfaces:**
- Consumes: `Renderer`, `geometry.js`
- Produces: `Efeitos` com `.animarPintura(x, y, cor)`, `.atualizar(dt)`, `.desenhar(ctx)` — pool fixo de 400 partículas; `HUD` com `.atualizar(msg)`, `.desenhar()` para feed, ranking, evento, progresso, inventário

- [ ] **Step 1: Implementar** as camadas na ordem do spec §14, com o dirty-flag: sem mensagem nova e sem animação ativa, não redesenha.
- [ ] **Step 2: Montar o layout 9:16** do spec §13. Somar as alturas: 120+140+900+320+260+100+80 = 1920.
- [ ] **Step 3: Verificar por screenshot** — Chrome headless com `--window-size=1080,1920 --screenshot`, carregando a página com um canvas pré-populado. Conferir que nada está cortado e que a legibilidade mínima de 28px está respeitada.
- [ ] **Step 4: Commit.** `feat: efeitos, hud e layout 9:16`

---

### Task 14: Painel de controle (test mode)

**Files:**
- Create: `control/index.html`, `control/control.js`, `control/control.css`

**Interfaces:**
- Consumes: a API de controle da Task 10

- [ ] **Step 1: Implementar** os controles do spec §16: simular comentário/presente(com quantidade)/like/follow/share por usuário arbitrário; forçar evento; resetar inventário; apagar pixel; ver histórico de pixel; botão **burst de 200 eventos**.
- [ ] **Step 2: Verificar manualmente** com o servidor rodando: cada botão produz o efeito esperado na tela do OBS.
- [ ] **Step 3: Commit.** `feat: painel de controle e test mode`

---

### Task 15: Entrypoint e documentação

**Files:**
- Create: `main.py`, `README.md`
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes: tudo
- Produces: `main()` com flags `--config`, `--test`, `--porta`, `--burst N`, `--headless`

- [ ] **Step 1: Testes** — `--test` não tenta conectar no TikTok; `--config` inexistente sai com código 2 e mensagem legível; `--burst 200` enfileira 200 eventos e não trava; o canvas é recarregado do banco no boot.
- [ ] **Step 2: Implementar** o boot em ordem: config → banco → canvas (carrega) → hub → app → scheduler → adapter → uvicorn.
- [ ] **Step 3: Escrever o README** com: instalação, o que é o jogo, como configurar `tiktok.username`, como apontar o OBS, como usar o test mode, e a limitação honesta de que o jogo só chega à audiência se o vídeo sair do PC.
- [ ] **Step 4: Rodar** → passa.
- [ ] **Step 5: Commit.** `feat: entrypoint e documentacao`

---

### Task 16: Verificação de aceite

**Files:**
- Modify: `README.md` (seção "o que foi verificado")
- Test: `tests/test_aceitacao.py`

- [ ] **Step 1: Teste de carga** — 2000 eventos simulados de uma vez: nenhum evento derruba o processo, o lote do hub sai em ≤ 50ms, e `publicar()` nunca bloqueia.
- [ ] **Step 2: Teste de persistência end-to-end** — sobe o app, pinta via API, derruba, sobe de novo, confere o canvas idêntico.
- [ ] **Step 3: Rodar a suíte completa** `python -m pytest tests/ -q` e o teste Node.
- [ ] **Step 4: Screenshot final** em 1080×1920 com canvas populado.
- [ ] **Step 5: Commit.** `test: verificacao de aceite`

---

## Self-Review

**Cobertura do spec:** §4 arquitetura → Tasks 1-15. §5 estrutura → idêntica. §6 dados → Task 4. §7 fluxo → Task 5. §8 parser → Task 2. §9 cores → Task 3. §10 progressão → Task 6. §11 eventos → Task 11. §12 protocolo → Tasks 9-10. §13 layout → Task 13. §14 efeitos → Task 13. §15 performance → Tasks 9, 16. §16 test mode → Tasks 8, 10, 14. §18 critérios → Task 16.

**Fora do escopo do spec §17** (modo imagem, regiões, conquistas, som) não têm tarefa — correto, são adiados por decisão.

**Consistência de tipos verificada:** `Celula` definida na Task 4 e usada nas Tasks 5, 7, 12. `ResultadoPintura` definido e consumido na Task 5 e devolvido pela Task 7. `LiveEvent` vem da Task 1 e alimenta 7, 8, 11. `cols`/`rows` fluem de `config["canvas"]` para 2, 3, 4, 12 — nenhum lugar assume 26×51.
