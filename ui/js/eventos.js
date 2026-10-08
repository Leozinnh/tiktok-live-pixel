/**
 * O desenho dos eventos da LIVE.
 *
 * O servidor manda, no `event_start`, um campo `effect`. Ele chegava inteiro
 * no navegador desde o primeiro dia e ninguem lia: um evento que so muda o
 * multiplicador nao se ve, e o que faz a audiencia perceber que algo esta
 * acontecendo e a TELA mudar.
 *
 * Sao dois tipos de efeito, e a diferenca decide onde cada um mora:
 *
 * - o ENFEITE por cima do quadro — o glitch do CAOS, a mira do DESAFIO, os
 *   riscos do PIXEL TURBO e a festa da HORA DO PIXEL — e desenhado aqui, e
 *   quem chama e o `renderer.desenhar`;
 * - o efeito de CELULA — o ARCO-IRIS e o feixe do BRILHO — troca a COR das
 *   celulas ja pintadas, e quem pinta celula e o renderer. Aqui moram so as
 *   contas de cor (`corDaCelula`).
 *
 * A regra que separa os dois: o enfeite decora a TELA, o efeito de celula
 * muda o DESENHO. Quando os dois disputam o mesmo pixel, quem decide e o que
 * a audiencia precisa ver — e o que ela pagou para ver e o desenho. Por isso
 * o ARCO-IRIS deixou de ser uma faixa passando por cima: a faixa tapava os
 * quadrados que a sala acabou de comprar.
 *
 * O BRILHO e os dois ao mesmo tempo, e nao contradiz a regra: o feixe acende
 * as celulas pintadas, e a festa (moldura + chuva de pixels dourados) toma a
 * tela. O feixe sozinho nao bastava — ele so existe onde alguem JA pintou, e
 * num quadro vazio a HORA DO PIXEL era so o banner.
 *
 * Tudo aqui e desenhado por cima da grade, no MESMO canvas: um terceiro canvas
 * so para o enfeite custaria mais memoria do que o enfeite inteiro. E nada
 * aqui pode ser caro — sao poucos retangulos por quadro, ao lado das celulas
 * que ja sao redesenhadas 60 vezes por segundo.
 *
 * O tempo entra por parametro (`t`, em segundos). Nada aqui le o relogio: e o
 * que permite testar a animacao sem esperar por ela. E nada aqui usa
 * `Math.random`: um enfeite que sorteia a propria forma a cada quadro nao
 * teria como ser testado, e um tremor sorteado na hora piscaria diferente em
 * cada captura do OBS. O sorteio e deterministico — `ruido(n)` da sempre o
 * mesmo numero para o mesmo `n` —, e quem avanca o "sorteio" e o tempo.
 */

import { hexParaRgb } from "./effects.js";

/** Quanto a tela do CAOS anda para os lados, no maximo, em pixels de CSS. */
const TREMOR_MAXIMO = 3;

/**
 * De quantos em quantos graus a matiz gira de uma celula para a vizinha.
 *
 * 12 graus: a travessia do quadro (x + y vai de 0 a ~50) cobre quase duas
 * voltas da roda de cor. A diagonal inteira vira um arco-iris de verdade —
 * varias cores visiveis ao mesmo tempo, que e o que o nome do evento promete —
 * em vez de um borrao de duas cores.
 */
const MATIZ_POR_CELULA = 12;

/**
 * Quantos graus a roda gira por segundo.
 *
 * 30 graus por segundo dao uma volta completa em 12 segundos, e cada celula
 * troca de cor nesse ritmo. E a velocidade da faixa antiga: ela atravessava o
 * quadro em 14 segundos com sete cores, o que da ~26 graus por segundo num
 * ponto parado da tela. O evento dura 60: a roda gira cinco vezes.
 */
const MATIZ_POR_SEGUNDO = 30;

/** A que velocidade a faixa do BRILHO atravessa o quadro, em celulas/s. */
const VELOCIDADE_DO_BRILHO = 9;

/**
 * Quantas celulas a faixa do BRILHO cobre, do centro para cada lado.
 *
 * Oito: numa celula de ~40px a faixa sai com uns 640px de largura — larga o
 * bastante para o olho ver um feixe de luz, e estreita o bastante para caber
 * mais de um no quadro e dar para acompanhar a travessia.
 */
const LARGURA_DO_BRILHO = 8;

