# 🎨 PIXEL WORLD

**A sua LIVE pinta um quadro. Um pixel por vez, por pessoa.**

Uma grade de 50 × 51 (A–Z, depois AA–AX, linhas 0–50) fica na tela do OBS.
Alguém entra na LIVE, vê
aquele monte de quadradinhos, pergunta *"que porra é essa?"* — e em quinze
segundos está mandando uma rosa e comentando `H5` para escolher onde pintar.
Volta dez minutos depois para ver o que a comunidade desenhou.

Não é um jogo de apostar. Não tem dinheiro, não tem pontos virando dinheiro,
não tem batalha naval. **Tem um quadro em branco e um monte de gente
decidindo junto o que aparece nele.**

---

## Como funciona

```
   🌹 Rose            H5                🎨
  presente aceito → comentário → a coordenada é sua → o pixel entra no quadro
```

1. **A audiência manda presente.** Uma rosa vira 1 pixel. Um Galaxy vira 60.
   Curtidas, seguir e compartilhar também valem pixel.
2. **Escreve a coordenada no chat.** `H5`, `h 5`, `/H5`, `/pixel H5` — o
   parser aceita todas as formas que as pessoas realmente escrevem. E aceita a
   **lista inteira**: `A2, B2, C3` — ou uma por linha — pinta tudo de uma vez,
   com o cooldown contando o comentário e não cada pixel. É assim que alguém
   que mandou um presente grande desenha uma figura em vez de montá-la
   quadrado a quadrado. Uma peça que não dá para ler não derruba o resto: ela
   aparece nomeada em `NAO ENTENDI: <peça>` e as outras pintam.
3. **O pixel entra na hora.** Animação, partícula, brilho, e o nome de quem
   pintou aparece pequenininho em cima. Entrou para o feed.
4. **O quadro é de todo mundo.** Alguém pode pintar por cima do seu pixel —
   e isso **custa o dobro**. Vandalismo tem preço.

Uma cor é sorteada automaticamente para cada pessoa na primeira pintura, e ela
fica. Quem quiser escolher escreve `/cor vermelho` ou `/color #FF0000`.

### Um coração de verdade, para testar

Cem rosas viram cem pixels. Dê a cor, mande as rosas, e cole isto:

```
/cor vermelho
U20,V20,AB20,AC20,T21,U21,V21,W21,AA21,AB21,AC21,AD21,S22,T22,U22,V22,W22,X22,Y22,Z22,AA22,AB22,AC22,AD22,AE22
S23,T23,U23,V23,W23,X23,Y23,Z23,AA23,AB23,AC23,AD23,AE23,T24,U24,V24,W24,X24,Y24,Z24,AA24,AB24,AC24,AD24,U25,V25,W25,X25,Y25,Z25,AA25,AB25,AC25
V26,W26,X26,Y26,Z26,AA26,AB26,W27,X27,Y27,Z27,AA27,X28,Y28,Z28,Y29
```

São 74 células, e sobram 26 pixels.

**No painel, é uma colada só.** O campo de texto aceita várias linhas, então
`Ctrl+V` nas três linhas de coordenadas e *Simular* pinta o coração inteiro de
uma vez — 74 pixels e **um** tique de cooldown. As três linhas são um
comentário: o `\n` separa coordenada igual à vírgula.

**Na LIVE de verdade, três comentários.** Não é o jogo que não aceita: um
comentário do TikTok cabe em ~150 caracteres e a lista inteira tem 321. Cada
linha acima cabe, e cada uma é uma jogada — dois segundos entre uma e outra. O
`/cor vermelho` é um comentário à parte, e ele não pinta nada: só troca a cor.
O desenho aparece assim:

```
     ████     ████
   ████████ ████████
  ██████████████████
  ██████████████████
   ████████████████
    ██████████████
     ██████████
       ██████
         ██
```

