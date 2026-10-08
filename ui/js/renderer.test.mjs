/**
 * O quadro que o Renderer entrega, medido em PIXELS DO APARELHO.
 *
 * O defeito que este teste mata: `desenhar()` desenha no espaco de CSS
 * (`ctx.scale(dpr, dpr)`) mas pedia o tamanho do apagador em pixels do
 * aparelho (`canvas.width`). Dentro do espaco escalado o tamanho era
 * multiplicado por `dpr` OUTRA VEZ. Com dpr 0,625 — um zoom de 50% do
 * navegador num monitor de Windows a 125% — o canvas de 675x762 pixels so era
 * apagado nos primeiros 422x476: o resto do quadro nunca era limpo, e o que
 * fosse desenhado por cima ia ACUMULANDO quadro a quadro.
 *
 * O sintoma nao parecia "falta de limpeza". Com a mistura `lighter` do
 * ARCO-IRIS, a metade direita do quadro saturava em cores berrantes enquanto a
 * esquerda ficava no tom certo, com uma emenda reta no meio; e os rotulos das
 * colunas apareciam duplicados ("AA AA AB AC") porque estavam sendo redesenhados
 * por cima deles mesmos. Um dpr >= 1 apagava demais — e apagar demais nao faz
 * mal nenhum —, entao o defeito so existia com a pagina encolhida.
 *
 * Por isso o teste varre dprs dos dois lados de 1. Um contexto de mentira que
 * apenas ANOTA os comandos nao serviria: a pergunta e justamente em que lugar
 * do quadro cada comando cai, e para isso o contexto falso precisa carregar a
 * transformacao corrente como um contexto de verdade.
 *
 * Roda com `node --test ui/js/renderer.test.mjs`.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { corDaCelula, corDoArcoIris } from "./eventos.js";
import { Renderer } from "./renderer.js";

const LARGURA = 1080;
const ALTURA = 1220;

/** O dpr 1 e o do OBS; os fracionarios sao a pagina encolhida. */
const DPRS = [1, 2, 1.25, 0.75, 0.5, 0.625];

/**
 * Um contexto 2D que so anota, mas que acompanha `scale`/`setTransform`/
 * `save`/`restore` para saber onde cada retangulo cai NO APARELHO.
 */
function contextoFalso() {
  const comandos = [];
  let a = 1;
  let d = 1;
  let e = 0;
  let f = 0;
  const pilha = [];

  // O retangulo depois de passar pela transformacao corrente.
  const caixa = (x, y, largura, altura) => ({
    x0: x * a + e,
    y0: y * d + f,
    x1: (x + largura) * a + e,
    y1: (y + altura) * d + f,
  });

  const anotar = (nome) => (...args) => comandos.push([nome, ...args]);

  return {
    comandos,
    ctx: {
      save: () => {
        pilha.push([a, d, e, f]);
        comandos.push(["save"]);
      },
      restore: () => {
        [a, d, e, f] = pilha.pop() || [1, 1, 0, 0];
        comandos.push(["restore"]);
      },
      scale: (sx, sy) => {
        comandos.push(["scale", sx, sy]);
        a *= sx;
        d *= sy;
      },
      setTransform: (na, nb, nc, nd, ne, nf) => {
        comandos.push(["setTransform", na, nb, nc, nd, ne, nf]);
        a = na;
        d = nd;
        e = ne;
        f = nf;
      },
      clearRect: (x, y, largura, altura) => {
        comandos.push(["clearRect", caixa(x, y, largura, altura)]);
      },
      // A tinta vai junto: e por ela que o teste do ARCO-IRIS pergunta de que
      // cor uma celula saiu neste quadro.
      fillRect: function (x, y, largura, altura) {
        comandos.push(["fillRect", caixa(x, y, largura, altura), this.fillStyle]);
      },
      createRadialGradient: () => ({ addColorStop() {} }),
      beginPath: anotar("beginPath"),
      rect: anotar("rect"),
      clip: anotar("clip"),
      strokeRect: anotar("strokeRect"),
      moveTo: anotar("moveTo"),
      lineTo: anotar("lineTo"),
      stroke: anotar("stroke"),
      fillText: anotar("fillText"),
      translate: anotar("translate"),
      globalCompositeOperation: "source-over",
      globalAlpha: 1,
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
      font: "",
      textAlign: "",
      textBaseline: "",
    },
  };
}

/** Um quadro desenhado com o dpr pedido; devolve a tela e os comandos. */
function quadro(dpr) {
  const anterior = globalThis.window;
  globalThis.window = { devicePixelRatio: dpr };

  try {
    const { ctx, comandos } = contextoFalso();
    const canvas = { width: 0, height: 0, style: {}, getContext: () => ctx };
    const renderer = new Renderer(canvas);
    renderer.redimensionar(LARGURA, ALTURA);
    renderer.desenhar(0);
    return { canvas, comandos };
  } finally {
    globalThis.window = anterior;
  }
}