/**
 * Quantas celulas a faixa do BRILHO viaja antes de reentrar.
 *
 * Maior que a travessia do quadro de proposito: depois de cruzar o desenho a
 * luz sai de cena, deixa alguns segundos de pausa, e volta. Uma luz que
 * reentra imediatamente viraria um ventilador girando; a pausa e o que faz a
 * chegada da proxima faixa ser um acontecimento.
 */
const CICLO_DO_BRILHO = 80;

/** A cor da luz na HORA DO PIXEL: branco quente, de sol batendo. */
const OURO = "#fff1c2";

/** O quanto a celula sob a faixa se aproxima da luz, no ponto mais forte. */
const FORCA_DO_BRILHO = 0.8;

/** Quantos riscos de velocidade cruzam o quadro no PIXEL TURBO. */
const RASTROS_DO_TURBO = 8;

/**
 * Quantos pixels dourados caem ao mesmo tempo na HORA DO PIXEL.
 *
 * Vinte e dois: num quadro de ~25 colunas da cerca de um pixel por coluna, e
 * a chuva fica presente sem virar cortina — ela cobre a tela, mas nao a ponto
 * de esconder o desenho, que foi o erro da faixa antiga do ARCO-IRIS.
 */
const DESTELOS_DO_BRILHO = 22;

/** As cores da chuva, na familia do OURO: amarelo, branco quente e ambar. */
const CORES_DO_DESTELO = ["#ffd93d", "#fff1c2", "#ffb02e"];

/** A grossura da moldura acesa da HORA DO PIXEL, em pixels de CSS. */
const MOLDURA_DO_BRILHO = 8;

/**
 * Um numero estavel entre 0 e 1 a partir de um inteiro.
 *
 * E o "sorteio" deste arquivo: `ruido(3)` da sempre o mesmo numero. O seno de
 * um numero grande oscila o suficiente para o resultado nao ter padrao
 * visivel, e o fracionario espreme a oscilacao no intervalo 0..1.
 */
function ruido(n) {
  const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return s - Math.floor(s);
}

/**
 * A cor de uma celula pintada enquanto o ARCO-IRIS esta no ar.
 *
 * O modo antigo pintava uma FAIXA por cima do quadro, e a faixa tapava o
 * desenho: a audiencia via um retangulo colorido passando de um lado para o
 * outro, e nao o pixel que tinha acabado de pagar. Agora quem muda de cor sao
 * as celulas JA pintadas — o desenho da comunidade vira o arco-iris, e o
 * quadro vazio continua escuro.
 *
 * A matiz vem de (x + y) e nao da ordem em que pintaram: o `Map` do renderer
 * guarda as celulas na ordem de chegada, e duas vizinhas pintadas com uma hora
 * de diferenca sairiam com cores distantes — um chuvisco, nao um arco-iris.
 * Pela posicao, a cor acompanha o chao: bandas diagonais deslizando.
 *
 * Devolve HEX e nao `hsl()`: quem desenha a celula ainda passa esta cor por
 * `clarear` e `rgba` (o brilho do efeito e o fio de cima), e as duas funcoes
 * so sabem ler hex — um `hsl()` aqui viraria branco nas duas.
 */
export function corDoArcoIris(x, y, t = 0) {
  const matiz =
    ((((x + y) * MATIZ_POR_CELULA + t * MATIZ_POR_SEGUNDO) % 360) + 360) % 360;
  return matizParaHex(matiz);
}

/**
 * A cor de uma celula pintada enquanto o BRILHO (HORA DO PIXEL) esta no ar.
 *
 * A HORA DO PIXEL e a hora dourada: um feixe de luz atravessa o quadro na
 * diagonal, e as celulas que ele alcanca pegam sol — a cor que a pessoa
 * escolheu continua ali, so que banhada. A faixa de luz e a mesma ideia do
 * ARCO-IRIS (mexe na cor do que esta pintado, nunca por cima), com o efeito
 * oposto: la a cor gira, aqui ela ACENDE.
 *
 * A posicao `x + y` e a mesma do arco-iris de proposito: a luz caminha na
 * mesma diagonal das bandas de cor, entao os dois eventos leem como o mesmo
 * quadro sendo iluminado de jeitos diferentes.
 *
 * Devolve HEX pelo mesmo motivo de `corDoArcoIris`.
 */
