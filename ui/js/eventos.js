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
 *   riscos do PIXEL TURBO, a festa da HORA DO PIXEL, a TEMPESTADE, a CHUVA
 *   DE CODIGO, os FOGOS, os flocos da NEVE, o tubo do ARCADE e o FILME
 *   ANTIGO — e desenhado aqui, e quem chama e o `renderer.desenhar`;
 * - o efeito de CELULA — o ARCO-IRIS, o feixe do BRILHO, o NEGATIVO, a
 *   geada da NEVE e o sepia do FILME — troca a COR das celulas ja pintadas,
 *   e quem pinta celula e o renderer. Aqui moram so as contas de cor
 *   (`corDaCelula`).
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
 * num quadro vazio a HORA DO PIXEL era so o banner. A NEVE e o FILME ANTIGO
 * seguem a mesma receita mista: a geada e o sepia nas celulas, os flocos e a
 * pelicula velha por cima.
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

/** Quantos fios de chuva cruzam o quadro na TEMPESTADE. */
const FIOS_DA_TEMPESTADE = 46;

/**
 * De quantos em quantos segundos cai um relampago.
 *
 * 1,9s: mais devagar vira cena parada com um susto raro; mais rapido vira
 * estrobo, e a tela piscando sem parar cansa quem so quer ver o desenho.
 */
const CICLO_DO_RAIO = 1.9;

/** Quanto do ciclo do raio o clarao dura — o resto e so a chuva. */
const DURACAO_DO_CLARAO = 0.22;

/** O quanto a noite da TEMPESTADE escurece o quadro (0 = nada, 1 = breu). */
const NOITE_DA_TEMPESTADE = 0.34;

/** Quantos degraus o risco do raio tem, de cima a baixo do quadro. */
const PASSOS_DO_RAIO = 12;

/** O ceu da TEMPESTADE: azul tao escuro que le como noite, nunca como cinza. */
const NOITE = "#04070f";

/** O fio da chuva: azul claro e dessaturado, para nao competir com o desenho. */
const CHUVA = "#9fc4ff";

/** O branco-azulado do clarao e o branco do risco do raio. */
const CLARAO = "#cfe4ff";
const RAIO = "#f4faff";

/** A cor do codigo caindo e a da cabeca acesa de cada coluna. */
const VERDE_DO_CODIGO = "#39ff6a";
const CABECA_DO_CODIGO = "#d8ffe0";

/** A cor da geada da NEVE: branco-azulado, o tom de coisa congelada. */
const GELO = "#dceeff";

/**
 * O quanto o gelo cobre a celula, do fraco ao forte.
 *
 * A geada nao e um filtro parado: ela cintila em ondas pela diagonal (a mesma
 * familia do arco-iris e do brilho), e estes dois numeros sao o quanto ela
 * tinge no vale e na crista da onda.
 */
const GELO_MINIMO = 0.2;
const GELO_MAXIMO = 0.5;

/** Quantos flocos caem ao mesmo tempo na NEVE. */
const FLOCOS_DA_NEVE = 34;

/** A cor do floco: branco levemente azulado, para ler contra a geada. */
const FLOCOS = "#f2f7ff";

/** O tom amarelado do FILME ANTIGO — o sepia de papel envelhecido. */
const SEPIA = "#c9b48f";

/** O quanto o sepia entra na celula; o resto e o cinza da pelicula. */
const SEPIA_DO_FILME = 0.45;

/**
 * Quantos quadros por segundo a pelicula do FILME ANTIGO roda.
 *
 * 24 e o numero do cinema — e o que faz o tremor de luz e os riscos piscarem
 * como projetor (a 60 quadros por segundo eles leriam como monitor).
 */
const QUADROS_DO_FILME = 24;

/** A grossura de cada degrau da vinheta do FILME e quantos degraus ela tem. */
const VINHETA_DO_FILME = 26;
const DEGRAUS_DA_VINHETA = 5;

/** Quantos riscos de pelicula podem cruzar o quadro. */
const RISCOS_DO_FILME = 3;

/** Quantas bombas sobem ao mesmo tempo na QUEIMA DE FOGOS. */
const BOMBAS_DOS_FOGOS = 3;

