# PIXEL WORLD — como tudo funciona por dentro

Este documento existe para uma coisa só: **você voltar aqui daqui a três meses
e conseguir mexer no código sem reler o projeto inteiro.**

O `README.md` explica o jogo para quem vai usar. Este explica o jogo para quem
vai *mexer*. Se os dois discordarem, o código manda — e vale abrir um issue
mental para corrigir o texto.

---

## Sumário

1. [O caminho de um evento](#1-o-caminho-de-um-evento) — o fluxo mais importante
2. [Mapa dos módulos](#2-mapa-dos-módulos) — quem faz o quê
3. [O laço do jogo](#3-o-laço-do-jogo) — o coração, 20 vezes por segundo
4. [O protocolo WebSocket](#4-o-protocolo-websocket) — e a armadilha do lote
5. [A API HTTP](#5-a-api-http)
6. [O banco de dados](#6-o-banco-de-dados)
7. [Configuração, chave por chave](#7-configuração-chave-por-chave)
8. [Receitas](#8-receitas) — como mudar as coisas mais comuns
9. [Invariantes](#9-invariantes) — o que você **não** pode quebrar
10. [Testes](#10-testes)

---

## 1. O caminho de um evento

Este é o fluxo que importa. Tudo o mais no projeto existe para servir a ele.

Alguém manda uma rosa e comenta `H5`. O que acontece, em ordem:

```
TikTok ──▶ tiktok/adapter.py ──▶ core/event_queue.py
                                        │
                                        ▼
                            backend/estado.py :: _laco()
                                        │  (a cada 50 ms)
                                        ▼
                            game/pipeline.py :: Pipeline.processar()
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            game/coordinates.py   game/painting.py    game/ranking.py
             "H5" → (7,5)         cobra, pinta        XP e nível
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                          backend/estado.py :: _publicar_do_hub()
                                        │
                                        ▼
                            backend/hub.py :: publicar()
                                        │  (acumula por quadro)
                                        ▼
                            backend/hub.py :: despejar()
                                        │  WebSocket
                                        ▼
                            ui/js/app.js :: aoMensagem()
                                        │
                                        ▼
                            ui/js/renderer.js  +  ui/js/hud.js
```

### Em detalhe

**1. O evento entra.** `tiktok/adapter.py` escuta a LIVE e traduz cada coisa
(comentário, presente, curtida, seguidor, compartilhamento) para um `LiveEvent`
(`core/events.py`). Em MODO TESTE, `tiktok/simulado.py` produz `LiveEvent`s
**idênticos** — é o mesmo contrato, então o resto do sistema não sabe a
diferença. Isso é de propósito: o que você ensaia é o jogo de verdade.

**2. O evento espera na fila.** `core/event_queue.py`. A fila tem teto
(`limits.queue_max_size`): se a LIVE viralizar, ela descarta os eventos **mais
antigos** em vez de crescer até derrubar o processo. Perder um comentário velho
é aceitável; perder a transmissão não é.

**3. O laço drena a fila.** `EstadoJogo._laco()` roda a cada `server.frame_ms`.
Ele tira até `app.events_per_frame` eventos e passa cada um para o pipeline.
**Nada acontece fora desse laço** — é ele que serializa tudo, e por isso não
existe condição de corrida entre dois espectadores pintando ao mesmo tempo.

**4. O pipeline decide.** `Pipeline.processar()` é o cérebro. Para um
comentário, ele tenta três coisas nesta ordem:

| Ordem | O quê | Onde |
|---|---|---|
| 1 | É uma coordenada? (`H5`, `h 5`, `/pixel H5`, `A2, B2, C3`) | `game/coordinates.py :: parse_coordenadas` |
| 2 | É um comando de cor? (`/cor vermelho`) | `game/colors.py :: parse_cor` |
| 3 | Não é nada disso → aviso "NÃO ENTENDI" | `Pipeline._erro` |

Repare que `parse_coordenadas` devolve lista vazia quando não entende — e o
pipeline **não adivinha**. Um pixel pintado no lugar errado é pior que uma
mensagem de erro, porque quem pintou só descobre depois. Essa dureza é sobre a
**peça**: `"H5extra"` nunca vira `H5`, e nunca vai virar.

Ela já foi dura sobre o **pedido** também — uma peça inválida derrubava a lista
inteira — e isso estava errado. O campo do painel tinha uma linha só, e um
`<input>` de uma linha cola texto de várias linhas **grudado**: a receita de um
coração em três linhas chegava como `...AE22S23...`, uma "coordenada" que não
existe, e o jogo respondia `NÃO ENTENDI` com as outras 72 células na mão. Quem
colou a receita e viu zero pixel não conclui "digitei errado" — conclui que não
funciona. Hoje a peça ilegível é **denunciada pelo nome** e o resto pinta:
`NAO ENTENDI: AE22S23`. Pintar metade era o pior desfecho enquanto ninguém
sabia *qual* metade; com o nome da peça na tela, é o melhor.

### Desenhar de uma vez: cem rosas e a lista

O gesto que o jogo precisa suportar é este: a pessoa manda um presente grande e
escreve o desenho inteiro num comentário. Duas coisas atrapalhavam.

**O presente ficava no teto.** `game/rewards.py` faz
`base * min(quantidade, max_multiplicador)` — o teto é do *streak*, não do
presente. Um Galaxy (base 60) manda 60 pixels; cem rosas mandavam 10, porque
`max_multiplicador` **não existia no `config.json`** e o código caía no padrão
10 em silêncio. Agora existe, em 100: cem rosas valem cem pixels, e um streak
maior continua parando aí.

**O comentário só entendia uma coordenada.** `parse_pedido` aceita
`A2, B2, C3`, `A2,B2`, `A2; B2`, `A2 B2` e uma coordenada por linha, além de
tudo que a versão antiga aceitava. Quatro decisões dentro dele:

- **A frase inteira tem a primeira chance.** `"H 5"` é uma célula desde o
  primeiro dia; se o espaço separasse lista antes disso, quem escreve com
  espaço pararia de pintar. Só o que *não* é uma coordenada sozinho chega a ser
  partido — e aí o espaço também corta, para `"A2, B2 C3"` virar três células.
- **A quebra de linha corta junto com a vírgula.** Não é enfeite: é o que faz
  a receita de várias linhas funcionar no campo do painel. Nenhuma coordenada
  válida contém `\n`, então cortar por ele não tem risco nenhum.
- **Célula repetida conta uma vez.** `"A2, a2, A-2"` é um pedido, não três.
  Peça ilegível repetida também vira um aviso só.
- **`/p A2` é o prefixo, não a coluna "PA".** Não existe canvas largo o
  bastante para "PA" ser uma coluna de verdade (índice 416), e é por isso mesmo
  que a ambiguidade morre na ordem das checagens: ela não daria erro, daria um
  pixel no lugar errado.

O que volta é um `Pedido`, não uma lista: `pedido.coordenadas` (o que dá para
pintar) e `pedido.invalidas` (as peças cruas, do jeito que a pessoa escreveu,
para a tela poder dizer o nome delas). `parse_coordenadas` continua existindo
como atalho para quem só quer as células.

**O cooldown é do comentário, não de cada pixel.** Em `game/painting.py`,
`pintar_lote` compartilha um `_Relogio` entre as células: a primeira que passa
por saldo e coordenada bate o relógio, e as outras pegam a porteira aberta. O
cooldown existe para uma pessoa não monopolizar o quadro — não para racionar
pixel que ela já pagou. Sem isso, `"A2, B2, C3..."` seria uma fila de minutos e
a lista nunca serviria para desenhar. E o tique só sai quando um pixel sai de
verdade: quem foi recusado por falta de saldo continua com a vez na mão.

**O que fazer quando não cabe.** `limits.max_pixels_por_comentario` (100) corta
a lista, e `max_pixels_por_evento` corta o crédito. Nos dois casos o que entrou
é pintado e um aviso diz o número — `SEM PIXELS — MANDE UMA ROSA 🌹 (3 DE 10)`
ou `SO CABEM 100 POR VEZ — 100 DE 150 PINTADOS`. Nunca truncar calado: a pessoa
precisa saber que faltou, senão a conclusão é "o jogo quebrou".

Os dois avisos contam só células legíveis, e a peça ilegível tem um terceiro
aviso, separado: `NAO ENTENDI: AE22S23`. Ele não promete nada sobre pintura de
propósito — vale igual quando o desenho entrou inteiro e quando o saldo acabou
no meio, e "o resto entrou" seria mentira no segundo caso. No máximo três peças
aparecem, encurtadas em 14 caracteres; o resto vira contagem.

Cem células levam ~150 ms e quatro escritas no banco cada uma. O teto de 100
existe por isso: um comentário colado com as 2550 células do quadro deixaria a
LIVE travada atendendo uma pessoa.

**5. A pintura acontece.** `game/painting.py :: ServicoPintura` faz as
checagens nesta ordem, e a ordem importa:

```
coordenada existe?  →  a pessoa tem saldo?  →  passou o cooldown?
```

Coordenada primeiro porque é o erro que a pessoa comete mais; saldo antes do
cooldown porque "faltam pixels" é uma mensagem mais útil que "espere 2s".
O custo é 1 em célula virgem e 2 por cima de outro (`rewards.pixel_custo` e
`rewards.sobrescrita_custo`).

**6. O jogo conta a novidade.** O resultado vira uma lista de mensagens
(`pixel_painted`, um `toast`, uma linha de `feed`…). Todas passam por
`EstadoJogo._publicar_do_hub()`.

**7. O hub agrupa.** `backend/hub.py` junta tudo que não é estado e manda **uma
mensagem por quadro** em vez de uma por pixel. Numa LIVE com 300 pessoas isso é
a diferença entre 1 mensagem e 300 a cada 50 ms. **Esta é a parte que você
precisa entender antes de mexer no cliente — veja a seção 4.**

**8. O navegador desenha.** `ui/js/app.js :: aoMensagem()` despacha, o
`renderer.js` pinta a grade no `<canvas>` e o `hud.js` atualiza o HTML em volta.

---

## 2. Mapa dos módulos

### `game/` — as regras

**Puro.** Não importa `tiktok/`, `backend/` nem `core/`. Não abre socket, não lê
arquivo, não olha o relógio (o tempo entra por parâmetro). Consequência prática:
**dá para testar a economia inteira sem subir servidor e sem esperar.**

| Arquivo | O que faz | API principal |
|---|---|---|
| `coordinates.py` | `"H5"` ↔ `(7, 5)`, e `"A2, B2, C3"` ↔ três células | `parse_coordenada`, `parse_pedido`, `parse_coordenadas`, `Pedido`, `rotulo_de`, `parece_pintura` |
| `canvas.py` | A grade e as células | `CanvasModel`, `Celula` |
| `colors.py` | Cor por pessoa, paleta, cores especiais | `cor_automatica`, `parse_cor`, `Cor` |
| `inventory.py` | Quantos pixels cada um tem | `adicionar`, `definir`, `gastar` |
| `painting.py` | Pintar, cobrar, sobrescrever | `ServicoPintura.pintar` |
| `pipeline.py` | Evento do TikTok → o que acontece no jogo | `Pipeline.processar` |
| `rewards.py` | Presente → quantos pixels; curtidas acumuladas | `pixels_do_evento` |
| `xp.py` | Curva de nível | `xp_para_nivel`, `titulo_de` |
| `ranking.py` | O placar | `Ranking.registrar`, `top` |
| `events.py` | Eventos automáticos da LIVE | `SchedulerEventos` |

**O alfabeto das colunas é indexação de planilha:** `A`=0, `Z`=25, `AA`=26.
`letra_para_indice` faz `AA → 26` com um `n = n * 26 + letra`. A mesma regra
existe em `ui/js/geometry.js` — **as duas precisam concordar** (seção 9).

### `tiktok/` — a fronteira com o mundo

| Arquivo | O que faz |
|---|---|
| `adapter.py` | `TikTokLive` → fila de eventos. Reconecta sozinho, com espera crescente. |
| `simulado.py` | O **mesmo** contrato, inventando os eventos (MODO TESTE). |
| `base.py` | O contrato que os dois cumprem. |

A importação da `TikTokLive` fica dentro de um `try` no topo do `adapter.py`.
Se a biblioteca não estiver instalada, o jogo sobe em MODO TESTE em vez de
morrer na importação — dá para trabalhar na interface sem a dependência.

### `backend/` — rede e persistência

| Arquivo | O que faz |
|---|---|
| `app.py` | FastAPI, WebSocket, as duas páginas. **Não tem regra de jogo.** |
| `estado.py` | A **raiz de composição**: quem monta o quê, e o laço do jogo. |
| `hub.py` | Fan-out do WebSocket, em lotes por quadro. |
| `database.py` | SQLite em WAL. |
| `control.py` | A API do painel do operador. |

Se você só puder ler um arquivo para entender o projeto, leia
**`backend/estado.py`**. É lá que todas as peças são ligadas, e é onde você
mexe quando quer acrescentar um componente novo.

### `core/` — o que serve a todos

`config.py` (lê, mescla e **valida**), `event_queue.py` (fila com teto),
`ratelimit.py` (cooldown e orçamento), `events.py` (o `LiveEvent` e o
`EventType`).

### `ui/` e `control/`

`ui/` é a tela que vai ao ar (1080×1920, Canvas 2D + HTML em volta).
`control/` é o painel do operador, que **não vai ao ar**.

| Arquivo | O que faz |
|---|---|
| `ui/js/app.js` | A ligação: WebSocket → estado → desenho. |
| `ui/js/renderer.js` | Desenha a grade no canvas. |
| `ui/js/geometry.js` | O parser e a matemática da grade (**espelha o Python**). |
| `ui/js/hud.js` | Ranking, feed, estatísticas, avisos, banner de evento. |
| `ui/js/effects.js` | Partículas e animações. |
| `ui/js/eventos.js` | O desenho dos eventos (arco-íris, CAOS, DESAFIO) por cima da grade. |
| `control/control.js` | O painel. Fala HTTP puro, sem WebSocket. |

**O campo de texto do painel é um `<textarea>`, e isso não é estética.** O
painel não valida coordenada nenhuma: ele manda o texto cru para
`POST /api/simular` e quem responde é o pipeline. Só que um `<input>` de uma
linha **cola texto de várias linhas grudado** — a receita do coração, colada
inteira, chegava no servidor como uma linha só, com `AE22` e `S23` fundidos em
`AE22S23`. Com o campo de várias linhas a quebra sobrevive ao paste, e o
parser do Python corta por ela. Se você trocar o `<textarea>` por `<input>`, o
conserto que existe no servidor perde o efeito no painel.

**O palco preenche a janela sozinho.** `#palco` tem uma **altura** de projeto
fixa (1920) e uma **largura** que vem da janela: `width: var(--largura-projeto)`.
As duas variáveis saem de `geometry.js :: escalaParaCaber`, chamado por
`app.js :: ajustar()` a cada `resize`:

```
escala = alturaJanela / 1920          -> --escala         (o transform do palco)
larguraProjeto = larguraJanela / escala -> --largura-projeto (a largura do palco)
```

Juntas, as duas contas dão `escala * 1920 == alturaJanela` e
`escala * larguraProjeto == larguraJanela`: o palco cobre a janela exatamente, em
qualquer formato, sem faixa preta e sem cortar o cabeçalho ou o rodapé.

**Por que a altura manda e a largura obedece.** Tudo que está dentro do palco é
uma fração da *altura* — cabeçalho 140px, rodapé 560px, arena o resto. Fixando a
altura, a composição vertical sai idêntica em qualquer janela (o título sempre
com 7,3% da altura, a arena com 63,5%). O que sobra de largura vira **arena**, e
a grade se centra nela. A alternativa — encaixar 1080×1920 inteiro — deixava
faixas pretas nas laterais de qualquer janela que não fosse 9:16, e quem assiste
pelo navegador vê a faixa.

Quatro armadilhas que já custaram caro:

- **O `transform` não mexe no layout.** Para efeito de posicionamento o palco
  continua medindo o tamanho nominal, então centralizá-lo com
  `place-items: center` no body **não funciona**: uma linha de grade `auto`
  cresce até o tamanho do próprio item, a linha vira 1920px numa janela de 768px
  e não sobra nada para centralizar. O palco escalado ficava pendurado no meio de
  uma página de 1920px, com metade abaixo da dobra. Hoje ele é centrado por
  **posição** (`absolute` + `left/top: 50%` + margem negativa da metade).
- **`getBoundingClientRect()` responde no espaço da TELA; o canvas vive no
  espaço do PALCO.** O rect devolve o tamanho *depois* do `transform: scale()`.
  Numa janela de 1366×768 a arena mede **3415** no layout e **1366** na tela —
  escrever 1366 no `canvas.style.width` fazia o canvas cobrir 40% da arena,
  colado na esquerda, e a grade saía desenhada num canto. Quem responde pelo
  layout é `arena.offsetWidth`/`offsetHeight`, que a escala não toca. Com
  `escala == 1` (o OBS) os dois espaços dão o mesmo número, e foi por isso que o
  defeito passou tanto tempo escondido.
- **O buffer, esse sim, é em pixels da tela.** `canvas.width` tem que ser
  `largura * escala * devicePixelRatio`, e é por isso que
  `renderer.redimensionar()` recebe a `escala` e a multiplica pelo
  `devicePixelRatio` em vez de substituí-lo. Sem isso a célula deixa de cair em
  pixel inteiro do aparelho e as bordas se dissolvem — o defeito dos "uns
  quadrados com borda e outros sem".
- **A medida do canvas vem depois das variáveis.** Escrever `--largura-projeto`
  muda o layout; medir antes daria a arena do tamanho antigo.

---

## 3. O laço do jogo

`backend/estado.py :: EstadoJogo._laco()` roda a cada `server.frame_ms`
(50 ms por padrão). Cada volta faz:

1. **Drena a fila** — até `events_per_frame` eventos para o pipeline.
2. **Faz o agendador andar** — `SchedulerEventos.tick()`, que sorteia e encerra
   eventos automáticos.
3. **Despeja o hub** — `hub.despejar()`, uma mensagem por cliente por quadro.
4. **Publica o estado** — mas só se alguém pintou neste quadro
   (`EstadoJogo.processar_pendentes`). Como `ranking` e `stats` pertencem ao
   balde de estado, publicar várias vezes no mesmo quadro custa **uma**
   mensagem: a última. É por isso que o laço pode chamar `publicar_estado()`
   sem medo.

**O laço nunca pode morrer.** `SchedulerEventos.tick()` engole exceções de
propósito: a tela do OBS fica horas no ar sem ninguém olhando o terminal, e um
erro de agendador derrubaria o desenho inteiro. Pelo mesmo motivo, o
`requestAnimationFrame` do cliente está dentro de um `try/catch`.

**Cadência:** 20 quadros por segundo. É o suficiente para parecer instantâneo
ao olho e é barato o bastante para rodar por dias. Se você baixar
`frame_ms` demais, o custo por segundo sobe e a diferença visual é nula.

---

## 4. O protocolo WebSocket

**Este é o pedaço que já causou o pior bug do projeto. Leia inteiro.**

O WebSocket é **mão única**: só `ping` sai do navegador. Toda pintura nasce de
um evento do TikTok ou do painel. É isso que impede alguém de abrir o endereço
do streamer e desenhar de graça.

### Os dois baldes

`backend/hub.py` separa as mensagens em dois grupos:

```python
TIPOS_DE_ESTADO = frozenset({"ranking", "stats", "estado", "canvas"})
```

| Balde | O que faz |
|---|---|
| **Estado** (`ranking`, `stats`, `estado`, `canvas`) | **Substitui.** Manda o retrato mais recente; quem chegou atrasado não perde nada. |
| **Todo o resto** | **Acumula** num `deque` e sai como `{"type": "pixels", "items": [...]}`. |

O lote é **heterogêneo**. Dentro dele viajam `pixel_painted`, `pixel_cleared`,
`toast`, `feed`, `inventario`, `event_start` e `event_end` — misturados, na
ordem em que aconteceram.

### A armadilha

O cliente recebe:

```json
{ "type": "pixels", "items": [ { "type": "toast", "text": "..." } ] }
```

`pacote.type` é **`"pixels"`**. Se você despachar por ele, vai procurar um
`case "toast"` que nunca aparece — e o aviso da rosa, o "NÃO ENTENDI" e o
banner de evento somem **sem deixar rastro**. Foi exatamente o que aconteceu: o
espectador mandava uma rosa, comentava a coordenada, e não via retorno nenhum.

O jeito certo, em `ui/js/app.js`:

```js
case "pixels":
  for (const item of pacote.items || []) aoMensagem(item);  // despacha pelo tipo DO ITEM
  break;
```

**Regra para quem for acrescentar um tipo novo:** se não for estado, ele é um
item dentro do lote. Coloque o `case` no nível de item, nunca no de envelope.

### Tipos que existem hoje

| Tipo | Balde | Forma |
|---|---|---|
| `hello` | sozinho | Manda o estado completo para quem acabou de conectar |
| `ranking` | estado | `{top: [...]}` |
| `stats` | estado | `{filled, users, percent, ...}` |
| `estado` | estado | O retrato completo |
| `canvas` | estado | A grade inteira |
| `pixel_painted` | item | `{x, y, color, user, coordinate, effect}` |
| `pixel_cleared` | item | `{x, y}` |
| `grid_cleared` | item | Sem corpo. O botão LIMPAR do painel — a tela zera as células **e** mata as animações |
| `toast` | item | `{kind, text}` |
| `feed` | item | Uma linha de "ÚLTIMAS PINTURAS" |
| `inventario` | item | O novo saldo de alguém |
| `event_start` / `event_end` | item | O banner do evento |

O `hello` sai **antes** de a conexão ser registrada no hub. Parece detalhe, mas
sem isso o cliente pode receber novidades antes do retrato que elas pressupõem
— e ficar com um ranking vazio depois de já ter visto pixels.

---

## 5. A API HTTP

Só o painel usa, e **só em `localhost`**. Não existe CORS configurado, e essa
ausência **é** o controle de segurança: uma página qualquer que você abrir no
navegador não consegue falar com o seu jogo.

| Método | Rota | O que faz |
|---|---|---|
| `GET` | `/` | A tela que vai ao ar |
| `GET` | `/control` | O painel |
| `GET` | `/api/estado` | Retrato completo (ranking, feed, canvas, fonte) |
| `GET` | `/api/pixel/{x}/{y}` | Um pixel e o histórico dele |
| `POST` | `/api/simular` | Inventa um evento (**só em MODO TESTE**) |
| `POST` | `/api/inventario` | **Crava** o saldo de alguém (`{user, pixels}`) |
| `POST` | `/api/burst` | Rajada de eventos falsos |
| `DELETE` | `/api/pixel/{x}/{y}` | Apaga um pixel |
| `DELETE` | `/api/canvas` | **Esvazia o quadro inteiro** e mata as animações. O ranking fica |
| `POST` | `/api/evento` | Força um evento pelo `key` |
| `WS` | `/ws` | O canal da tela |

**Vocabulário da fronteira.** Todo corpo de requisição e todo JSON que
atravessa a rede fala os nomes do spec §12 — `type`, `user`, `text`, `gift`,
`quantity`, `count`, `key`, `level`, `title`, `top`, `position`, `cells`,
`filled`, `coordinate`, `effect`, `event`. Só os nomes **internos** são em
português. A fronteira de rede é uma só no projeto inteiro; ter duas seria pior
que ter uma em inglês. Se você expor um campo novo, use o nome da fronteira e
traduza na hora de responder (é o que `control.py` faz com o histórico).

---

## 6. O banco de dados

SQLite em WAL, em `app.db_path`. **Escrever é em lote:** uma LIVE com 300
pessoas não pode custar 300 `INSERT` por segundo, então as pinturas são
agrupadas por quadro.

| Tabela | O que guarda |
|---|---|
| `users` | Quem é quem: nome, cor escolhida, efeito |
| `pixels` | A grade: quem pintou cada célula e quando |
| `pixel_history` | Tudo que já passou por cada célula |
| `paint_actions` | Cada ação de pintura (a matéria-prima do ranking) |
| `gifts` | Os presentes recebidos |
| `events` | Os eventos automáticos que já rodaram |
| `achievements`, `user_stats`, `canvas_settings`, `challenges` | Estrutura pronta |

**O que é durável e o que não é.** Ao reiniciar, o jogo **reconstrói** o canvas,
o ranking e a cor de cada pessoa a partir do banco. Duas consequências que
valem saber:

- A cor automática vem de `crc32(username)`, **não** de `hash()`. O `hash()` do
  Python é aleatorizado a cada processo: a cor de todo mundo trocaria a cada
  reinicialização e a audiência perderia a única referência visual que tem.
- O `Ranking` é carregado de `top_pintores(500)`. Quem escolheu `/cor` mas
  **nunca pintou**, ou está fora dos 500 maiores, volta para a cor automática.
  Se isso incomodar, o conserto é carregar mais gente no boot, em
  `backend/estado.py`.

**Recomeçar do zero:** pare o servidor e apague `pixelworld.db` (e os
`-wal`/`-shm` ao lado). Com o servidor no ar o Windows não solta os arquivos.

---

## 7. Configuração, chave por chave

Tudo que dá para afinar vive em `config.json`. **Configuração inválida não
sobe** — o erro diz qual chave corrigir (`core/config.py` valida e mescla por
cima dos padrões do código).

### `app`

| Chave | Padrão | O que faz |
|---|---|---|
| `titulo`, `subtitulo` | `PIXEL WORLD` | O que aparece no topo |
| `log_dir` | `logs` | Onde o log é escrito |
| `db_path` | `pixelworld.db` | O banco |
| `feed_size` | `6` | Quantas linhas cabem em "ÚLTIMAS PINTURAS" |
| `events_per_frame` | `400` | Teto de eventos processados por quadro |

### `server`

`host`, `port` e `frame_ms` (o intervalo do laço — seção 3).

### `canvas`

`cols`, `rows`, `paleta` e `especiais`. **O canvas pode crescer, e isso é só
config** (veja a receita abaixo).

### `tiktok`

`username` (o `@` da LIVE), `reconnect_seconds`, `reconnect_max_seconds`,
`fetch_gift_info`, `cooldown_pintura` (o cooldown por pessoa, em segundos).

### `rewards`

`pixel_custo`, `sobrescrita_custo`, `presente_desconhecido` e o mapa `gifts`.
Presente fora do mapa vale `presente_desconhecido` — o TikTok lança presente
novo toda semana, e é melhor dar 1 pixel do que travar a LIVE.

`max_multiplicador` é o teto do **streak**, não do presente: a conta é
`base × min(quantidade, teto)`. Com 100, cem rosas valem cem pixels e um streak
maior continua parando aí. Se ele sumir do arquivo, o código cai no padrão 10
sem avisar ninguém — há um teste que lê *este* arquivo justamente para isso.

### `xp` e `limits`

A curva de nível e os tetos: `queue_max_size` (a fila), `max_pixels_por_evento`
(o crédito de um evento) e `max_pixels_por_comentario` (o tamanho de uma lista
de coordenadas). Veja a seção 9 sobre chaves mortas.

---

## 8. Receitas

### Aumentar ou diminuir o canvas

```json
"canvas": { "cols": 50, "rows": 51 }
```

**É só isso.** O tamanho da célula é *calculado* (`ui/js/geometry.js ::
calcularGrade`), nunca fixo — a grade encolhe e continua cabendo na tela. O
alfabeto vai até `ZZ` (702); acima disso o servidor recusa a configuração,
porque o rótulo deixa de ser algo que uma pessoa digita sem errar.

**Se você passar de 26 colunas**, os rótulos ganham duas letras (`AA`) e a
fonte deles encolhe sozinha (`fonteDoRotulo`) para as duas caberem na célula.
Sem isso, `AA` encosta na célula vizinha.

### Acrescentar um presente

Em `config.json`, dentro de `rewards.gifts`:

```json
"Meu Presente Novo": 10
```

O nome tem que bater com o que a `TikTokLive` reporta. Use
`fetch_gift_info: true` e olhe o log: os presentes que chegam aparecem lá com o
nome exato.

### Acrescentar uma cor

Na paleta, dentro de `canvas.paleta`:

```json
"turquesa": "#40E0D0"
```

O nome vira o que a audiência digita (`/cor turquesa`) e o que o aviso mostra.
Acentuação e maiúsculas não importam — `achatar()` normaliza.

Cores especiais (com efeito animado) ficam em `canvas.especiais` e precisam de
um efeito implementado em `ui/js/efeitos.js` para desenhar diferente.

### Acrescentar um evento automático

Em `events.catalog`:

```json
{ "key": "chuva", "name": "CHUVA DE PIXEL", "emoji": "🌧",
  "duration": 30, "multiplier": 2.0, "weight": 2.0, "effect": null }
```

- `weight` é o peso do sorteio (peso maior = sai mais).
- `multiplier` multiplica **quantos pixels cada presente dá** durante a janela.
- `effect` é um efeito visual aplicado durante o evento (`caos`, `arco_iris`…).
- `key` é o que o painel manda em `POST /api/evento`.

`events.active: false` desliga o **sorteio**, não o agendador — forçar pelo
painel continua funcionando, para você poder voltar atrás sem reiniciar o
servidor no meio da LIVE.

### Acrescentar um comando de chat

Um comando novo (tipo `/ranking`) entra em `Pipeline.processar()`, em
`game/pipeline.py`, **antes** da tentativa de coordenada. Siga o padrão de
`_trocar_cor`: valide, faça o efeito, e devolva um `toast` — o comando precisa
responder alguma coisa, mesmo que dê errado.

Se o comando puder ser confundido com uma coordenada, ensine
`parece_pintura()` a recusá-lo (veja a seção 9).

### Mudar o visual

- **Cores e espaçamento do HUD:** `ui/style.css`. As cores do tema estão em
  variáveis CSS no topo (`:root`).
- **A grade e a régua:** `ui/js/renderer.js`.
- **As partículas:** `ui/js/effects.js`.

**A régua tem uma tinta só dela** — o âmbar `--regua` (`#ffc14d`), o mesmo em
`style.css` e `renderer.js`. Ele aparece onde há **leitura** (o rótulo da
coluna, o número da linha, a coordenada no feed, a escala do cabeçalho) e em
nenhum outro lugar. O resto da tela é frio: ciano, rosa, o azul do fundo. É a
regra de carta topográfica — o terreno numa cor, a grade de referência em
outra — e é o que faz uma coordenada no feed e a mesma coordenada na margem do
quadro parecerem a mesma coisa.

⚠️ Se você trocar `--regua` num arquivo e esquecer do outro, a coordenada do
feed deixa de ser a coordenada da tela. Não há teste para isso: os dois valores
são independentes por construção. Mexa nos dois.

A **largura das faixas** (`faixaLetras` / `faixaNumeros` em `geometry.js`) é
maior do que o rótulo precisa porque dentro delas mora também a fileira de
tracinhos. Alargar custa largura de grade: com 1080 de largura sobram 1018 para
50 colunas = 20,36, então a célula continua 20. **Mais um pixel de faixa e a
célula cai para 19** — a grade inteira encolhe por causa de enfeite. Se for
mexer, rode `node --test ui/js/geometry.test.mjs` depois.

### Onde ficam as decisões de desenho

- **O traço comprido e o rótulo aceso caem nas MESMAS colunas** — os dois
  perguntam `ehMarco()` em `geometry.js`. Se um dia divergirem, quem conta de
  cinco em cinco pelas marcas para achar a coluna H conta errado.
- **Os números das linhas são alinhados pela direita**, para as unidades
  ficarem na mesma coluna e a fileira virar uma escala.
- **A barra de progresso é uma escala graduada** (marcas de 10 em 10%), e não
  uma barra lisa: dá para ler o número na própria barra.
- **O título não tem halo.** O brilho de letreiro lava a borda da letra. O neon
  da tela vem do ciano da grade, do âmbar da régua e das cores da comunidade.

⚠️ Emoji no HTML e no JS é seguro (as páginas são UTF-8). O que **não** é
seguro é um `print()` com emoji em código que rode fora do `main.py` — o
console do Windows é cp1252 e estoura. Veja o invariante 7.

### Recomeçar o placar

Pare o servidor, apague `pixelworld.db` e os vizinhos `-wal`/`-shm`, suba de
novo. O banco é recriado vazio na primeira execução.

### Limpar o quadro (sem parar o servidor)

O botão **Limpar tudo** no painel (`DELETE /api/canvas`). Apaga todos os pixels
— memória **e** banco — e avisa a tela, que zera as células e mata as animações
no ar. Não tem desfazer; o painel pede confirmação e diz quantos pixels vão
embora.

O que ele **não** apaga, de propósito:

| Fica | Por quê |
|---|---|
| O **ranking** e o XP | Limpar o quadro é apagar o desenho. Apagar o placar seria apagar a participação de quem mandou rosa a LIVE inteira. |
| O **histórico** (`pixel_history`) | É a memória do que aconteceu, não o desenho. É a única forma de responder "quem apagou o meu pixel?" ao vivo. |
| O **`users`** | Quem pintou não deixa de ter pintado porque o quadro foi limpo. |

Se você quiser apagar tudo mesmo, é a receita acima: banco fora, servidor
parado.

---

## 9. Invariantes

Coisas que **não** podem deixar de valer. Cada uma já custou caro uma vez.

### 1. Os dois parsers de coordenada precisam concordar

`game/coordinates.py` (Python) e `ui/js/geometry.js` (JavaScript) implementam a
mesma regra, e o painel do operador importa o do **JS** de propósito. Se
divergirem, o sintoma é o pior possível: **o streamer inspeciona uma
coordenada que a audiência pintou e o painel mostra outro pixel.**

Os dois já divergiram uma vez: o Python aceitava `H-5` e `/p H5`, o JS não.
Hoje existe uma **tabela de verdade compartilhada** nos dois arquivos de teste,
com a resposta literal do backend. Se você mexer em um parser, rode os dois
testes — e acrescente o caso novo na tabela dos dois lados.

O parser do JS aceita `cols`/`rows` opcionais. Sem eles (no servidor) quem
decide é o limite do canvas; com eles (no painel) as duas implementações
respondem igual **até nos casos de limite** — `/pintar 5 5` só é recusado pelo
tamanho da grade.

**A lista é a divergência que existe hoje, e ela é deliberada.** `analisarRotulo`
no JS entende UMA célula; `parse_pedido` no Python entende a lista. Não é
esquecimento: o único lugar do painel que chama o parser do JS é o campinho
*Inspecionar pixel*, que pergunta "qual é esta célula?" e não tem como responder
sobre setenta e quatro. Quem manda texto para o jogo manda para o Python — o
painel entrega o comentário cru para `POST /api/simular` e quem decide é o
pipeline. Se algum dia o painel precisar validar uma lista antes de enviar, o
espelho tem que crescer junto; hoje ele não precisa, e por isso não cresceu.

### 2. Ninguém adivinha uma coordenada

Se uma peça não vira uma célula exata, ela **não é pintada** — e o jogo diz o
nome dela. Não existe "quase H5": `H5extra` nunca vira `H5`. Isso vale para a
peça, não para o pedido: numa lista, as peças boas pintam e as ruins aparecem em
`NAO ENTENDI: <nome delas>`. Um pixel errado é pior que uma mensagem de erro,
porque quem pintou só descobre depois; uma lista inteira perdida por causa de
uma peça colada é pior que as duas.

### 3. O cliente nunca pinta

O WebSocket é mão única. A única coisa que sai do navegador é um `ping`. Se
alguma coisa nova precisar escrever, ela passa pela API do painel — que só
aceita `localhost`, e que por isso não é alcançável pela audiência.

### 4. O lote é heterogêneo (seção 4)

Despache itens pelo tipo **do item**.

### 5. Todo `id` que o JS procura tem que existir

`ui/js/dom.test.mjs` confere isso: todo `$("id")` e `getElementById("id")` em
`ui/js/*.js` e `control/control.js` existe na página **ou** no HTML que o
próprio JS escreve.

Parece pouco; foram os dois piores bugs do projeto. Um `getElementById`
devolvendo `null` estoura dentro do laço de desenho, o laço morre junto, e a
tela congela. O HUD continua bonito — porque é HTML, não canvas — e o sintoma
parece problema de tamanho. Se você acrescentar um elemento criado por
`innerHTML`, o teste acha. Se procurar por id sem criar, ele acusa.

### 6. O laço de desenho não pode morrer

Qualquer coisa que rode dentro de `quadro()` em `app.js` tem que estar dentro do
`try/catch`. Um erro ali mata o `requestAnimationFrame` para sempre, e ninguém
está olhando o console do OBS às 23h.

### 7. Emoji no Windows: o console mente

O terminal do Windows abre em **cp1252**, e um `print("🎨")` ali levanta
`UnicodeEncodeError` — o programa morreria na primeira linha por causa de
decoração. `main.py :: _preparar_saida()` reconfigura `stdout` e `stderr` para
UTF-8 com `errors="replace"`: o emoji degrada para `?` em vez de derrubar o
servidor. Se você acrescentar um `print` com emoji, ele passa por esse caminho
— **não** tire a chamada.

Do lado da tela não há esse problema: as duas páginas declaram
`<meta charset="utf-8">`, então emoji no HTML, no CSS e no JS é seguro. Os
ícones dos eventos e das cores vivem no `config.json`, que também é UTF-8.

(Se você vir `String.fromCharCode` no `geometry.js`, é outra coisa: monta as
**letras** da coluna, de `A` a `Z`, a partir do índice.)

### 8. Toda borda da grade cai em cima de um pixel do aparelho

O sintoma que originou esta regra: *"alguns quadrado estão com border diferentes
dos outros, tem quadrados com e sem"*.

O `renderer.js` roda com `ctx.scale(dpr, dpr)`. Num monitor de Windows a 125%,
`devicePixelRatio` é **1.25** — fracionário. Um traço de 1px numa coordenada
inteira de CSS cai no **meio** de um pixel do aparelho: metade da tinta num
pixel, metade no vizinho. Uns traços caem em cheio e ficam nítidos; outros se
dissolvem em dois — e como a cor da grade já é quase transparente
(`rgba(255,255,255,0.045)`), os que se dissolvem **somem**.

**A regra:** nenhum desenho da grade usa `origemX + x * celula` direto. Tudo
passa por `bordasDaGrade(grade, dpr)`, que arredonda cada fronteira para o pixel
mais próximo do aparelho. Com `dpr = 1` o arredondamento é a identidade, então
no OBS nada muda.

Consequência prática: as **células pintadas usam as mesmas fronteiras das
linhas**. Se cada uma calculasse o próprio tamanho a partir de `celula`, as duas
contas divergiriam por um pixel e apareceria um fio de fundo entre dois pixels
vizinhos — o desenho da comunidade rachado em quadradinhos soltos.

Vale para qualquer coisa nova que você desenhar no canvas: use `xs[]`/`ys[]`,
nunca a multiplicação.

### 9. A camada de partículas se limpa sozinha

A grade e as partículas são **dois canvas separados**. `renderer.desenhar()`
limpa o canvas da grade; isso não limpa o das partículas — são contextos
diferentes, com contas de backing store diferentes.

O sintoma que originou esta regra: *"os efeito de explosão fica parado um tempão
no pixel e nunca sai"*. Cada faísca que morria continuava acesa na tela para
sempre, e o rastro se acumulava até virar um borrão preso naquele pixel.

**A regra:** `Efeitos.desenhar(ctx)` limpa o **próprio** canvas na primeira
linha, sempre, antes de desenhar qualquer coisa. E limpa em espaço de
**aparelho** (`setTransform(1,0,0,1,0,0)` antes do `clearRect`): com a escala do
dpr ligada, o `clearRect` cobriria só `largura` pixels de um canvas que tem
`largura * dpr`, deixando uma faixa suja na borda direita e embaixo.

Se você criar uma terceira camada, ela precisa fazer o mesmo. Um canvas só se
limpa se alguém mandar.

**A mesma regra vale para o canvas da GRADE.** Ela estava escrita aqui, valendo
só para as partículas, e o `renderer.js` fazia exatamente o que o parágrafo
acima proíbe: `clearRect(0, 0, canvas.width, canvas.height)` **dentro** do
`ctx.scale(dpr, dpr)`. O tamanho do canvas em pixels do aparelho era
multiplicado pelo dpr uma segunda vez.

Com dpr ≥ 1 o retângulo ficava maior que o canvas e o defeito não existia —
por isso ele sobreviveu a 656 testes e a meses de OBS, que roda a dpr 1. Com
dpr **0,625** (zoom de 50% do navegador num monitor de Windows a 125%, que era
como o streamer conseguia ver o quadro inteiro antes do ajuste automático), um
canvas de 675 × 762 só era apagado nos primeiros 422 × 476.

O sintoma não parecia "falta de limpeza" — parecia três defeitos diferentes:

- a faixa de ARCO-ÍRIS saturava na metade direita do quadro, com uma **emenda
  reta** no meio, porque a mescla `lighter` somava de novo a cada quadro;
- os rótulos das colunas apareciam **duplicados** ("AA AA AB AC") porque eram
  redesenhados por cima deles mesmos;
- o fundo não cobria o canvas inteiro, então a borda direita e a de baixo
  mostravam o fundo do palco em vez do fundo do quadro, com uma emenda visível.

O conserto tem duas partes, e as duas importam: o apagador trabalha em espaço
de **aparelho**, e o fundo é pintado em espaço de CSS com `Math.ceil` no
tamanho — porque `canvas.width` foi arredondado na criação e, num dpr
fracionário, pode ficar meio pixel maior que `largura * dpr`. Sem o `ceil`,
essa metade de pixel nunca seria pintada.

`renderer.test.mjs` varre dprs dos dois lados de 1 e cobra o invariante em
pixels do aparelho: **um quadro tem que apagar e repintar o backing store
inteiro**. Um contexto falso que só anota comandos não serviria — a pergunta é
onde cada retângulo cai, e para isso ele precisa carregar a transformação
corrente como um contexto de verdade.

### O mesmo defeito, um andar acima: a medida da arena

O `clearRect` misturava espaço de CSS com espaço de aparelho **dentro** do
renderer. A mesma confusão existia um andar acima, entre o `app.js` e o CSS — e
produzia o sintoma oposto: não sobrava quadro, faltava canvas.

```
getBoundingClientRect()  ->  espaço da TELA   (depois do transform: scale do palco)
canvas.style.width       ->  espaço do PALCO  (antes do transform)
```

Numa janela de 1366 × 768 a escala do palco é 0,4, então a arena mede **3415**
no layout e **1366** na tela. O `ajustar()` media com o rect e escrevia 1366 no
`style.width`: o canvas passava a cobrir 40% da arena, colado na esquerda, com a
grade desenhada num canto de ~9px por célula — *"o grid está minúsculo na tela,
está ocupando só metade da metade"*. O conserto são três linhas:

- o layout vem de `arena.offsetWidth` / `offsetHeight`, que a escala não toca;
- a escala vai junto para o `renderer.redimensionar(largura, altura, escala)`;
- o buffer é `largura * escala * devicePixelRatio` — os pixels que a área
  realmente ocupa na tela.

Esse também é o motivo de `renderer.dpr` **multiplicar** pelo `devicePixelRatio`
em vez de substituí-lo: as duas escalas encolhem pelo mesmo caminho, e é a
`calcularGrade({dpr})` que precisa do produto para escolher uma célula de
pixels inteiros. Sem isso, a célula de 67 no espaço do palco vira 26,8 na tela e
a borda de meio pixel se dissolve em dois — o defeito dos quadrados com e sem
borda voltaria, agora disparado pelo zoom da página em vez do monitor.

---

## 10. Testes

```bash
.venv\Scripts\python.exe -m pytest tests/ -q      # 656 testes
node --test ui/js/*.test.mjs                      # 32 testes da tela
```

**Rode os dois.** O Python não vê o JavaScript, e os dois defeitos mais graves
do projeto viveram exatamente na fronteira entre os dois.

| Arquivo | O que protege |
|---|---|
| `test_coordinates.py` | O parser: as formas aceitas, as recusadas, os limites |
| `geometry.test.mjs` | O mesmo, no JS — e a tabela compartilhada |
| `dom.test.mjs` | Todo id que o JS procura existe |
| `effects.test.mjs` | A camada de partículas é limpa a cada quadro |
| `renderer.test.mjs` | A grade é apagada e repintada **por inteiro**, em qualquer dpr; e o canvas cobre a arena inteira com o palco encolhido |
| `eventos.test.mjs` | Cada efeito desenha, anima, e um evento sem efeito não pinta nada |
| `test_pipeline.py` | O caminho completo: evento entra, pintura sai |
| `test_painting.py` | Cobrança, sobrescrita, cooldown |
| `test_app.py` | A aplicação de ponta a ponta, com um servidor de verdade |
| `test_hub.py` | O lote, os dois baldes, o `hello` antes do registro |
| `test_config.py` | A validação e o `config.json` real do projeto |

**Os testes não fingem.** Os de `test_app.py` sobem uma aplicação FastAPI de
verdade, com WebSocket de verdade, e leem o que ela responde. É a única forma
de pegar um bug que só existe na fronteira — como os dois `Critical` que
passaram despercebidos por 600 testes de unidade.

---

## Onde mexer, por sintoma

| Sintoma | Comece por |
|---|---|
| Um aviso/banner não aparece na tela | `ui/js/app.js :: aoMensagem` e a seção 4 |
| O pixel foi para o lugar errado | `game/coordinates.py` **e** `ui/js/geometry.js` |
| A tela congelou, mas o HUD está bonito | O `try/catch` do `quadro()`, e `dom.test.mjs` |
| Um presente deu pixels errados | `game/rewards.py :: pixels_do_evento` e `rewards.gifts` |
| O ranking não bate com o que você viu | `game/ranking.py` e `Database.top_pintores` |
| O evento automático não sai | `events.catalog` no config, e `SchedulerEventos` |
| O painel recusa uma coordenada válida | O parser do JS — ele recebe o tamanho do canvas |
| Nada acontece ao reiniciar | O servidor não soltou o banco: pare ele antes de apagar |
| **Uns quadrados com borda, outros sem** | `geometry.js :: bordasDaGrade` e `renderer.js`. Veja o invariante 8 |
| **A explosão fica parada no pixel e não sai** | `effects.js :: desenhar` — ele tem que LIMPAR antes. Veja o invariante 9 |
| **Metade do quadro satura / rótulos duplicados** | `renderer.js :: desenhar` — o apagador em espaço de aparelho. Veja o invariante 9 |
| **O palco corta embaixo numa janela pequena** | `style.css :: #palco` (centralizar por posição) e `app.js :: ajustar` |
| **A grade aparece minúscula, num canto** | `app.js :: ajustar` — a arena tem que ser medida com `offsetWidth`, não com `getBoundingClientRect()` |
| **Sobra faixa preta nas laterais** | `geometry.js :: escalaParaCaber` e o `width: var(--largura-projeto)` do `#palco` |
| **Um evento não muda nada na tela** | `eventos.js` e `app.js :: definirEvento` — o `effect` tem que chegar ao `renderer` |