O cooldown de 2 segundos vale por **comentário**, não por pixel: cada bloco
acima é uma jogada só. Colar os três de uma vez faz os dois últimos levarem
`CALMA! ESPERE 2 SEGUNDOS` — sem custar nada, e é só repetir.

### As regras que fazem a coisa funcionar

| Regra | Por quê |
|---|---|
| **1 presente = 1 pixel** | A conta que a audiência faz de cabeça. |
| **Pintar em pixel virgem custa 1; por cima de outro, 2** | Destruir o desenho alheio custa o dobro de colaborar. |
| **A coordenada tem que ser exata** | Se o parser não entender, ele **recusa**. Pintar o pixel errado é pior que mostrar um erro. |
| **A cor é estável por pessoa** | Depois de três pinturas, a audiência reconhece quem é quem pela cor. |
| **Cooldown de 2s por pessoa** | Sem isso, um script pinta o quadro inteiro sozinho. |

---

## Rodando

Precisa de Python 3.12+ e de um `config.json` (já vem pronto no repositório).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

### Ensaie primeiro — sem LIVE, sem presente, sem plateia

```bash
python main.py --test
```

O **MODO TESTE** troca a conexão do TikTok por um simulador e abre o painel em
`http://localhost:8000/control`. Ali você inventa uma rosa, comenta `H5` e vê o
pixel aparecer de verdade — mesmo pipeline, mesma fila, mesmas regras. O que
muda é só quem entrega a encomenda.

Vale a pena ensaiar sempre. O momento de descobrir que o canvas não caberia na
tela não é com 300 pessoas assistindo.

### Agora ao vivo

Troque o usuário no `config.json`:

```json
"tiktok": { "username": "@seu_perfil" }
```

E suba:

```bash
python main.py
```

A conexão é somente leitura: o jogo **escuta** a LIVE, nunca escreve nela. Não
existe risco de a sua conta postar ou interagir sozinha.

### Opções

| Flag | O que faz |
|---|---|
| `--test` | MODO TESTE: simulador no lugar da LIVE, sem exigir `@usuario` |
| `--config CAMINHO` | Usa outro arquivo de configuração |
| `--porta 9000` | Sobrepõe a porta do config |
| `--burst 2000` | Enfileira 2000 eventos falsos na largada, para medir carga |
| `--headless` | Não abre o navegador |

---

## Colocando no OBS

O jogo já sai pronto para 9:16. Não há layout alternativo escondido atrás de um
breakpoint: a **altura** do palco é medida de projeto — 1920 — e a **largura**
é a que a janela pedir. Cabeçalho, arena e rodapé são frações dessa altura, então
a composição que você ensaiou é a que vai ao ar em qualquer tamanho de janela.

**A página preenche a janela sozinha. Não use o zoom do navegador.** Numa janela
de 1366 × 768 não sobra faixa preta em lugar nenhum e nada é cortado: o palco
escala para caber na altura, e a largura que sobra vira **arena**, com a grade
centralizada nela. Dar zoom out *por cima* disso continua funcionando, mas
encolhe o quadro sem motivo — o ajuste já é automático.

> Isto é uma diferença real em relação às primeiras versões. O `--escala` que faz
> o encolhimento existia no CSS desde o começo e **ninguém escrevia nele**, então
> o palco ficava nos 1080 × 1920 nominais para sempre e a única forma de ver o
> quadro todo numa tela menor era dar zoom out.

**Numa janela vertical a grade fica bem maior.** A grade é 50 × 51, quase
quadrada, e quem manda no tamanho da célula é a **altura**: cada linha é
`altura_da_arena ÷ 51`. Numa janela vertical (9:16, ou qualquer coisa perto
disso) a arena fica alta e a grade usa ~93% da largura disponível. Numa janela
deitada a arena fica baixa e larga, e a grade para no limite da altura — ela
continua inteira e centralizada, só sobra espaço nas laterais. Para a grade
grande, compartilhe uma janela vertical.