/** Quanto do ciclo de uma bomba e a subida — o resto e a explosao. */
const SUBIDA_DOS_FOGOS = 0.3;

/** Quantas faiscas cada explosao abre. */
const FAISCAS_DOS_FOGOS = 16;

/** As cores das explosoes, uma por bomba. */
const CORES_DOS_FOGOS = ["#ff6fd8", "#5ff0ff", "#ffd93d"];

/** De quantos em quantos pixels de CSS cai um risco de varredura do ARCADE. */
const LINHAS_DO_ARCADE = 5;

/** A que velocidade os riscos do ARCADE rolam para cima, em pixels/s. */
const ROLAGEM_DO_ARCADE = 9;

/** A que velocidade a faixa de varredura do ARCADE desce, em voltas/s. */
const VARREDURA_DO_ARCADE = 0.22;

/** O verde do fosforo: a cara de qualquer tela de tubo. */
const FOSFORO = "#7dffd4";

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
 * A cor de uma celula pintada no NEGATIVO: a foto invertida.
 *
 * O efeito mais barato de explicar e o mais estranho de ver: cada canal da
 * cor vira o seu complemento (255 menos o valor), como o negativo de um
 * filme. O desenho da comunidade continua exatamente onde estava — invertido
 * canal a canal, e so.
 */
function corDoNegativo(cor) {
  const { r, g, b } = hexParaRgb(cor);
  const canal = (v) => (255 - v).toString(16).padStart(2, "0");
  return `#${canal(r)}${canal(g)}${canal(b)}`;
}

/**
 * A cor de uma celula pintada sob a NEVE: a geada.
 *
 * A neve nao troca a cor de quem pintou: ela POUSA em cima — cada celula
 * ganha uma camada de gelo, e o desenho segue legivel por baixo. A onda pela
 * diagonal faz a geada cintilar devagar; parada, ela seria so um filtro
 * azulado, e o nome do evento promete neve, nao um filtro.
 */
function corDaNeve(cor, x, y, t) {
  const onda = 0.5 + 0.5 * Math.sin((x + y) * 0.55 - t * 1.6);
  return misturar(cor, GELO, GELO_MINIMO + (GELO_MAXIMO - GELO_MINIMO) * onda);
}

/**
 * A cor de uma celula pintada no FILME ANTIGO: preto e branco com sepia.
 *
 * Primeiro a pelicula perde a cor — a luminancia da cor original, para o
 * olho nao achar que virou outro pixel —, e depois leva o sepia, o amarelo
 * de papel envelhecido. E o mesmo desenho, so que num projetor de 1960.
 */
