/**
 * O desenho dos eventos da LIVE.
 *
 * O servidor manda, no `event_start`, um campo `effect` — `arco_iris`, `caos`,
 * `desafio`. Ele chegava inteiro no navegador desde o primeiro dia e ninguem
 * lia: o ARCO-IRIS era um banner com contador, e o CAOS tambem. Um evento que
 * so muda o multiplicador nao se ve; o que faz a audiencia perceber que algo
 * esta acontecendo e a TELA mudar.
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

const SETE_CORES = 7;

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
 * Desenha o efeito do evento por cima da grade. `area` e o retangulo da grade,
 * em pixels de CSS.
 *
 * Sem efeito conhecido nao desenha NADA — nem um retangulo transparente. Um
 * evento sem efeito (`hora_do_pixel`, `pixel_turbo`) e so multiplicador e
 * banner, e nao pode custar trabalho por quadro.
 */
export function desenharEvento(ctx, efeito, area, t = 0) {
  if (!area || !efeito) return;
  if (efeito !== "arco_iris" && efeito !== "caos" && efeito !== "desafio") return;

  ctx.save();

  // Tudo que for pintado fica DENTRO do quadro. Sem o corte, a faixa de
  // arco-iris passaria por cima dos rotulos das colunas e do ranking, e a
  // coordenada — a unica coisa que a audiencia precisa ler para participar —
  // viraria borrao colorido.
  ctx.beginPath();
  ctx.rect(area.x, area.y, area.w, area.h);
  ctx.clip();

  if (efeito === "arco_iris") {
    faixaArcoIris(ctx, area, t);
  } else if (efeito === "caos") {
    claraoDoCaos(ctx, area, t);
  } else {
    alvoDoDesafio(ctx, area, t);
  }

  ctx.restore();
}

/** Sete faixas de cor que atravessam o quadro, devagar. */
function faixaArcoIris(ctx, area, t) {
  const largura = area.w / SETE_CORES;
  // Anda para a direita em ciclo fechado: a faixa que sai por um lado entra
  // pelo outro, entao nao existe o "pulo" de quando a animacao reinicia.
  const deslocamento = ((t * 70) % (largura * SETE_CORES)) - largura * SETE_CORES;

  ctx.globalCompositeOperation = "lighter";
  ctx.globalAlpha = 0.16;

  for (let i = 0; i < SETE_CORES; i += 1) {
    const x = area.x + i * largura + deslocamento + largura * SETE_CORES;
    if (x > area.x + area.w || x + largura < area.x) continue;
    // A matiz gira com o tempo alem de a faixa andar: parada, uma faixa de
    // sete cores lê como um enfeite fixo; girando, lê como algo VIVO.
    const matiz = (i * (360 / SETE_CORES) + t * 45) % 360;
    ctx.fillStyle = `hsla(${matiz.toFixed(1)}, 100%, 62%, 1)`;
    ctx.fillRect(x, area.y, largura, area.h);
  }
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