function corDoBrilho(x, y, t, cor) {
  const posicao = (t * VELOCIDADE_DO_BRILHO) % CICLO_DO_BRILHO;
  const distancia = Math.abs(x + y - posicao);

  if (distancia >= LARGURA_DO_BRILHO) return cor;

  // A forca cai do centro da faixa para as bordas: a luz tem um miolo aceso e
  // vai morrendo nas beiradas, em vez de acender e apagar de um quadro para o
  // outro — que pareceria defeito, nao amanhecer.
  const forca = 1 - distancia / LARGURA_DO_BRILHO;
  return misturar(cor, OURO, FORCA_DO_BRILHO * forca);
}

/**
 * A cor com que UMA celula pintada deve sair neste quadro.
 *
 * E o unico ponto por onde o renderer pergunta a cor — ele nao sabe (nem
 * precisa saber) quais efeitos trocam a cor das celulas. Com um efeito que
 * nao mexe em celula (ou sem evento nenhum) a cor volta INTACTA: a conta e
 * identidade, e quem pinta paga so uma comparacao de string.
 */
export function corDaCelula(efeito, x, y, t, cor) {
  if (efeito === "arco_iris") return corDoArcoIris(x, y, t);
  if (efeito === "brilho") return corDoBrilho(x, y, t, cor);
  return cor;
}

/** Duas cores misturadas em `quanto` (0 = a primeira, 1 = a segunda), em hex. */
function misturar(hexA, hexB, quanto) {
  const a = hexParaRgb(hexA);
  const b = hexParaRgb(hexB);
  const canal = (va, vb) =>
    Math.round(va + (vb - va) * quanto)
      .toString(16)
      .padStart(2, "0");
  return `#${canal(a.r, b.r)}${canal(a.g, b.g)}${canal(a.b, b.b)}`;
}

/**
 * HSL com saturacao cheia e 62% de luz, em `#rrggbb`.
 *
 * 62% de luz e a mesma tinta da faixa antiga (`hsla(..., 100%, 62%)`): cor de
 * LED, saturada o bastante para sobreviver ao encode do TikTok e clara o
 * bastante para nao virar buraco preto no meio do quadro.
 *
 * A conta e a conversao padrao de HSL para RGB escrita a mao — o canvas sabe
 * fazer isso, mas so devolvendo `hsl(...)`, que as funcoes de cor do projeto
 * nao leem (ver `corDoArcoIris`).
 */
function matizParaHex(matiz) {
  const luz = 0.62;
  const c = 1 - Math.abs(2 * luz - 1); // saturacao cheia
  const h = matiz / 60;
  const x = c * (1 - Math.abs((h % 2) - 1));
  const m = luz - c / 2;

  let r = 0;
  let g = 0;
  let b = 0;
  if (h < 1) [r, g] = [c, x];
  else if (h < 2) [r, g] = [x, c];
  else if (h < 3) [g, b] = [c, x];
  else if (h < 4) [g, b] = [x, c];
  else if (h < 5) [r, b] = [x, c];
  else [r, b] = [c, x];

  const canal = (v) =>
    Math.round((v + m) * 255)
      .toString(16)
      .padStart(2, "0");
  return `#${canal(r)}${canal(g)}${canal(b)}`;
}

/**
 * O deslocamento que o evento impoe na grade INTEIRA.
 *
 * So o CAOS mexe no quadro: o nome e a promessa. Um tremor grande demais
 * jogaria celula para fora da tela e esconderia o desenho da comunidade — que
 * e o unico motivo de a tela existir — entao ele anda 3 pixels, e nao 30.
 *
 * O tranco troca de valor a cada ~80ms e troca de forma IMPREVISIVEL: duas
 * senoides suaves davam uma deriva continua, que o olho acompanha — parecia
 * camera tremida, nao tela quebrando. Pulos secos entre valores sem relacao
 * entre si leem como pane. O arredondamento continua: deslocamento
 * fracionario borraria a grade inteira no meio do tranco.
 */
export function deslocamentoDoEvento(efeito, t = 0) {
  if (efeito !== "caos") return { dx: 0, dy: 0 };

  const passo = Math.floor(t * 12);
  return {
    dx: Math.round((ruido(passo * 1.7) * 2 - 1) * TREMOR_MAXIMO),
    dy: Math.round((ruido(passo * 1.7 + 53.1) * 2 - 1) * TREMOR_MAXIMO),
  };
}