/** O comando cobre o quadro inteiro, do pixel 0 ao ultimo? */
const cobre = (caixa, canvas) =>
  caixa.x0 <= 0 &&
  caixa.y0 <= 0 &&
  caixa.x1 >= canvas.width &&
  caixa.y1 >= canvas.height;

const tamanho = (c) => c[1] && `x ${c[1].x0}..${c[1].x1}  y ${c[1].y0}..${c[1].y1}`;

/**
 * A tinta com que a celula (x, y) foi preenchida no ultimo quadro desenhado.
 *
 * Os efeitos de celula (ARCO-IRIS, BRILHO) nao aparecem como comando proprio —
 * eles trocam a COR com que a celula e preenchida. E esta cor que o teste olha.
 */
function tintaDaCelula(comandos, renderer, x, y) {
  const { xs, ys } = renderer.bordas();
  const tinta = comandos.find(
    (c) =>
      c[0] === "fillRect" &&
      c[1].x0 === xs[x] &&
      c[1].y0 === ys[y] &&
      c[1].x1 === xs[x + 1] &&
      c[1].y1 === ys[y + 1]
  );
  return tinta && tinta[2];
}

test("o apagador limpa o quadro INTEIRO, em qualquer dpr", () => {
  for (const dpr of DPRS) {
    const { canvas, comandos } = quadro(dpr);
    const apagadas = comandos.filter((c) => c[0] === "clearRect");

    assert.ok(apagadas.length > 0, `com dpr ${dpr} nem apagou o quadro`);

    for (const comando of apagadas) {
      assert.ok(
        cobre(comando[1], canvas),
        `com dpr ${dpr} sobrou quadro sem apagar em ${tamanho(comando)} — ` +
          `um canvas de ${canvas.width}x${canvas.height}: o que ficar de fora ` +
          `acumula quadro a quadro`
      );
    }
  }
});

/**
 * O canvas mora DENTRO do palco, e o palco inteiro passa por
 * `transform: scale(escala)`. Isso poe as duas medidas do `redimensionar` em
 * espacos DIFERENTES, e trocar uma pela outra custa a tela:
 *
 *   `canvas.style.width` e um comprimento de LAYOUT, lido no espaco do palco;
 *   `canvas.width` e o buffer, em PIXELS DO APARELHO ja na tela.
 *
 * Medir a arena com `getBoundingClientRect()` devolve o tamanho DEPOIS da
 * escala do palco, e escrever esse numero no `style.width` encolhe o canvas
 * duas vezes: numa janela de 1366x768 (escala 0,4) o canvas ficava com 40% da
 * largura da arena, colado na esquerda. A grade saia desenhada num canto, com
 * o rotulo das colunas ilegivel — o "grid minusculo, ocupando so metade da
 * metade" do relato.
 *
 * Com escala 1 os dois espacos dao o MESMO numero, e por isso o defeito passou
 * a vida inteira escondido: o OBS captura a 1080x1920, onde nao ha diferenca.
 */

/** A arena de uma janela de 1366x768: 768/1920 = 0,4 de escala, 3415 de largura. */
const ARENA = [3415, 1220];

/** Um quadro dimensionado com a escala do palco e o dpr do aparelho. */
function quadroEscalado(escala, dpr, [largura, altura] = ARENA) {
  const anterior = globalThis.window;
  globalThis.window = { devicePixelRatio: dpr };

  try {
    const { ctx } = contextoFalso();
    const canvas = { width: 0, height: 0, style: {}, getContext: () => ctx };
    const renderer = new Renderer(canvas);
    renderer.redimensionar(largura, altura, escala);
    return { canvas, renderer };
  } finally {
    globalThis.window = anterior;
  }
}

test("o canvas cobre a arena INTEIRA por mais encolhido que o palco esteja", () => {
  for (const escala of [0.25, 0.4, 0.5625, 1, 1.125]) {
    const { canvas } = quadroEscalado(escala, 1);
    const naTela = Math.round(ARENA[0] * escala);

    assert.equal(
      canvas.style.width,
      `${ARENA[0]}px`,
      `escala ${escala}: o canvas ficou com ${canvas.style.width} de layout numa ` +
        `arena de ${ARENA[0]}px — o resto da arena fica sem canvas`
    );
    assert.equal(canvas.style.height, `${ARENA[1]}px`);
    assert.equal(
      canvas.width,
      naTela,
      `escala ${escala}: o buffer tem ${canvas.width} pixels para ${naTela} na tela`
    );
  }
});