1. **Fontes → + → Navegador**
2. URL: `http://localhost:8000/`
3. Largura **1080**, altura **1920**
4. Marque **Desligar o áudio** (a página não emite som nenhum)
5. Marque **Atualizar o navegador quando a cena ficar ativa**

A tela se reconecta sozinha se a rede cair. Você pode deixar essa fonte aberta
por dias.

**A composição, de cima para baixo:** título e status da conexão → o canvas com
as coordenadas nas marginais → o banner do evento → a barra de progresso → o
ranking e o feed lado a lado → a instrução de como participar.

---

## Os eventos da LIVE

De tempo em tempo o jogo anuncia alguma coisa e **multiplica os pixels** por
alguns segundos. É o que mantém a tela viva quando ninguém está mandando nada
— e o que dá a quem está só olhando um motivo para mandar a próxima rosa
(*"faltam 8 segundos de TURBO"*).

**Uma coisa só define um evento: o multiplicador.** Durante a janela, os
pixels que a audiência ganha por mandar presente, curtir, seguir ou
compartilhar são multiplicados. O multiplicador **não** barateia o custo de
pintar nem o preço de pintar por cima de alguém — pintar custa 1 (ou 2, por
cima) a vida inteira, com ou sem evento no ar.

### Os cinco do catálogo

| Evento | Duração | Multiplicador | Sorteio | O que é |
|---|---|---|---|---|
| ⚡ **PIXEL TURBO** | 30s | **×3** | 30% | A rosa vira 3 pixels. O mais generoso e o mais curto: a decisão é agora ou nunca. |
| 🎨 **HORA DO PIXEL** | 30s | **×2** | 30% | A mesma pressa do TURBO com metade do prêmio. É o que acontece com mais frequência, e a audiência já sabe o que fazer quando ele chega. |
| 🌈 **ARCO-ÍRIS** | 60s | ×1 | 20% | A janela mais longa, **sem bônus nenhum**. Um minuto para a comunidade desenhar com calma. |
| 💥 **CAOS** | 20s | **×1,5** | 10% | Vinte segundos de bagunça. Curto demais para combinar qualquer coisa — e é esse o ponto. |
| 🎯 **DESAFIO** | 45s | ×1 | 10% | Quarenta e cinco segundos para a comunidade se organizar e terminar algo junto. |

O **sorteio** é o peso de cada um na escolha. Somando 10, sai um evento a cada
3 minutos em média (`interval: 180`), e o primeiro chega 75 segundos depois de
o servidor subir (`first_after: 75`). O relógio só começa a contar de novo
depois que o evento **termina** — um ARCO-ÍRIS de 60s empurra o próximo para
60s + 180s.

O banner no telão mostra o emoji, o nome, e `PIXELS x3` — ou `PINTE AGORA`
quando o multiplicador é 1. Abaixo dele, o contador e a barra andando. Quem
faz a audiência correr é a barra.

### 🌈 tem dois: o evento e a cor

Os dois se chamam ARCO-ÍRIS, usam o mesmo emoji, e não têm nada a ver um com o
outro. Vale saber a diferença antes de procurar defeito:

| | 🌈 o **evento** | 🌈 a **cor especial** |
|---|---|---|
| Quem aciona | o agendador sozinho, ou o painel à mão | a pessoa, escrevendo `/cor arco-iris` |
| O que muda | quantos pixels cada presente rende | só a aparência do pixel que ela pintar |
| Quanto dura | 60 segundos | para sempre — o pixel fica no quadro |
| Dá vantagem? | **não**, o multiplicador dele é 1 | nenhuma, cor é cosmética |

Quem quer bônus de verdade está olhando para o **PIXEL TURBO**. O ARCO-ÍRIS
não é um evento de prêmio: é um convite longo para desenhar.

### O que cada evento faz NA TELA

Dos cinco, três mexem no quadro — não só no banner. O `effect` que o servidor
manda no `event_start` virou desenho:

