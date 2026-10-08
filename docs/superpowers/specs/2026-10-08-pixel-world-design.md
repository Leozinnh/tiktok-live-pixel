# PIXEL WORLD — Spec de Design

**Data:** 2026-10-08
**Status:** Aprovado para implementação

---

## 1. Objetivo

Um quadro digital coletivo que pertence à audiência de uma LIVE do TikTok.

Não é um jogo que *reage* a presentes. É um canvas permanente onde cada pessoa
que interage deixa uma marca, e a comunidade — ao longo de horas ou dias —
constrói uma imagem que ninguém desenhou sozinho.

**Critério de sucesso:** alguém entra às 20h sem entender nada, pergunta "como eu
pinto um pixel?", manda uma rosa, escolhe uma coordenada — e volta às 23h para
ver o que a comunidade fez, reconhecendo a própria contribuição.

**O gancho:** "QUE PORRA É ESSA?" → "Como eu pinto?" → "Vou mandar uma rosa" →
"Qual coordenada eu escolho?" → "Vou voltar depois pra ver como está."

---

## 2. Decisões travadas

| Decisão | Escolha | Porquê |
|---|---|---|
| Base | Projeto novo em `tiktok_live_pixel`, reaproveitando do `tiktok_live_interactive_game` **apenas** a camada de conexão TikTok | Reescrever a conexão jogaria fora a parte que já funciona contra a LIVE real |
| Cor | Automática e estável por usuário (hash do nome → paleta). `/cor` troca e persiste | Ninguém precisa escolher nada para participar; quem quer, personaliza |
| Sobrescrita | Custa 2 pixels. Pixel virgem custa 1 | Disputa de terreno é possível, vandalismo em massa é caro |
| Visual | NEON / HUD futurista | Alto contraste para celular, bonito mesmo com o canvas vazio |
| Persistência | O canvas **nunca** reseta | A arte de dias atrás é o motivo de voltar |
| Stack | Backend Python, frontend Canvas 2D servido local | Python porque é o que a camada TikTok reaproveitável usa |

---

## 3. Stack

| Camada | Tecnologia | Porquê |
|---|---|---|
| Conexão TikTok | Biblioteca do projeto antigo | Já funciona contra LIVE real |
| Backend | Python 3.11+ / FastAPI / uvicorn | Async nativo, WebSocket de primeira classe, mesmo runtime da camada TikTok |
| Persistência | SQLite via `aiosqlite` | Zero-config, arquivo único, sobrevive a restart. Postgres é overkill para um app de streamer |
| Frontend | HTML + Canvas 2D + WebSocket | 1326 células é trivial para Canvas 2D. Sem build step: o streamer só abre o OBS |
| Transporte OBS | Browser Source em `localhost` | Formato 1080x1920 exato, sem screen capture |

**Sem build step.** Sem npm, sem bundler. O streamer instala Python, roda
`python main.py`, aponta o OBS para `http://localhost:8000`. Qualquer outra
coisa é atrito que impede o projeto de ser usado.

---

## 4. Arquitetura

```
TikTok LIVE
    │
    ▼
TikTokEventAdapter ──── reconexão automática
    │
    ├─ GiftEvent    ──▶ PixelReward ──▶ UserInventory (+N pixels)
    ├─ CommentEvent ──▶ CommandParser ──┐
    ├─ LikeEvent    ──▶ PixelReward     │
    ├─ FollowEvent  ──▶ PixelReward     │
    └─ ShareEvent   ──▶ PixelReward     │
                                        ▼
                              PaintingService
                        (valida, cobra, escreve)
                                        │
                          ┌─────────────┼─────────────┐
                          ▼             ▼             ▼
                      CanvasModel    Database    EventBus
                    (estado em RAM)  (SQLite)        │
                                                    ▼
                                              WebSocketHub
                                                    │
                          ┌─────────────────────────┼──────────────┐
                          ▼                         ▼              ▼
                   Tela OBS (9:16)         Painel do streamer   Reconexão
```

**Princípio central:** o `CanvasModel` vive em RAM e é a fonte de verdade para
renderização. O SQLite é write-behind: a pintura é aplicada em memória,
transmitida na hora, e persistida de forma assíncrona. Um disco lento nunca
trava a tela.

---

## 5. Estrutura de arquivos