/**
 * Desenha o ENFEITE do evento por cima da grade. `area` e o retangulo da
 * grade, em pixels de CSS — mais `cols`/`rows`, que a chuva da HORA DO PIXEL
 * usa para cair em tamanho de celula.
 *
 * Sem efeito conhecido nao desenha NADA — nem um retangulo transparente: um
 * evento sem enfeite e so multiplicador e banner, e nao pode custar trabalho
 * por quadro.
 */
export function desenharEvento(ctx, efeito, area, t = 0) {
  if (!area) return;

  const enfeites = ["caos", "desafio", "rastro", "brilho"];
  if (!enfeites.includes(efeito)) return;

  // A moldura da HORA DO PIXEL fica no vao entre a grade e a regua, FORA do
  // quadro — e por isso e desenhada antes do corte, que a comeria.
  if (efeito === "brilho") molduraDoBrilho(ctx, area, t);

  ctx.save();

  // Tudo que for pintado fica DENTRO do quadro. Sem o corte, o glitch do CAOS
  // passaria por cima dos rotulos das colunas e do ranking, e a coordenada —
  // a unica coisa que a audiencia precisa ler para participar — viraria borrao
  // colorido.
  ctx.beginPath();
  ctx.rect(area.x, area.y, area.w, area.h);
  ctx.clip();

  if (efeito === "caos") {
    glitchDoCaos(ctx, area, t);
  } else if (efeito === "desafio") {
    miraDoDesafio(ctx, area, t);
  } else if (efeito === "rastro") {
    rastrosDoTurbo(ctx, area, t);
  } else {
    chuvaDoBrilho(ctx, area, t);
  }

  ctx.restore();
}

/**
 * O CAOS quebrou a tela.
 *
 * O clarao rosa pulsando sozinho nao dizia nada: era um blush, nao um caos. O
 * que le como pane e o GLITCH — faixas horizontais piscando em ciano e magenta
 * em posicoes que nao se repetem, um estouro branco de vez em quando, e o
 * tranco da grade (que mora em `deslocamentoDoEvento`). Tudo re-sorteado a cada
 * ~80ms: mais devagar vira cintilacao de enfeite de Natal; mais rapido o olho
 * nao registra.
 */
function glitchDoCaos(ctx, area, t) {
  const passo = Math.floor(t * 12);

  // A mistura `lighter` soma luz ao que ja esta na tela: a faixa nao TAPA o
  // desenho, ela o estoura — que e o efeito de um glitch de verdade.
  ctx.globalCompositeOperation = "lighter";

  // O brilho de fundo: um magenta fraco pulsando por baixo das faixas, para o
  // quadro inteiro participar do terremoto, e nao so as listras.
  ctx.globalAlpha = 0.07 + 0.05 * ruido(passo * 3.1);
  ctx.fillStyle = "#ff3f8e";
  ctx.fillRect(area.x, area.y, area.w, area.h);

  for (let i = 0; i < 6; i += 1) {
    const n = ruido(i * 7.3 + passo * 1.7);

    // Cada piscada apaga parte das faixas. Sem isso, o quadro teria sempre as
    // mesmas seis listras rolando — um padrao, que e o contrario de caos.
    if (n < 0.3) continue;

    const y = area.y + ruido(i * 3.7 + passo * 0.9) * area.h;
    const altura = Math.max(2, area.h * (0.015 + 0.06 * ruido(i * 5.1 + passo * 2.3)));
    const largura = area.w * (0.25 + 0.75 * ruido(i * 9.7 + passo * 1.3));
    const x = area.x + ruido(i * 2.9 + passo * 3.3) * (area.w - largura);

    ctx.globalAlpha = 0.1 + 0.18 * n;
    ctx.fillStyle = n > 0.62 ? "#5ff0ff" : "#ff4fd8";
    ctx.fillRect(x, y, largura, altura);
  }

  // O estouro branco, raro: o quadro inteiro levando um flash. E o que faz a
  // tela parecer que apanhou, e nao que ganhou um filtro.
  if (ruido(passo * 0.77) > 0.78) {
    ctx.globalAlpha = 0.06 + 0.06 * ruido(passo * 4.4);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(area.x, area.y, area.w, area.h);
  }
}

/**
 * O DESAFIO: o quadro virou um visor de mira.
 *
 * O alvo quadrado fechando no centro era uma coisa so, parada no meio de um
 * quadro enorme. Agora sao QUATRO pecas que dizem a mesma frase — "o quadro
 * inteiro e o alvo":
 *
 *   1. os cantos do visor, que respiram (o olho entende "visor" na hora);
 *   2. as cruzetas de borda a borda, com um vao no meio — o centro e para
 *      olhar, nao para riscar;
 *   3. o alvo fechando, de novo e de novo;
 *   4. um losango por dentro do alvo, girando a leitura para o centro.
 *
 * Tudo em ambar, a cor do DESAFIO — e a mesma familia da regua do quadro, o
 * que faz a mira parecer parte da tela, e nao adesivo por cima dela.
 */