test("a celula e um numero INTEIRO de pixels do aparelho com o palco encolhido", () => {
  // A promessa do `calcularGrade` e a celula cair no pixel do aparelho. Com o
  // palco escalado, o "pixel do aparelho" da celula e o da TELA: a escala entra
  // na conta JUNTO com o `devicePixelRatio`, nao no lugar dele. E o que faz a
  // celula de 23 numeros valer 9 pixels redondos de tela, e nao 9,2.
  for (const escala of [0.25, 0.4, 0.625, 1, 1.25]) {
    for (const dpr of [1, 1.25, 2]) {
      const { renderer } = quadroEscalado(escala, dpr);
      const naTela = renderer.grade.celula * escala * dpr;

      assert.ok(
        Math.abs(naTela - Math.round(naTela)) < 1e-9,
        `escala ${escala} com dpr ${dpr}: a celula vale ${naTela} pixels do ` +
          `aparelho — meio pixel de borda se dissolve em dois e some`
      );
    }
  }
});

test("com o palco em 1:1 nada muda: o caso do OBS", () => {
  const { canvas, renderer } = quadroEscalado(1, 1, [1080, 1220]);

  assert.equal(canvas.style.width, "1080px");
  assert.equal(canvas.width, 1080);
  assert.equal(renderer.dpr, 1);
});

test("o teto da fonte vem da config, e a margem da regua acompanha", () => {
  // O caso real do streamer: OBS a 1080 de largura, grade de 25 colunas. A
  // celula tem ~40px e a conta da fonte pediria 34 — com o teto de 15 do
  // padrao a letra saia pequena demais, e depois do encode do video virava
  // borrao. Com o teto vindo da config, a letra cresce E a margem da regua
  // cresce junto: rotulo maior sem margem maior sairia por cima do quadro.
  const anterior = globalThis.window;
  globalThis.window = { devicePixelRatio: 1 };

  try {
    const { ctx } = contextoFalso();
    const canvas = { width: 0, height: 0, style: {}, getContext: () => ctx };
    const renderer = new Renderer(canvas);
    renderer.definirCanvas(25, 26);
    renderer.redimensionar(1080, 1220, 1);

    assert.equal(renderer.fonteRegua, 15, "sem config, o teto de sempre");

    renderer.definirTela({ fonte_regua_min: 12, fonte_regua_max: 26 });
    renderer.redimensionar(1080, 1220, 1);

    assert.equal(renderer.fonteRegua, 26, "o teto da config tem que valer");
    assert.ok(
      renderer.fonteRegua * 0.62 * 2 + 8 <= renderer.grade.faixaNumeros,
      `um rotulo de dois digitos (${Math.round(renderer.fonteRegua * 0.62 * 2)}px) ` +
        `nao cabe na margem de ${renderer.grade.faixaNumeros}px`
    );
    assert.ok(
      renderer.grade.celula >= 30,
      `a grade encolheu demais para caber a margem: celula de ${renderer.grade.celula}px`
    );
  } finally {
    globalThis.window = anterior;
  }
});

test("o fundo pinta o quadro INTEIRO, em qualquer dpr", () => {
  for (const dpr of DPRS) {
    const { canvas, comandos } = quadro(dpr);
    const fundos = comandos.filter((c) => c[0] === "fillRect");

    assert.ok(fundos.length > 0, `com dpr ${dpr} nao pintou fundo nenhum`);

    // "Algum retangulo cobre o quadro", e nao "todos cobrem".
    //
    // Enquanto a regua so escrevia texto, o unico `fillRect` do quadro era o
    // fundo e as duas frases davam no mesmo. Agora a regua pinta o proprio
    // campo com um `fillRect` pequeno, de proposito — e exigir que ELE cubra o
    // quadro seria exigir que a margem engolisse o desenho.
    //
    // O que se protege aqui continua sendo uma coisa so, e e a que importa:
    // sobrou faixa do canvas sem fundo? Se `larguraCss`/`alturaCss` errarem o
    // arredondamento, NENHUM retangulo cobre e o teste acusa.
    assert.ok(
      fundos.some((comando) => cobre(comando[1], canvas)),
      `com dpr ${dpr} nenhum fundo cobriu o canvas de ${canvas.width}x` +
        `${canvas.height}: ${fundos.map(tamanho).join(" | ")}`
    );
  }
});

/**
 * O pedido que este teste protege: "o modo arco iris ainda fica passando uma
 * div pra la e pra ca, em vez de simplesmente ficar mudando de cor os
 * quadrados ja pintados".
 *
 * Quem muda de cor sao as celulas JA pintadas: o desenho da comunidade vira o
 * arco-iris, o quadro vazio continua escuro, e a cor de uma celula nao e a da
 * vizinha — varias cores na tela ao mesmo tempo, que e o que o nome do evento
 * promete.
 */