```
tiktok_live_pixel/
├── main.py                    # entrypoint único
├── config.json                # toda a afinação num lugar só
├── requirements.txt
├── README.md
├── backend/
│   ├── app.py                 # FastAPI, rotas, montagem
│   ├── database.py            # schema + queries async
│   ├── models.py              # dataclasses internas
│   ├── hub.py                 # WebSocketHub (broadcast, backpressure)
│   ├── statistics.py          # agregados do canvas
│   └── control.py             # API do painel do streamer
├── game/
│   ├── coordinates.py         # parser "H5" / "h 5" / "/pintar H5"
│   ├── colors.py              # paleta, cores especiais, hash por usuário
│   ├── canvas.py              # CanvasModel, expansível
│   ├── inventory.py           # pixels disponíveis por usuário
│   ├── painting.py            # regras: custo, sobrescrita, validação
│   ├── xp.py                  # XP, níveis, títulos
│   ├── ranking.py             # leaderboards
│   ├── rewards.py             # presente → quantidade de pixels
│   ├── events.py              # eventos automáticos da LIVE
│   └── challenges.py          # metas coletivas
├── tiktok/
│   ├── adapter.py             # TikTokEventAdapter
│   ├── parser.py              # comentário → comando interno
│   └── reconnect.py           # supervisão da conexão
├── ui/
│   ├── index.html             # página do OBS (1080x1920)
│   ├── style.css
│   └── js/
│       ├── ws.js              # cliente WebSocket + reconexão
│       ├── renderer.js        # desenho do grid e dos pixels
│       ├── effects.js         # partículas, brilho, tinta
│       ├── hud.js             # ranking, feed, progresso, evento
│       └── app.js             # wiring
├── control/
│   └── index.html             # painel do streamer (test mode)
└── tests/
```

Cada arquivo tem um propósito único e é entendível sozinho. Nada de arquivo
gigante.

---

## 6. Modelo de dados

### Canvas

Coordenadas são **sempre validadas contra a configuração**, nunca contra
constantes no código.

- Colunas: `A`..`Z` (26) — configurável, suporta além de Z via `AA`, `AB`
- Linhas: `0`..`50` (51) — configurável
- Total: 1326 pixels
- Célula: `x` (índice), `y` (índice), `color`, `owner_id`, `painted_at`, `effect`

O código nunca assume 26×51. Expansão para 50×100 ou 100×100 é uma mudança de
`config.json` mais uma migração de schema — não uma reescrita.

### Tabelas SQLite

| Tabela | Conteúdo |
|---|---|
| `users` | id, username, display_name, color, xp, level, pixels_painted, pixels_overwritten, pixels_lost, gifts_received, first_seen, last_seen, streak_days |
| `pixels` | x, y, color, owner_id, painted_at, effect — a linha atual de cada célula |
| `pixel_history` | append-only: x, y, color, owner_id, painted_at — nunca apagado |
| `paint_actions` | log de toda tentativa: user_id, x, y, cost, result, reason, timestamp |
| `gifts` | user_id, gift_name, gift_id, count, pixel_reward, timestamp |
| `events` | tipo, início, fim, payload — eventos automáticos ocorridos |
| `achievements` | user_id, achievement_key, unlocked_at — tabela criada agora, *sistema* de conquistas completo fica para depois (ver §17) |
| `user_stats` | agregados por usuário derivados (evita COUNT em toda leitura) |
| `canvas_settings` | largura, altura, colunas, linhas, paleta ativa |
| `challenges` | meta, progresso, concluída_em |

`pixel_history` é append-only por design: o histórico é a memória do projeto e
o que permite "quem já pintou aqui?" muito depois.

---

## 7. Fluxo de pintura

```
Comentário "H5" do @joao
    │
    ▼
Parser normaliza (trim, maiúscula, remove barras e prefixos)
    │
    ├─ Inválido ──▶ ❌ toast "Coordenada inválida" (só no painel, não na LIVE)
    │
    ▼
Resolve coordenada → (x, y)
    │
    ▼
Verifica inventário de @joao
    ├─ 0 pixels ──▶ 🔒 toast "@joao, envie um presente para ganhar pixels"
    │
    ▼
Verifica custo: célula vazia = 1 | célula com dono = 2
    ├─ insuficiente ──▶ 🔒 "você precisa de 2 pixels"
    │
    ▼
Cobra do inventário → aplica no CanvasModel → grava em pixel_history
    │
    ▼
Broadcast WebSocket: pixel_painted + feed + ranking + stats
    │
    ▼
Animação: coordenada → brilho → partículas → tinta → cor → "@joao"
```

**Regra de sobrescrita:** o dono anterior **não** perde estatística — ele ganha
`pixels_lost` e o pixel continua contando no total histórico dele. A arte pode
ser disputada, a história não é apagada.