function miraDoDesafio(ctx, area, t) {
  const cx = area.x + area.w / 2;
  const cy = area.y + area.h / 2;
  const menor = Math.min(area.w, area.h);
  const respiro = 0.85 + 0.15 * Math.sin(t * 2.2);
  const recuo = menor * 0.045;
  const grossura = Math.max(2, menor * 0.006);

  ctx.strokeStyle = "#ffd93d";

  // 1. Os cantos do visor.
  const braco = menor * 0.1 * respiro;
  ctx.globalAlpha = 0.8;
  ctx.lineWidth = grossura;
  ctx.beginPath();
  for (const [x, y, sx, sy] of [
    [area.x + recuo, area.y + recuo, 1, 1],
    [area.x + area.w - recuo, area.y + recuo, -1, 1],
    [area.x + recuo, area.y + area.h - recuo, 1, -1],
    [area.x + area.w - recuo, area.y + area.h - recuo, -1, -1],
  ]) {
    ctx.moveTo(x + braco * sx, y);
    ctx.lineTo(x, y);
    ctx.lineTo(x, y + braco * sy);
  }
  ctx.stroke();

  // 2. As cruzetas, com o vao no centro.
  const vao = menor * 0.16 * respiro;
  ctx.globalAlpha = 0.45;
  ctx.lineWidth = Math.max(1, grossura * 0.5);
  ctx.beginPath();
  ctx.moveTo(cx, area.y + recuo);
  ctx.lineTo(cx, cy - vao);
  ctx.moveTo(cx, cy + vao);
  ctx.lineTo(cx, area.y + area.h - recuo);
  ctx.moveTo(area.x + recuo, cy);
  ctx.lineTo(cx - vao, cy);
  ctx.moveTo(cx + vao, cy);
  ctx.lineTo(area.x + area.w - recuo, cy);
  ctx.stroke();

  // 3. O alvo fechando, de novo e de novo a cada 2,4s.
  const ciclo = (t % 2.4) / 2.4;
  const meio = menor * 0.5 * (0.9 - 0.75 * ciclo);
  ctx.globalAlpha = 0.85 * (1 - ciclo);
  ctx.lineWidth = grossura;
  ctx.strokeRect(cx - meio, cy - meio, meio * 2, meio * 2);

  // 4. O losango por dentro. Fechado com um `lineTo` de volta, e nao com
  // `closePath`: um comando a menos em cada quadro, e o traco fica igual.
  const ponta = meio * 0.62;
  ctx.globalAlpha = 0.5 * (1 - ciclo);
  ctx.beginPath();
  ctx.moveTo(cx, cy - ponta);
  ctx.lineTo(cx + ponta, cy);
  ctx.lineTo(cx, cy + ponta);
  ctx.lineTo(cx - ponta, cy);
  ctx.lineTo(cx, cy - ponta);
  ctx.stroke();
}

/**
 * O PIXEL TURBO: riscos de velocidade cruzando o quadro.
 *
 * Velocidade nao se desenha — se sugere. O risco de anime e a forma mais
 * direta: uma cabeca acesa com uma cauda que apaga para tras, atravessando o
 * quadro na horizontal.
 *
 * Cada risco tem a propria altura, velocidade e comprimento, sorteados uma vez
 * (pelo indice, via `ruido`) e nunca mais — se mudassem a cada quadro, os
 * riscos saltariam de lugar e o efeito leria como chuvisco. Quem muda a cada
 * instante e so a POSICAO, que e o que da a velocidade.
 */