test("no ARCO-IRIS quem muda de cor sao as celulas ja pintadas", () => {
  const anterior = globalThis.window;
  globalThis.window = { devicePixelRatio: 1 };

  try {
    const { ctx, comandos } = contextoFalso();
    const canvas = { width: 0, height: 0, style: {}, getContext: () => ctx };
    const renderer = new Renderer(canvas);
    const CELULA = [3, 4];
    const VIZINHA = [4, 4];
    renderer.definirCanvas(25, 26, [
      { x: CELULA[0], y: CELULA[1], color: "#ff3b5c" },
      { x: VIZINHA[0], y: VIZINHA[1], color: "#ff3b5c" },
    ]);
    renderer.redimensionar(1080, 1220);

    renderer.efeito = "arco_iris";
    renderer.desenhar(0);

    assert.equal(
      tintaDaCelula(comandos, renderer, ...CELULA),
      corDoArcoIris(...CELULA, 0),
      "a celula pintada nao saiu com a cor do arco-iris"
    );
    assert.equal(
      tintaDaCelula(comandos, renderer, 0, 0),
      undefined,
      "o quadro vazio ganhou cor do arco-iris"
    );

    comandos.length = 0;
    renderer.desenhar(0.5);

    assert.notEqual(
      tintaDaCelula(comandos, renderer, ...CELULA),
      corDoArcoIris(...CELULA, 0),
      "meio segundo depois a celula esta da mesma cor: o arco-iris ficou parado"
    );
    assert.notEqual(
      tintaDaCelula(comandos, renderer, ...CELULA),
      tintaDaCelula(comandos, renderer, ...VIZINHA),
      "duas celulas vizinhas saem da mesma cor: o desenho pisca de uma cor so"
    );

    // Sem evento, a celula volta a cor dela: o arco-iris e do EVENTO, nao da
    // celula. Se a cor ficasse, o desenho da comunidade nunca mais voltaria.
    comandos.length = 0;
    renderer.efeito = null;
    renderer.desenhar(0.9);
    assert.equal(tintaDaCelula(comandos, renderer, ...CELULA), "#ff3b5c");
  } finally {
    globalThis.window = anterior;
  }
});

/**
 * A HORA DO PIXEL e a hora dourada: a luz atravessa o quadro e as celulas que
 * ela alcanca pegam sol. Como no ARCO-IRIS, nada e desenhado por cima — quem
 * muda de cor sao as celulas JA pintadas, e a que esta fora da faixa continua
 * exatamente da cor que a pessoa escolheu.
 */
test("na HORA DO PIXEL a celula sob a faixa pega sol, e so ela", () => {
  const anterior = globalThis.window;
  globalThis.window = { devicePixelRatio: 1 };

  try {
    const { ctx, comandos } = contextoFalso();
    const canvas = { width: 0, height: 0, style: {}, getContext: () => ctx };
    const renderer = new Renderer(canvas);
    // Na diagonal 0, onde a faixa comeca em t=0.
    const ACESA = [0, 0];
    // Longe da faixa: continua na cor da pessoa em todo o teste.
    const LONGE = [10, 10];
    renderer.definirCanvas(25, 26, [
      { x: ACESA[0], y: ACESA[1], color: "#3d9bff" },
      { x: LONGE[0], y: LONGE[1], color: "#ff3b5c" },
    ]);
    renderer.redimensionar(1080, 1220);

    renderer.efeito = "brilho";
    renderer.desenhar(0);

    assert.equal(
      tintaDaCelula(comandos, renderer, ...ACESA),
      corDaCelula("brilho", ...ACESA, 0, "#3d9bff"),
      "a celula sob a faixa nao saiu com a cor acesa"
    );
    assert.notEqual(
      tintaDaCelula(comandos, renderer, ...ACESA),
      "#3d9bff",
      "a faixa passou e a celula nao mudou de cor"
    );
    assert.equal(
      tintaDaCelula(comandos, renderer, ...LONGE),
      "#ff3b5c",
      "a luz alcancou uma celula fora da faixa"
    );

    // A faixa anda: depois de passar, a celula volta a cor dela — o brilho e
    // do EVENTO, nao um verniz que fica.
    comandos.length = 0;
    renderer.desenhar(1.2);
    assert.equal(
      tintaDaCelula(comandos, renderer, ...ACESA),
      "#3d9bff",
      "a faixa ficou parada: a celula continua acesa depois de ela passar"
    );
  } finally {
    globalThis.window = anterior;
  }
});