---

## 8. Parser de coordenadas

Formatos aceitos:

```
H5      h5      H 5      h 5      H-5
/H5     /pixel H5     /pintar H5     /p H5
```

Rejeitados com mensagem clara:

```
A51     → linha fora do intervalo (0–50)
AA5     → coluna fora do intervalo (A–Z, neste canvas)
1H      → ordem invertida
ABC     → coluna dupla sem linha
H       → falta a linha
```

O parser **não** adivinha. "H5" com a coluna H inexistente no canvas atual é
erro, não correção silenciosa — coordenada errada pintada é pior que erro.

Prefixos de comando (case-insensitive):

| Comando | Efeito |
|---|---|
| `<coordenada>` | Pinta |
| `/cor <nome\|#HEX>` | Define cor do usuário |
| `/cores` | Lista a paleta |
| `/meus` | Quantos pixels o usuário tem |
| `/rank` | Posição no ranking |
| `/ajuda` | Como jogar |

---

## 9. Cores

**Cor automática:** `hash(username) % len(paleta)` → cor estável e determinística.
O mesmo usuário sempre recebe a mesma cor, mesmo depois de um restart, sem
precisar de estado.

**Paleta base (8):** vermelho, laranja, amarelo, verde, azul, roxo, rosa, branco.

**Cores especiais** (desbloqueadas por conquista, com efeito visual animado):
🌈 arco-íris, 🔥 fogo, ⚡ elétrico, 🌌 galáxia, ✨ neon, 💎 diamante.

Cores especiais são puramente cosméticas. Não dão vantagem, não valem nada.

---

## 10. Progressão

**XP:** cada pixel pintado = 10 XP. Sobrescrever = 15 XP. Sequência de dias
consecutivos dá multiplicador.

| Nível | Título |
|---|---|
| 1 | Novato |
| 5 | Pintor |
| 10 | Artista |
| 20 | Mestre |
| 30 | Pixel Master |
| 50 | Lenda |

**Ranking:** top 5 visível na tela, com pixels pintados, sobrescritos, cores
usadas e sequência. Ranking completo no painel do streamer.

---

## 11. Eventos automáticos

Rodam sozinhos em ciclo, para que a tela nunca fique parada mesmo sem audiência.

| Evento | Duração | Efeito |
|---|---|---|
| 🎨 HORA DO PIXEL | 30s | Todos ganham +1 pixel |
| 🌈 ARCO-ÍRIS | 60s | Paleta especial liberada |
| ⚡ PIXEL TURBO | 30s | Interações dão pixels em dobro |
| 💥 CAOS | 20s | Custo cai para 1, sobrescrita liberada |
| 🎯 DESAFIO | — | Meta de região, recompensa coletiva |

O scheduler é um loop asyncio no backend. O frontend só recebe `event_start` e
`event_end` — toda a lógica de tempo vive no servidor, então múltiplas telas
nunca dessincronizam.

---

## 12. Protocolo WebSocket

**Cliente → servidor:** apenas `ping`. O cliente **nunca** pinta — pintura só
nasce de evento TikTok ou do painel de teste. Isso impede que alguém abra o
`localhost` e desenhe de graça.

**Servidor → cliente:**

```json
{"type":"hello","canvas":{"cols":26,"rows":51,"cells":[...]},"stats":{...}}
{"type":"pixel_painted","x":7,"y":5,"coordinate":"H5","color":"#FF0055",
 "user":"@joao","effect":null,"cost":1,"ts":1759931524}
{"type":"toast","kind":"reward","text":"🌹 @joao ganhou 1 PIXEL!"}
{"type":"feed","user":"@joao","coordinate":"H5","color":"#FF0055"}
{"type":"ranking","top":[{"user":"@joao","pixels":427,"level":27,"title":"Mestre"}]}
{"type":"stats","filled":842,"total":1326,"users":187,"colors":16}
{"type":"event_start","key":"rainbow","name":"ARCO-ÍRIS","ends_at":1759931584}
{"type":"event_end","key":"rainbow"}
{"type":"camera_focus","x":7,"y":5,"reason":"rare_pixel"}
{"type":"challenge","name":"DESENHEM UM CORAÇÃO","progress":78}
```

**Backpressure:** o hub agrupa atualizações de pixel num frame de ~50ms antes de
transmitir. Mil eventos por segundo viram 20 mensagens por segundo. Sem isso, a
tela engasga exatamente quando a LIVE está mais animada.

---

## 13. Layout OBS (1080x1920)