function rastrosDoTurbo(ctx, area, t) {
  ctx.globalCompositeOperation = "lighter";

  for (let i = 0; i < RASTROS_DO_TURBO; i += 1) {
    const velocidade = 0.7 + 0.6 * ruido(i * 4.7); // voltas por segundo
    const comprimento = area.w * (0.12 + 0.22 * ruido(i * 8.3));
    const altura = Math.max(2, area.h * (0.004 + 0.01 * ruido(i * 6.1)));
    const y = area.y + (0.06 + 0.88 * ruido(i * 12.9)) * area.h;
    const x = area.x + (((t * velocidade + ruido(i * 2.3)) % 1.3) - 0.15) * area.w;

    // A cauda em quatro pedacos que apagam para tras. Quatro e o suficiente:
    // mais pedacos viram um degrade que o encode do TikTok come; menos viram
    // um risco de comprimento fixo, sem a sensacao de arrasto.
    const cor = ruido(i * 5.9) > 0.7 ? "#ffffff" : "#6ff2ff";
    for (let pedaco = 0; pedaco < 4; pedaco += 1) {
      const parte = 1 - pedaco / 4;
      ctx.globalAlpha = 0.3 * parte * parte;
      ctx.fillStyle = cor;
      ctx.fillRect(
        x - (comprimento * (pedaco + 1)) / 4,
        y,
        comprimento / 4,
        altura
      );
    }

    // A cabeca: o ponto mais aceso do risco, e o que da a direcao do movimento.
    ctx.globalAlpha = 0.5;
    ctx.fillStyle = "#d8feff";
    ctx.fillRect(x, y - altura * 0.4, altura * 2.4, altura * 1.8);
  }
}

/**
 * A moldura acesa em volta do quadro, na HORA DO PIXEL.
 *
 * E o sinal que nao depende de ninguem: mesmo sem uma celula pintada, e mesmo
 * com a chuva no meio de uma pausa, a borda dourada respirando diz que a hora
 * esta rendendo dobro. Duas voltas — a linha fina e nitida por dentro, o halo
 * largo e fraco por fora — dao o aspecto de borda ACESA, e nao de borda
 * desenhada: a mesma leitura do glitch do CAOS, que soma luz em vez de tapar.
 */
function molduraDoBrilho(ctx, area, t) {
  const respiro = 0.5 + 0.5 * Math.sin(t * 3.1);
  const folga = MOLDURA_DO_BRILHO;

  ctx.save();
  ctx.globalCompositeOperation = "lighter";
  ctx.strokeStyle = "#ffd93d";
  ctx.lineWidth = 3;
  ctx.globalAlpha = 0.35 + 0.45 * respiro;
  ctx.strokeRect(
    area.x - folga,
    area.y - folga,
    area.w + folga * 2,
    area.h + folga * 2
  );

  ctx.strokeStyle = OURO;
  ctx.lineWidth = folga * 2;
  ctx.globalAlpha = 0.06 + 0.1 * respiro;
  ctx.strokeRect(
    area.x - folga * 2,
    area.y - folga * 2,
    area.w + folga * 4,
    area.h + folga * 4
  );
  ctx.restore();
}

/**
 * A chuva de pixels dourados da HORA DO PIXEL.
 *
 * O feixe de luz so acende o que JA esta pintado; num quadro vazio — ou quase
 * — a HORA DO PIXEL era so o banner. A chuva e a festa que nao depende do
 * desenho de ninguem: pixels dourados do tamanho de uma celula caindo pelo
 * quadro inteiro, como moeda caindo — o proprio nome do evento convidando a
 * sala a pintar enquanto ele durar.
 *
 * Cada pixel cai sempre na MESMA coluna, no mesmo ritmo e no mesmo tamanho (o
 * sorteio e pelo indice, via `ruido`); o que muda a cada quadro e so a
 * posicao, que e o que le como queda. O brilho acende no meio do caminho e
 * apaga nas pontas: o pixel entra e sai de cena sem piscar de um quadro para
 * o outro.
 */
function chuvaDoBrilho(ctx, area, t) {
  const cols = Math.max(1, Math.round(area.cols || 25));
  const cela = area.w / cols;

  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  for (let i = 0; i < DESTELOS_DO_BRILHO; i += 1) {
    const coluna = Math.floor(ruido(i * 1.13) * cols);
    const tamanho = cela * (0.45 + ruido(i * 5.9) * 0.6);
    const velocidade = 0.3 + 0.55 * ruido(i * 3.7); // quedas por segundo
    const progresso = (t * velocidade + ruido(i * 7.31)) % 1;

    ctx.globalAlpha = 0.9 * Math.sin(Math.PI * progresso);
    ctx.fillStyle = CORES_DO_DESTELO[i % CORES_DO_DESTELO.length];
    ctx.fillRect(
      area.x + coluna * cela + (cela - tamanho) / 2,
      area.y + progresso * (area.h - tamanho),
      tamanho,
      tamanho
    );
  }
  ctx.restore();
}