| Evento | O que aparece por cima da grade |
|---|---|
| 🌈 **ARCO-ÍRIS** | Sete faixas de cor atravessam o quadro devagar, da esquerda para a direita, girando a matiz enquanto andam. Ficam dentro da moldura: os rótulos das colunas continuam legíveis. |
| 💥 **CAOS** | O quadro inteiro treme — a grade **e** tudo que já foi pintado nela, até 3px para os lados — e leva um clarão rosa pulsando por cima. É o único que mexe no enquadramento. |
| 🎯 **DESAFIO** | Um alvo amarelo fecha no centro do quadro, de novo e de novo, a cada 2,4s. |
| ⚡ **PIXEL TURBO** | Nada por cima da grade: o que muda é o multiplicador. |
| 🎨 **HORA DO PIXEL** | Idem. |

**Só o CAOS move a grade.** Um tremor grande demais esconderia o desenho da
comunidade — o único motivo de a tela existir — então ele anda 3px, e o
deslocamento é arredondado para o pixel inteiro: um tremor fracionário borraria
a grade toda no meio do efeito. Os outros dois desenham *por cima*, sem mexer
em nada do que já está lá.

Um arco-íris **fora** de evento continua existindo: é a cor especial `/cor
arco-iris`, na seção seguinte.

---

## As cores especiais

