/**
 * O desenho dos eventos da LIVE.
 *
 * O servidor manda, no `event_start`, um campo `effect` — `arco_iris`, `caos`,
 * `desafio`. Ele chegava inteiro no navegador desde o primeiro dia e ninguem
 * lia: o ARCO-IRIS era um banner com contador, e o CAOS tambem. Um evento que
 * so muda o multiplicador nao se ve; o que faz a audiencia perceber que algo
 * esta acontecendo e a TELA mudar.
 *
 * Sao dois tipos de efeito, e a diferenca decide onde cada um mora:
 *
 * - o ENFEITE por cima do quadro — o tremor do CAOS, o alvo do DESAFIO — e
 *   desenhado aqui, e quem chama e o `renderer.desenhar`;
 * - o ARCO-IRIS nao desenha nada por cima: ele troca a COR das celulas ja
 *   pintadas, e quem pinta celula e o renderer. Aqui mora so a conta da cor
 *   (`corDoArcoIris`).
 *
 * Tudo aqui e desenhado por cima da grade, no MESMO canvas: um terceiro canvas
 * so para o enfeite custaria mais memoria do que o enfeite inteiro. E nada
 * aqui pode ser caro — sao poucos retangulos por quadro, ao lado de 1326
 * celulas que ja sao redesenhadas 60 vezes por segundo.
 *
 * O tempo entra por parametro (`t`, em segundos). Nada aqui le o relogio: e o
 * que permite testar a animacao sem esperar por ela.
 */

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

/**
 * A cor de uma celula pintada enquanto o ARCO-IRIS esta no ar.
 *
 * O modo antigo pintava uma FAIXA por cima do quadro, e a faixa tapava o
 * desenho: a audiencia via um retangulo colorido passando de um lado para o
 * outro, e nao o pixel que tinha acabado de pagar. Agora quem muda de cor sao
 * as celulas JA pintadas — o desenho da comunidade vira o arco-iris, e o
 * quadro vazio continua escuro. O efeito mostra exatamente o que foi
 * construido, e nada por cima dele.
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
 * Arredondado de proposito: deslocamento fracionario borraria a grade inteira
 * no meio de um tremor, e o defeito de borda que acabou de ser consertado
 * voltaria em dobro.
 */
export function deslocamentoDoEvento(efeito, t = 0) {
  if (efeito !== "caos") return { dx: 0, dy: 0 };

  // Duas senoides de periodos primos entre si: a soma nao repete tao cedo, e
  // o olho nao consegue prever para onde a tela vai pular.
  return {
    dx: Math.round(Math.sin(t * 37) * TREMOR_MAXIMO),
    dy: Math.round(Math.cos(t * 53) * TREMOR_MAXIMO),
  };
}

/**
 * Desenha o ENFEITE do evento por cima da grade. `area` e o retangulo da
 * grade, em pixels de CSS.
 *
 * O ARCO-IRIS nao esta aqui de proposito: ele nao pinta nada por cima —
 * troca a cor das celulas pintadas, dentro do laco do renderer (ver
 * `corDoArcoIris`). Sem efeito conhecido nao desenha NADA — nem um retangulo
 * transparente. Um evento sem efeito (`hora_do_pixel`, `pixel_turbo`) e so
 * multiplicador e banner, e nao pode custar trabalho por quadro — e o
 * ARCO-IRIS cai no mesmo caminho: o custo dele e o das celulas que ja iam ser
 * desenhadas de qualquer jeito.
 */
export function desenharEvento(ctx, efeito, area, t = 0) {
  if (!area) return;
  if (efeito !== "caos" && efeito !== "desafio") return;

  ctx.save();

  // Tudo que for pintado fica DENTRO do quadro. Sem o corte, o clarao do CAOS
  // passaria por cima dos rotulos das colunas e do ranking, e a coordenada —
  // a unica coisa que a audiencia precisa ler para participar — viraria borrao
  // colorido.
  ctx.beginPath();
  ctx.rect(area.x, area.y, area.w, area.h);
  ctx.clip();

  if (efeito === "caos") {
    claraoDoCaos(ctx, area, t);
  } else {
    alvoDoDesafio(ctx, area, t);
  }

  ctx.restore();
}

/** Um clarao rosa pulsando: o quadro inteiro levando um empurrao. */
function claraoDoCaos(ctx, area, t) {
  ctx.globalCompositeOperation = "lighter";
  ctx.globalAlpha = 0.10 + 0.07 * (1 + Math.sin(t * 11)) * 0.5;
  ctx.fillStyle = "#ff3f8e";
  ctx.fillRect(area.x, area.y, area.w, area.h);
}

/** Um alvo que fecha no centro do quadro, de novo e de novo. */
function alvoDoDesafio(ctx, area, t) {
  const ciclo = (t % 2.4) / 2.4;
  const meio = Math.min(area.w, area.h) * 0.5 * (0.9 - 0.75 * ciclo);

  ctx.globalAlpha = 0.55 * (1 - ciclo);
  ctx.strokeStyle = "#ffd93d";
  ctx.lineWidth = 3;

  const cx = area.x + area.w / 2;
  const cy = area.y + area.h / 2;
  ctx.strokeRect(cx - meio, cy - meio, meio * 2, meio * 2);
}