function corDoFilme(cor) {
  const { r, g, b } = hexParaRgb(cor);
  const luz = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  const canal = luz.toString(16).padStart(2, "0");
  return misturar(`#${canal}${canal}${canal}`, SEPIA, SEPIA_DO_FILME);
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
  if (efeito === "negativo") return corDoNegativo(cor);
  if (efeito === "neve") return corDaNeve(cor, x, y, t);
  if (efeito === "filme") return corDoFilme(cor);
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
 * Os enfeites, por nome de efeito. O `config.json` manda o nome no
 * `event_start`, e este mapa e a unica ponte entre o nome e o desenho.
 *
 * Mapa e nao uma cadeia de `if`: com dez efeitos, o `else` final vira uma
 * armadilha — um efeito novo sem ramo proprio cai calado no desenho do
 * BRILHO. Aqui, efeito sem entrada simplesmente nao desenha, e o teste
 * "cada ENFEITE pinta" acusa na hora.
 *
 * Efeito SO de celula (ARCO-IRIS, NEGATIVO) nao entra: quem desenha a cor
 * deles e o renderer, pelo `corDaCelula`.
 */
export const ENFEITES = {
  caos: glitchDoCaos,
  desafio: miraDoDesafio,
  rastro: rastrosDoTurbo,
  brilho: chuvaDoBrilho,
  tempestade: tempestadeDoEvento,
  codigo: chuvaDoCodigo,
  fogos: fogosDoEvento,
  neve: flocosDaNeve,
  arcade: scanlinesDoArcade,
  filme: filmeAntigo,
};

/**
 * Desenha o ENFEITE do evento por cima da grade. `area` e o retangulo da
 * grade, em pixels de CSS — mais `cols`/`rows`, que a chuva da HORA DO PIXEL
 * e a de codigo usam para cair em tamanho de celula.
 *
 * Sem efeito conhecido nao desenha NADA — nem um retangulo transparente: um
 * evento sem enfeite e so multiplicador e banner, e nao pode custar trabalho
 * por quadro.
 */
export function desenharEvento(ctx, efeito, area, t = 0) {
  if (!area) return;

  const enfeite = ENFEITES[efeito];
  if (typeof enfeite !== "function") return;

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

  enfeite(ctx, area, t);

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
 * A TEMPESTADE: a noite cai, a chuva desce e o raio risca o ceu.
 *
 * O evento existe para punir quem esta de costas: a tela pisca, troveja no
 * nome e o multiplicador dobra. O desenho segue a mesma ideia — em vez de
 * enfeitar o quadro, ele MUDA O CLIMA dele:
 *
 *   1. a noite, um veu escuro por cima do desenho — a comunidade ve o que
 *      pintou, mas sob a chuva;
 *   2. a chuva, fios curtos caindo em colunas fixas;
 *   3. o raio, a cada ~1,9s: um clarao no quadro inteiro e um risco
 *      quebrado descendo, sempre na mesma forma durante a piscada.
 *
 * A noite e a unica coisa deste arquivo que TAPA o desenho de proposito — e
 * por isso ela e fraca (0,34) e temporaria: a regra continua valendo (o
 * desenho e o que a audiencia pagou para ver), e a tempestade passa.
 */
function tempestadeDoEvento(ctx, area, t) {
  // `source-over` com alfa, e nao `lighter`: escurecer nao se faz somando luz.
  ctx.globalAlpha = NOITE_DA_TEMPESTADE;
  ctx.fillStyle = NOITE;
  ctx.fillRect(area.x, area.y, area.w, area.h);

  // Daqui para baixo tudo SOMA luz (a chuva e o raio sao claridade na noite).
  ctx.globalCompositeOperation = "lighter";

  for (let i = 0; i < FIOS_DA_TEMPESTADE; i += 1) {
    const x = area.x + ruido(i * 7.7) * area.w;
    const velocidade = 0.9 + 0.9 * ruido(i * 3.3); // quedas por segundo
    const comprimento = area.h * (0.02 + 0.05 * ruido(i * 5.1));
    const y = area.y + ((t * velocidade + ruido(i * 9.9)) % 1) * area.h;

    ctx.globalAlpha = 0.06 + 0.12 * ruido(i * 2.7);
    ctx.fillStyle = CHUVA;
    // Mais fino que alto de proposito: o fio da chuva, e nao uma barra.
    ctx.fillRect(x, y, 1.5, comprimento);
  }

  // O raio. O ciclo inteiro e `floor(t / CICLO)`: o `floor` e o que congela a
  // forma do risco durante a piscada — se ela fosse sorteada por `t`, o raio
  // tremeria como um verme a cada quadro, em vez de ser UM raio por relampago.
  const ciclo = Math.floor(t / CICLO_DO_RAIO);
  const fase = (t % CICLO_DO_RAIO) / CICLO_DO_RAIO;
  if (fase >= DURACAO_DO_CLARAO) return;

  const forca = 1 - fase / DURACAO_DO_CLARAO;
  ctx.globalAlpha = 0.14 + 0.3 * forca * forca;
  ctx.fillStyle = CLARAO;
  ctx.fillRect(area.x, area.y, area.w, area.h);

  // O risco: degraus empilhados descendo, cada um desviando um pouco do
  // anterior. O desvio e sorteado por (ciclo, degrau) — o mesmo relampago
  // desenha sempre o mesmo raio, e cada relampago desenha um raio diferente.
  let x = area.x + ruido(ciclo * 12.9) * area.w;
  const altura = area.h / PASSOS_DO_RAIO;
  ctx.globalAlpha = 0.45 + 0.55 * forca;
  ctx.fillStyle = RAIO;
  for (let passo = 0; passo < PASSOS_DO_RAIO; passo += 1) {
    x += (ruido(ciclo * 31.7 + passo * 4.1) * 2 - 1) * area.w * 0.035;
    ctx.fillRect(x, area.y + passo * altura, 3, altura + 2);
  }
}

/**
 * A CHUVA DE CODIGO: colunas verdes caindo, tela de terminal.
 *
 * A piada visual e conhecida — o filme que todo mundo ja viu — e o evento e o
 * unico que nao promete premio: o multiplicador e 1.0 e o que a CHUVA DE
 * CODIGO entrega e o espetaculo. Por isso ela cai no tamanho exato da CELULA:
 * os quadradinhos verdes sao da mesma familia dos que a sala pinta, e a tela
 * parece o proprio jogo sendo hackeado.
 *
 * Cada coluna tem velocidade, comprimento de cauda e defasagem sorteados uma
 * vez (pelo indice, via `ruido`); a cada quadro muda so a posicao. A cabeca e
 * branca e a cauda apaga quadratica: o olho le "letra acesa com rastro", que
 * e o que da a direcao da queda.
 */
function chuvaDoCodigo(ctx, area, t) {
  const cols = Math.max(1, Math.round(area.cols || 25));
  const cela = area.w / cols;

  ctx.save();
  ctx.globalCompositeOperation = "lighter";

  for (let i = 0; i < cols; i += 1) {
    const velocidade = 0.22 + 0.5 * ruido(i * 4.3); // quedas por segundo
    const cauda = 5 + Math.floor(ruido(i * 6.7) * 8);
    const progresso = (t * velocidade + ruido(i * 9.1)) % 1;

    // A viagem cobre a altura MAIS a cauda: assim a coluna entra por cima com
    // a cauda inteira atras e sai por baixo inteira — sem aparecer cortada no
    // meio do quadro, que denunciaria o truque.
    const topo = area.y + progresso * (area.h + cauda * cela) - cauda * cela;

    for (let j = 0; j < cauda; j += 1) {
      const y = topo + j * cela;
      if (y < area.y - cela || y > area.y + area.h) continue;

      const apagando = 1 - j / cauda;
      ctx.globalAlpha = 0.8 * apagando * apagando;
      ctx.fillStyle = j === 0 ? CABECA_DO_CODIGO : VERDE_DO_CODIGO;
      // O quadrado menor que a celula, com uma folga: le como caractere
      // aceso, e nao como uma coluna solida pintada.
      ctx.fillRect(
        area.x + i * cela + cela * 0.14,
        y + cela * 0.14,
        cela * 0.72,
        cela * 0.72
      );
    }
  }

  ctx.restore();
}

/**
 * A QUEIMA DE FOGOS: as bombas sobem, explodem e a tela toda se enfeita.
 *
 * Cada bomba tem o proprio ritmo: sobe como um ponto aceso e vira um anel de
 * faiscas na altura mais alta. As tres sao defasadas de proposito — sempre
 * tem uma subindo ou explodindo no ar, que e o que faz a queima parecer
 * continua, e nao um conta-gotas.
 *
 * A bomba inteira e funcao do tempo: `u` (0..1) e o quanto ela andou no
 * proprio ciclo, e cada fase e um pedaco de `u`. Nada e sorteado por quadro
 * — pelo motivo de sempre: o OBS captura o que desenhamos, e um fogo que
 * troca de forma a cada captura leria como chuvisco.
 */
function fogosDoEvento(ctx, area, t) {
  ctx.globalCompositeOperation = "lighter";

  for (let i = 0; i < BOMBAS_DOS_FOGOS; i += 1) {
    const periodo = 2.4 + 1.6 * ruido(i * 3.1); // segundos por bomba
    const u = ((t + ruido(i * 7.7) * periodo) % periodo) / periodo;
    const x = area.x + (0.15 + 0.7 * ruido(i * 5.3)) * area.w;
    const altura = area.y + (0.08 + 0.3 * ruido(i * 9.1)) * area.h;
    const cor = CORES_DOS_FOGOS[i % CORES_DOS_FOGOS.length];

    if (u < SUBIDA_DOS_FOGOS) {
      // A subida: o ponto aceso galgando o ceu, com um rastro curto atras.
      const p = u / SUBIDA_DOS_FOGOS;
      const y = area.y + area.h - (area.y + area.h - altura) * p;
      ctx.fillStyle = cor;
      ctx.globalAlpha = 0.85;
      ctx.fillRect(x - 1.5, y, 3, 3);
      ctx.globalAlpha = 0.3;
      ctx.fillRect(x - 1, y + 3, 2, Math.max(4, area.h * 0.025));
      continue;
    }

    // A explosao: um anel que abre e apaga, com um desvio por faisca para o
    // anel nao sair de compasso. O desvio e sorteado por (bomba, faisca) —
    // entao ele fica parado durante a explosao inteira, e muda de bomba para
    // bomba.
    const p = (u - SUBIDA_DOS_FOGOS) / (1 - SUBIDA_DOS_FOGOS);
    const apagando = (1 - p) * (1 - p);
    const tamanho = Math.max(1.5, 4.5 * (1 - p));
    const base = area.h * (0.1 + 0.12 * ruido(i * 4.9));
    ctx.fillStyle = cor;

    for (let k = 0; k < FAISCAS_DOS_FOGOS; k += 1) {
      const angulo =
        (k / FAISCAS_DOS_FOGOS) * Math.PI * 2 +
        (ruido(i * 11.3 + k * 1.9) - 0.5) * 0.5;
      const raio = p * base * (0.8 + 0.4 * ruido(i * 2.1 + k * 5.7));
      ctx.globalAlpha = 0.85 * apagando;
      ctx.fillRect(
        x + Math.cos(angulo) * raio - tamanho / 2,
        altura + Math.sin(angulo) * raio * 0.85 - tamanho / 2,
        tamanho,
        tamanho
      );
    }
  }
}

/**
 * A NEVE caindo: flocos lentos e graúdos, balancando ao vento.
 *
 * O par oposto da TEMPESTADE: la e chuva rapida e violenta, com noite e raio;
 * aqui e neve — devagar, do tamanho de meia celula, e cada floco descendo no
 * proprio ritmo. O balanco lateral e o que separa "neve" de "pontos
 * descendo": um floco de verdade nao cai em linha reta.
 */
function flocosDaNeve(ctx, area, t) {
  ctx.globalCompositeOperation = "lighter";

  for (let i = 0; i < FLOCOS_DA_NEVE; i += 1) {
    const tamanho = Math.max(2, area.w * (0.008 + 0.012 * ruido(i * 5.9)));
    const velocidade = 0.1 + 0.16 * ruido(i * 3.7); // quedas por segundo
    const progresso = (t * velocidade + ruido(i * 7.3)) % 1;
    const balanco =
      Math.sin(t * (0.6 + 0.8 * ruido(i * 2.9)) + ruido(i * 11.1) * 6.28) *
      area.w *
      0.02;
    const x = area.x + ruido(i * 1.7) * area.w + balanco;
    const y = area.y + progresso * (area.h + tamanho) - tamanho;

    // Entra e sai de cena sem piscar: some suave nas pontas do caminho.
    const aparecendo = Math.min(1, progresso * 6, (1 - progresso) * 6);
    ctx.globalAlpha = (0.3 + 0.45 * ruido(i * 9.7)) * aparecendo;
    ctx.fillStyle = FLOCOS;
    ctx.fillRect(x, y, tamanho, tamanho);
  }
}

/**
 * O ARCADE: o quadro virou a tela de um fliperama.
 *
 * Sao tres camadas, todas baratas, e juntas leem como tubo de verdade:
 *
 *   1. os riscos de varredura — linhas frias e finas entre as linhas de
 *      fosforo —, rolando devagar para cima, como tela de tubo mal ajustada;
 *   2. o banho de fosforo: um verde fraco por cima de tudo;
 *   3. a faixa de varredura descendo: o instante em que o canhao redesenha o
 *      quadro, de cima a baixo.
 *
 * Nada disso esconde o desenho: as linhas somam 0,16 de alfa e a faixa 0,07 —
 * o pixel da comunidade continua o dono da tela.
 */
function scanlinesDoArcade(ctx, area, t) {
  // 1. As linhas frias. Elas ESCURECEM (source-over): somar luz clarearia
  // justamente onde a tela de tubo tem o vao entre as linhas de fosforo.
  const deslocamento = (t * ROLAGEM_DO_ARCADE) % LINHAS_DO_ARCADE;
  ctx.fillStyle = "#020604";
  ctx.globalAlpha = 0.16;
  for (
    let y = area.y + deslocamento - LINHAS_DO_ARCADE;
    y < area.y + area.h;
    y += LINHAS_DO_ARCADE
  ) {
    ctx.fillRect(area.x, y, area.w, 1.6);
  }

  ctx.globalCompositeOperation = "lighter";

  // 2. O banho de fosforo.
  ctx.globalAlpha = 0.05;
  ctx.fillStyle = FOSFORO;
  ctx.fillRect(area.x, area.y, area.w, area.h);

  // 3. A faixa de varredura.
  const altura = area.h * 0.12;
  const y = area.y + ((t * VARREDURA_DO_ARCADE) % 1) * (area.h + altura) - altura;
  ctx.globalAlpha = 0.07;
  ctx.fillRect(area.x, y, area.w, altura);
}

/**
 * O FILME ANTIGO: o quadro virou pelicula de 1960.
 *
 * O sepia das celulas (ver `corDoFilme`) e metade do efeito; a outra metade
 * e o que a pelicula faz POR CIMA do quadro:
 *
 *   1. o tremor de luz — um veu que muda de intensidade a cada quadro (24 por
 *      segundo, o numero do cinema): e o que faz a tela piscar como projetor,
 *      e nao como monitor;
 *   2. a vinheta — degraus escuros empilhados das bordas para dentro, o
 *      escuro da lente que nao alcancava os cantos;
 *   3. os riscos e a poeira — raros e por quadro, como num rolo de verdade.
 */
function filmeAntigo(ctx, area, t) {
  const quadro = Math.floor(t * QUADROS_DO_FILME);

  // 1. O tremor de luz.
  ctx.globalAlpha = 0.03 + 0.05 * ruido(quadro * 0.77);
  ctx.fillStyle = "#1a1208";
  ctx.fillRect(area.x, area.y, area.w, area.h);

  // 2. A vinheta: o anel k fica a `k * passo` da borda, e o de fora e o mais
  // escuro — por isso o alfa cai conforme o anel entra.
  ctx.fillStyle = "#0a0705";
  for (let k = 0; k < DEGRAUS_DA_VINHETA; k += 1) {
    const d = k * VINHETA_DO_FILME;
    const lado = Math.max(0, area.h - d * 2);
    ctx.globalAlpha = 0.2 - k * 0.032;
    ctx.fillRect(area.x, area.y + d, area.w, VINHETA_DO_FILME);
    ctx.fillRect(
      area.x,
      area.y + area.h - d - VINHETA_DO_FILME,
      area.w,
      VINHETA_DO_FILME
    );
    ctx.fillRect(area.x + d, area.y + d, VINHETA_DO_FILME, lado);
    ctx.fillRect(
      area.x + area.w - d - VINHETA_DO_FILME,
      area.y + d,
      VINHETA_DO_FILME,
      lado
    );
  }

  // 3. Os riscos: cada quadro sorteia de novo, e a maioria dos quadros nao
  // tem risco nenhum — e isso que faz o que aparece parecer defeito de
  // pelicula, e nao enfeite.
  ctx.globalCompositeOperation = "lighter";
  for (let r = 0; r < RISCOS_DO_FILME; r += 1) {
    if (ruido(quadro * 7.7 + r * 13.1) < 0.86) continue;
    const x = area.x + ruido(quadro * 3.3 + r * 5.9) * area.w;
    const y = area.y + ruido(quadro * 1.9 + r * 8.3) * area.h * 0.5;
    const altura = area.h * (0.1 + 0.36 * ruido(quadro * 4.1 + r * 2.7));
    ctx.globalAlpha = 0.1 + 0.12 * ruido(quadro * 6.1 + r * 3.7);
    ctx.fillStyle = "#fff6e0";
    ctx.fillRect(x, y, 1.5, altura);
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