Toda pessoa ganha uma cor automática na primeira pintura, sorteada do próprio
nome e sempre a mesma (ver `crc32` em [Decisões](#decisões-que-valem-explicar)).
Quem quiser escolher escreve no chat:

```
/cor vermelho      uma das 8 da paleta
/color #FF0055     qualquer hexadecimal
/cor arco-iris     uma das 6 especiais, com brilho próprio
```

Também aceita sem a barra (`vermelho`, `arco-iris`), com ou sem acento, e com
espaço ou hífen no lugar do `_` — `ARCO-ÍRIS`, `arco iris` e `arco_iris` são a
mesma coisa, de propósito. A lista vive em `canvas.especiais` no `config.json`.

| Cor | Como escrever | Cor de partida |
|---|---|---|
| 🌈 ARCO-ÍRIS | `arco-iris` | `#FF00E5` |
| 🔥 FOGO | `fogo` | `#FF6A00` |
| ⚡ ELÉTRICO | `eletrico` | `#00E5FF` |
| 🌌 GALÁXIA | `galaxia` | `#7B2FFF` |
| ✨ NEON | `neon` | `#39FF14` |
| 💎 DIAMANTE | `diamante` | `#7DF9FF` |

### O que "especial" muda na tela

Menos do que o nome sugere, hoje. Um pixel especial ganha **uma faixa clara no
topo** e solta **26 faíscas** ao ser pintado, contra 14 de um pixel comum. As
seis se comportam igual — o que muda entre elas é só a cor de partida.

A cor de partida existe por um motivo prático: um navegador que não anime nada
precisa mostrar *alguma* coisa naquele pixel. Sem ela, o pixel especial ficaria
invisível, e a pessoa acharia que o comando não funcionou.

### `desbloqueio` ainda não está ligado

Cada cor especial traz um número em `canvas.especiais.<cor>.desbloqueio` — de
250 (FOGO, ELÉTRICO) a 1000 (DIAMANTE). **Nada no código lê esse campo.**
Qualquer pessoa escolhe qualquer especial desde a primeira pintura.

Ele está no config como o lugar onde a conquista vai entrar quando existir. Não
é uma promessa quebrada, é um campo esperando o dono.

---

## Configurando

**Tudo** o que dá para afinar vive em `config.json`. Nada de número mágico no
meio do código.

### O canvas pode crescer

```json
"canvas": { "cols": 50, "rows": 51 }
```

Trocar para `100 × 100` é **só isso**. As células encolhem e o desenho continua
cabendo na tela — o tamanho da célula é calculado, nunca fixo.

Hoje são 50 colunas, e o motivo é o quadro: com 26 a grade virava uma tira
estreita no meio de 1080px, com duas faixas mortas de ~200px de cada lado.
Com 50 ela ocupa a largura inteira e ainda sobra altura.

Colunas vão de `A` até `ZZ` (702). A partir de `AA` a coordenada tem duas
letras — e o rótulo na tela encolhe sozinho para as duas caberem na célula,
porque ninguém consegue comentar uma coluna que não consegue ler. Acima de
`ZZ` o rótulo deixa de ser algo que uma pessoa digita sem errar, e o servidor
recusa a configuração.

### Quanto vale cada presente

```json
"rewards": {
  "pixel_custo": 1,
  "sobrescrita_custo": 2,
  "gifts": { "Rose": 1, "Galaxy": 60, "Lion": 300 }
}
```

Presente que não está na lista vale `presente_desconhecido` (1 por padrão) —
o TikTok lança presente novo toda semana e é melhor dar 1 pixel do que travar.

### Os eventos automáticos

O que cada evento faz está em [Os eventos da LIVE](#os-eventos-da-live).
Aqui é só como mexer neles.

```json
"events": {
  "active": true,
  "interval": 180,
  "first_after": 75,
  "catalog": [
    { "key": "pixel_turbo", "name": "PIXEL TURBO", "emoji": "⚡",
      "duration": 30, "multiplier": 3.0, "weight": 3.0, "effect": null }
  ]
}
```

| Chave | O que é |
|---|---|
| `catalog[].weight` | O peso no sorteio. `0` tira o evento do rodízio sem tirá-lo do painel. |
| `catalog[].multiplier` | Quantos pixels cada presente rende durante a janela. |
| `catalog[].duration` | Quantos segundos ele dura. |
| `catalog[].effect` | O nome do efeito visual. **Viaja até a tela e ninguém desenha ainda** — ver acima. |
| `interval` | Segundos de silêncio entre o fim de um evento e o sorteio do próximo. |
| `first_after` | Segundos entre o servidor subir e o primeiro evento. |
| `active: false` | Desliga o **sorteio**. Forçar pelo painel continua valendo, para você poder voltar atrás sem reiniciar o servidor no meio da LIVE. |

Acrescentar um evento é acrescentar um item na lista — o banner, o sorteio e o
botão do painel saem dali sozinhos. O `key` é o nome que o painel manda em
`POST /api/evento`.

### O resto

| Seção | Para quê |
|---|---|
| `app` | Título, caminho do banco, tamanho do feed, quantos eventos por quadro |
| `server` | Host, porta, e o intervalo do laço do jogo (`frame_ms`) |
| `xp` | Quanto XP vale uma pintura e como a curva de nível sobe |
| `limits` | Teto da fila e teto de pixels por evento |

Configuração inválida **não sobe**. O erro diz exatamente qual chave corrigir.

---

## Os níveis

| Nível | Título | Pixels |
|---|---|---|
| 1 | Novato | 1+ |
| 5 | Pintor | |
| 10 | Artista | |
| 20 | Mestre | |
| 30 | Pixel Master | |
| 50 | **Lenda** | |

XP: 10 por pixel pintado, 15 por pintar por cima de outro. O ranking mostra os
cinco maiores ao vivo, e o `\api\estado` guarda os 500 primeiros.

---

## O painel de controle

`http://localhost:8000/control` — **não vai ao ar**, é a sua bancada:

- **Simular evento** — comentário, presente, curtida, seguidor,
  compartilhamento. Entra na *mesma fila* que a LIVE usa: o que você vê aqui é
  o jogo de verdade, só o carteiro é falso.
- **Pixels de alguém** — crava o saldo de quem mandou presente e o sistema
  perdeu. Repare que é **cravar**, não somar: clicar duas vezes em 50 deixa 50.
- **Eventos** — força um evento agora.
- **Inspecionar pixel** — quem pintou, quando, e tudo que já passou por ali.
  Apagar devolve a célula ao estado virgem; o histórico permanece.
- **Limpar o quadro** — apaga **todos** os pixels e mata as animações na tela,
  sem parar o servidor. Pede confirmação e diz quantos pixels vão embora,
  porque não tem volta. O **ranking e o histórico ficam**: limpar o quadro é
  apagar o desenho, não a participação de quem mandou rosa a LIVE inteira.
- **Rajada** — dispara centenas de eventos de uma vez para medir o teto.

O painel só consegue escrever em `localhost`. Não existe CORS configurado, e
essa ausência **é** o controle de segurança: uma página qualquer que você abrir
no navegador não consegue falar com o seu jogo.

---

## Como o código está organizado

```
main.py              Sobe tudo. Não tem regra de jogo nenhuma.

game/                As regras. Puro, sem rede, sem banco, sem relógio.
  coordinates.py       "H5" → (7, 5). E recusa o que não entende.
  canvas.py            A grade e suas células.
  colors.py            Cor automática por pessoa + paleta + cores especiais.
  inventory.py         Quantos pixels cada um tem.
  painting.py          Pintar, cobrar, sobrescrever.
  pipeline.py          Evento do TikTok → o que acontece no jogo.
  rewards.py           Presente → quantos pixels.
  xp.py  ranking.py    Progressão e placar.
  events.py            Os eventos automáticos da LIVE.

tiktok/              A fronteira com o mundo.
  adapter.py           TikTokLive → fila de eventos. Reconecta sozinho.
  simulado.py          O MESMO contrato, inventando os eventos.

backend/             Rede e persistência.
  app.py               FastAPI, WebSocket, as páginas.
  estado.py            A raiz de composição: quem monta o quê.
  hub.py               Fan-out do WebSocket, em lotes por quadro.
  database.py          SQLite (WAL). Canvas, pixels, histórico, ranking.
  control.py           A API do painel.

core/                O que serve a todos.
  config.py            Lê, mescla e VALIDA o config.json.
  event_queue.py       Fila com teto e descarte do mais velho.
  ratelimit.py         Cooldown e orçamento de ações.
  events.py            Os tipos de evento.

ui/                  A tela que vai ao ar (1920 de altura, largura fluida).
control/             O painel do operador.
```

**A regra de dependência:** `game/` não importa `tiktok/`, `backend/` nem
`core/`. Consequência prática: dá para testar a economia inteira sem subir
servidor, sem abrir socket e sem esperar.

**Para mexer no código**, o [`DOCUMENTACAO.md`](DOCUMENTACAO.md) explica o
caminho de um evento do comentário até o pixel, o protocolo do WebSocket, o
banco, cada chave do config, receitas ("como acrescentar um presente") e os
invariantes que não podem cair. Comece por lá.

---

## Decisões que valem explicar

**O cliente nunca pinta.** O WebSocket é mão única — a única coisa que sai do
navegador é um `ping`. Pintura nasce de um evento do TikTok ou do painel. É o
que impede alguém de abrir o endereço do streamer e desenhar de graça.

**O parser recusa em vez de adivinhar.** `A51` não é "quase H5". Se a peça não
vira uma célula exata, ela não é pintada — `H5extra` nunca vira `H5`. Um pixel
errado é pior que uma mensagem de erro, porque quem pintou só descobre depois.

**A dureza é da peça, não da lista.** Ela já foi das duas, e a segunda estava
errada. O campo do painel tinha uma linha só, e um `<input>` de uma linha cola
texto de várias linhas **grudado**: a receita do coração em três linhas chegava
como `...AE22S23...`, uma "coordenada" impossível, e a regra antiga jogava fora
as outras 72 células. A tela dizia só `NÃO ENTENDI` — e quem colou a receita e
viu zero pixel não conclui "digitei errado", conclui que não funciona. Hoje a
peça ilegível é **denunciada pelo nome** (`NAO ENTENDI: AE22S23`) e o resto
pinta. Metade do desenho era o pior desfecho enquanto ninguém sabia qual
metade; com o nome dela na tela, é o melhor.

**O cooldown é do comentário, não do pixel.** Quem manda um presente grande e
escreve `A2, B2, C3` está fazendo *uma* jogada. O limite de 2 segundos existe
para uma pessoa não monopolizar o quadro — não para racionar pixel que ela já
pagou. O relógio bate uma vez por comentário, e só quando um pixel entra de
verdade: quem foi recusado por falta de saldo continua com a vez na mão.

**O teto do streak ficava escondido.** `base × min(quantidade, teto)`: o teto é
do *streak*, não do presente. Ele morava só como constante no código, nunca
tinha chegado ao `config.json`, então valia 10 em silêncio — cem rosas pagavam
o mesmo que dez. Agora está no arquivo, em 100, e um teste lê o `config.json`
de verdade para garantir que ele não suma de novo.

**Escrever no banco é em lote.** Uma LIVE com 300 pessoas não pode custar 300
`INSERT` por segundo. O SQLite roda em WAL e as pinturas são agrupadas por
quadro.

**A fila tem teto.** Se a LIVE viralizar, a fila descarta os eventos mais
antigos em vez de crescer até derrubar o servidor. Perder um comentário antigo
é aceitável; perder a transmissão não.

**A cor de cada pessoa vem de `crc32`, não de `hash()`.** O `hash()` do Python
é aleatorizado a cada processo — a cor de todo mundo trocaria a cada
reinicialização, e a audiência perderia a única referência visual que tem.

**A grade desenha em pixel de aparelho, não de CSS.** Num monitor de Windows a
125%, `devicePixelRatio` é 1.25. Um traço de 1px numa coordenada inteira de CSS
cai no meio de um pixel do aparelho e se dissolve em dois — e como a cor da
grade é quase transparente, os traços que se dissolvem somem. Era isso que
fazia uns quadrados terem borda e outros não. Toda fronteira passa por
`bordasDaGrade()`, que arredonda para o pixel mais próximo; no OBS (onde o
`dpr` é 1) o arredondamento é a identidade e nada muda.

**Cada canvas se limpa.** A grade e as partículas são camadas separadas, com
contextos separados. Limpar uma não limpa a outra — e uma faísca que morre sem
alguém apagar o canvas continua acesa na tela para sempre. Foi assim que a
explosão ficou "parada no pixel".

**A coordenada é impressa em âmbar, e o resto da tela é frio.** O quadro é
ciano, rosa e azul; a régua em volta dele — as letras das colunas, os números
das linhas — sai numa tinta quente, `#ffc14d`, que não aparece em mais nada
além de coordenada e medida (o `H5` do feed, a escala no cabeçalho, a barra de
progresso). É a regra de carta topográfica: o terreno numa cor, a grade de
referência em outra, e ninguém confunde a margem com o desenho. A régua tem
traço comprido de cinco em cinco, para quem conta de cabeça não se perder entre
`F` e `K`. Veja o invariante 9 em `DOCUMENTACAO.md`.

**O console do Windows não aguenta emoji, a tela aguenta.** O terminal abre em
cp1252 e um `print("🎨")` o derrubaria; `main.py` reconfigura a saída para UTF-8
e o emoji degrada para `?` em vez de matar o servidor. Já as páginas são UTF-8
declarado, então emoji no HTML, no CSS e no `config.json` é para usar sem medo.

---

## Problemas comuns

| Sintoma | O que é |
|---|---|
| `tiktok.username ainda e o placeholder` | Troque o `@` no config.json ou rode com `--test` |
| Conecta mas não acontece nada | O `@` está certo? A LIVE está no ar *agora*? |
| Não pinta e mostra erro | A coordenada não existe, ou faltam pixels. O aviso diz qual. |
| `NAO ENTENDI: <pedaço>` no painel | O aviso nomeia a peça ilegível; o resto da lista pinta. Colar as linhas de uma receita num `<input>` de uma linha gruda `AE22` com `S23` — o campo do painel é de várias linhas justamente por isso |
| Colei a receita e faltou um pixel na quebra de linha | Duas células coladas viram uma peça só, e ela não dá para desfazer. O aviso diz o nome dela: apague e repita só aquela |
| Pixel não aparece na tela do OBS | Recarregue a fonte. A pílula no topo diz `AO VIVO`? |
| Canvas borrado no OBS | Confira 1080 × 1920 na fonte de navegador |
| Uns quadrados com borda, outros sem | Escala do Windows a 125% (`devicePixelRatio` fracionário) — o desenho tem que passar por `bordasDaGrade()` |
| `/cor arco-iris` pinta, mas não faz arco-íris | É a **cor especial**: um rosa-choque estático. Quem atravessa o quadro são as faixas do **evento** ARCO-ÍRIS — ver [As cores especiais](#as-cores-especiais) |
| A grade quebra / uns quadrados maiores | Não dê zoom out. A página já ajusta o palco sozinha para preencher a janela — ver [Colocando no OBS](#colocando-no-obs) |
| Janela pequena corta o rodapé | Era o palco de 1920px pendurado fora da janela. Hoje ele escala para caber na altura; se ainda corta, recarregue a página |
| A grade aparece minúscula, num canto da tela | O canvas foi dimensionado pelo `getBoundingClientRect()` da arena, que devolve o tamanho **depois** do `transform: scale()` do palco. O canvas é posicionado no espaço *antes* da escala — ver `ui/js/app.js :: ajustar()`. Recarregue; se persistir, é código antigo em cache |
| ARCO-ÍRIS não deu bônus nenhum | Correto: o multiplicador dele é **1**. São 60s de janela para desenhar, não um prêmio. Bônus é o PIXEL TURBO |
| Escolhi uma cor especial e ninguém me barrou | `desbloqueio` ainda não está ligado: qualquer pessoa escolhe qualquer especial desde a primeira pintura |
| Quero recomeçar do zero | **Limpar o quadro** no painel (o ranking fica), ou apague o `pixelworld.db` com o servidor parado |

---

## Testes

```bash
.venv\Scripts\python.exe -m pytest tests/ -q      # 656 testes
node --test ui/js/*.test.mjs                      # 32 testes da tela
```

A geometria da tela é testada porque ela e o backend precisam concordar sobre o
que é `H5`. Se divergirem, a pessoa comenta `H5` e o pixel aparece em outro
lugar — e não existe bug pior neste projeto que esse. A lista de formas
aceitas (`H5`, `h5`, `H 5`, `H-5`, `/p H5`…) é **a mesma** nos dois arquivos de
teste, de propósito, e o painel do operador chama o parser passando o tamanho
do canvas para responder igual ao backend até nos casos de limite.

A **lista** é a única coisa que o Python entende e o JS não — e é deliberado. O
único lugar do painel que chama o parser do JS é o campinho *Inspecionar pixel*,
que pergunta por *uma* célula. Quem manda texto para o jogo manda o comentário
cru para o Python. Se o painel um dia precisar validar uma lista antes de
enviar, o espelho tem que crescer junto.

`dom.test.mjs` confere que todo `id` que o JavaScript procura existe: na
página, ou no HTML que ele mesmo escreve. Parece pouco, mas dois defeitos
graves nasceram aí — um `getElementById` devolvendo `null` estoura dentro do
laço de desenho, e o laço morre junto. A tela congela parecendo problema de
tamanho, e o HUD continua bonito porque é HTML, não canvas.

---

Feito para rodar por dias sem ninguém olhando o terminal.