```
┌──────────────────────────────┐
│  🎨 PIXEL WORLD              │  120px
│  VOCÊ CONTROLA A ARTE        │
├──────────────────────────────┤
│  ⚡ EVENTO ATIVO             │
│  🌈 ARCO-ÍRIS    00:42       │  140px
├──────────────────────────────┤
│                              │
│      C A N V A S             │
│      26 × 51                 │  900px
│      (letras no topo,        │
│       números na lateral)    │
│                              │
├──────────────────────────────┤
│  🎨 ÚLTIMAS PINTURAS         │  320px
│  @joao → H5                  │
│  @maria → C12                │
├──────────────────────────────┤
│  🏆 TOP PINTORES             │
│  1. @joao    427             │  260px
│  2. @maria   391             │
├──────────────────────────────┤
│  📊 842/1326 · 63%           │  100px
├──────────────────────────────┤
│  ENVIE PRESENTE → GANHE      │
│  PIXELS → COMENTE A          │  80px
│  COORDENADA                  │
└──────────────────────────────┘
```

**Nenhum elemento usa blur pesado.** OBS Browser Source renderiza em GPU
limitada e a captura fica borrada em movimento. Brilho é feito com gradiente e
`shadowBlur` contido, não com `filter: blur()` em áreas grandes.

**Legibilidade à distância:** tudo que o espectador precisa ler está em ≥28px.
Coordenadas e nomes em ≥32px. A pessoa assiste no celular, com o vídeo ocupando
metade da tela.

---

## 14. Efeitos

Camadas, de baixo para cima:

1. **Fundo** — gradiente escuro, grade sutil
2. **Pixels** — células pintadas, com brilho interno proporcional ao tempo desde a pintura (pixels novos brilham mais e desbotam para o estado estável)
3. **Efeitos de pixel** — arco-íris cicla matiz, fogo pulsa, elétrico pisca
4. **Partículas** — pool fixo, reutilizado; nunca alocado por evento
5. **HUD** — ranking, feed, evento, progresso
6. **Câmera** — transform aplicado às camadas 1-4

**Animação de pintura** (~700ms): flash branco na célula → partículas na cor →
tinta preenche → cor final → nome do usuário flutua e some.

**Câmera:** só reage a pixel raro ou conquista. Zoom leve por ~1.2s e volta.
Disparar sempre vira ruído.

---

## 15. Performance

| Risco | Mitigação |
|---|---|
| Pico de eventos | Fila asyncio com worker único; pinturas são serializadas |
| Milhares de mensagens/s | Agrupamento em frames de 50ms antes do broadcast |
| Spam de comentário | Rate limit por usuário (1 pintura/2s), excedente descartado |
| Loop de render pesado | `requestAnimationFrame` com dirty-flag: sem mudança, sem redraw |
| Partículas | Pool fixo de 400, reciclado |
| Disco lento | Persistência write-behind, nunca no caminho da renderização |
| Reconexão | Backoff exponencial com jitter; estado completo reenviado ao reconectar |

---

## 16. Test Mode

Cidadão de primeira classe. Painel em `/control`, **não** aparece na transmissão.

Permite simular comentário, presente (com quantidade), like, follow, share — por
um usuário arbitrário. Também permite: forçar evento, resetar inventário, apagar
pixel, ver histórico de um pixel, e um botão que simula 200 eventos de uma vez
para testar carga.

Sem isso, iterar no visual depende de ter audiência. Com isso, o jogo é
desenvolvido em minutos, não em dias.

---

## 17. Fora de escopo (vertical slice)

Deliberadamente adiado, mas a arquitetura não bloqueia nenhum:

- Modo Imagem (converter foto em pixel art e desafiar a comunidade a reproduzir)
- Regiões do mapa com eventos por área
- Sistema de conquistas completo
- Música/ambiente sonoro
- Múltiplas salas simultâneas

---

## 18. Critérios de aceite do vertical slice

1. `python main.py` sobe o servidor e serve a tela do OBS
2. A tela carrega em 1080x1920 sem scroll, sem elemento cortado
3. O painel de controle simula um presente → o inventário sobe → o comentário
   com coordenada pinta o pixel → a animação roda → ranking e feed atualizam
4. Fechar e reabrir o programa preserva o canvas inteiro e o histórico
5. Conectar na LIVE real funciona com a mesma camada do projeto antigo
6. 200 eventos simulados de uma vez não travam a tela nem dropam frames visíveis
7. Sobrescrever pixel custa 2 e aparece no histórico
8. Coordenada inválida é rejeitada com mensagem clara e não cobra o usuário
