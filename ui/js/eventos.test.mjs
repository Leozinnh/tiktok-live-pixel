/**
 * O desenho dos eventos, na tela.
 *
 * Este teste existe porque o servidor MANDA o efeito e a tela nao desenhava
 * nada com ele: `event_start` carregava `effect: "arco_iris"` desde o primeiro
 * dia, chegava inteiro no navegador, e ninguem lia. O ARCO-IRIS era um banner
 * com um contador e mais nada.
 *
 * Hoje sao dois tipos de efeito, e o teste separa os dois:
 *
 * - os ENFEITES (do glitch do CAOS a pelicula do FILME ANTIGO) desenham por
 *   cima do quadro;
 * - os efeitos de CELULA (ARCO-IRIS, NEGATIVO e companhia) trocam a cor das
 *   celulas pintadas, e por isso a conta de cor deles e testada aqui, celula
 *   a celula. BRILHO, NEVE e FILME sao hibridos: alem da cor, tem enfeite
 *   proprio — que e o que aparece quando o quadro esta vazio.
 *
 * A lista de enfeites sai do proprio mapa `ENFEITES` do modulo, e o catalogo
 * de efeitos que rodam de verdade sai do `config.json` — o mesmo arquivo que
 * o servidor le. Efeito novo entra no desenho e nos testes na mesma edicao,
 * sem lista paralela para esquecer.
 *
 * Um canvas nao tem outra coisa observavel alem da sequencia de comandos que
 * ele recebe — entao e isso que o teste olha.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  ENFEITES,
  corDaCelula,
  corDoArcoIris,
  desenharEvento,
  deslocamentoDoEvento,
} from "./eventos.js";

const AREA = { x: 55, y: 111, w: 1000, h: 1020 };

/**
 * Todo enfeite conhecido, pelo nome que o servidor manda.
 *
 * A lista sai do proprio mapa (`ENFEITES`) de proposito: efeito novo entra no
 * desenho e nos testes na mesma edicao — sem uma segunda lista aqui para
 * esquecer de atualizar.
 */
const NOMES = Object.keys(ENFEITES);

/** Os enfeites que TAMBEM mudam a cor das celulas (a lista hibrida). */
const HIBRIDOS = ["brilho", "neve", "filme"];

/** Os efeitos que so mudam a cor das celulas: nao pintam por cima. */
const SO_CELULA = ["arco_iris", "negativo"];

/** Um contexto que so anota o que mandaram ele fazer. */
function contextoFalso() {
  const comandos = [];
  const ctx = {
    globalCompositeOperation: "source-over",
    globalAlpha: 1,
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
  };

  // A tinta do momento vai junto do comando: "pintou um retangulo" diz pouco —
  // ha teste que precisa saber o retangulo, a cor E a mistura (o veu da
  // TEMPESTADE e escuro e vem ANTES da chuva, e e isso que o separa do
  // BRILHO; so a lista de retangulos nao provaria nenhuma das duas coisas).
  const anotar = (nome) => (...args) =>
    comandos.push([
      nome,
      ...args,
      ctx.fillStyle,
      ctx.globalAlpha,
      ctx.globalCompositeOperation,
    ]);

  Object.assign(ctx, {
    save: anotar("save"),
    restore: anotar("restore"),
    beginPath: anotar("beginPath"),
    rect: anotar("rect"),
    clip: anotar("clip"),
    fillRect: anotar("fillRect"),
    strokeRect: anotar("strokeRect"),
    moveTo: anotar("moveTo"),
    lineTo: anotar("lineTo"),
    stroke: anotar("stroke"),
  });

  return { comandos, ctx };
}

/** Tudo que o efeito mandou pintar, na ordem. */
function pinturas(comandos) {
  return comandos
    .filter((c) => c[0] === "fillRect" || c[0] === "strokeRect")
    .map((c) => c.join(" "));
}

test("cada ENFEITE pinta alguma coisa por cima do quadro", () => {
  for (const efeito of NOMES) {
    const { ctx, comandos } = contextoFalso();
    desenharEvento(ctx, efeito, AREA, 0.7);

    assert.ok(
      pinturas(comandos).length > 0,
      `o efeito ${efeito} nao pintou nada: e um banner com contador e so`
    );
  }
});

test("a HORA DO PIXEL mostra a festa mesmo com o quadro VAZIO", () => {
  // O pedido que criou este teste: "o efeito hora do pixel so mostra o
  // badge". O feixe do brilho so acende o que JA esta pintado — num quadro
  // vazio ele nao tem o que acender, e o evento virava so o banner. A moldura
  // e a chuva sao a festa que nao depende de ninguem.
  for (const t of [0, 0.9, 4.2]) {
    const { ctx, comandos } = contextoFalso();
    desenharEvento(ctx, "brilho", AREA, t);
    assert.ok(
      pinturas(comandos).length > 0,
      `com t=${t} a hora do pixel nao pintou nada: num quadro vazio ela e so o badge`
    );
  }
});

test("a TEMPESTADE escurece o quadro ANTES de chover", () => {
  // O veu da noite e o que separa a TEMPESTADE da outra chuva do projeto:
  // ele cobre o quadro INTEIRO, no escuro e em `source-over` (somar luz nao
  // escurece nada), e vem antes de qualquer gota. E o unico efeito que TAPA o
  // desenho de proposito — e o teste existe porque a alternativa era ele cair
  // no `else` do despacho e virar uma chuva dourada sem ninguem notar.
  const { ctx, comandos } = contextoFalso();
  desenharEvento(ctx, "tempestade", AREA, 0.7);

  const primeiro = comandos.find((c) => c[0] === "fillRect");
  assert.ok(primeiro, "a tempestade nao pintou nada");

  // A posicao dos campos e a do `contextoFalso`: nome, x, y, w, h, cor,
  // alfa, mistura.
  const [, x, y, w, h, , alfa, mistura] = primeiro;
  assert.deepEqual([x, y, w, h], [AREA.x, AREA.y, AREA.w, AREA.h], "a tempestade comecou por outra coisa que nao a noite");
  assert.equal(mistura, "source-over", "o veu da noite somou luz em vez de escurecer");
  assert.ok(alfa < 1, "o veu da noite foi pintado opaco: tapou o desenho da comunidade");
});

test("a moldura do BRILHO fica FORA do quadro — no vao da regua", () => {
  // O corte do quadro (o `clip`) comeria qualquer coisa desenhada para fora
  // dele; a moldura so aparece porque e desenhada ANTES do corte. Se alguem a
  // mover para dentro do laco cortado, este teste acusa: ela tem que ter
  // pelo menos uma volta comecando para fora da area da grade.
  const { ctx, comandos } = contextoFalso();
  desenharEvento(ctx, "brilho", AREA, 0.4);

  const molduras = comandos.filter((c) => c[0] === "strokeRect");
  assert.ok(molduras.length > 0, "a moldura nao foi desenhada");
  assert.ok(
    molduras.some((m) => m[1] < AREA.x || m[2] < AREA.y),
    "a moldura foi desenhada dentro do quadro"
  );
});

test("os efeitos SO de celula nao pintam NADA por cima", () => {
  // O pedido que este teste protege: "o modo arco iris ainda fica passando uma
  // div pra la e pra ca, em vez de simplesmente mudar de cor os quadrados ja
  // pintados". Se alguem reintroduzir uma faixa por cima do quadro, ela
  // reaparece aqui como comando de desenho — e o teste acusa. (O BRILHO, a
  // NEVE e o FILME tambem trocam a cor das celulas, mas tem enfeite proprio —
  // por isso eles nao entram nesta lista.)
  for (const efeito of SO_CELULA) {
    for (const t of [0, 0.7, 3.1]) {
      const { ctx, comandos } = contextoFalso();
      desenharEvento(ctx, efeito, AREA, t);
      assert.deepEqual(
        comandos,
        [],
        `com t=${t} o ${efeito} mexeu no quadro por cima: ele so pode trocar a cor das celulas`
      );
    }
  }
});

test("o ENFEITE ANIMA: a tinta de agora nao e a de um segundo atras", () => {
  for (const efeito of NOMES) {
    const a = contextoFalso();
    const b = contextoFalso();

    desenharEvento(a.ctx, efeito, AREA, 0);
    desenharEvento(b.ctx, efeito, AREA, 0.37);

    const tintaA = JSON.stringify([a.ctx.fillStyle, a.ctx.globalAlpha, pinturas(a.comandos)]);
    const tintaB = JSON.stringify([b.ctx.fillStyle, b.ctx.globalAlpha, pinturas(b.comandos)]);

    assert.notEqual(
      tintaA,
      tintaB,
      `o efeito ${efeito} desenha a mesma coisa em todo instante: virou um adesivo`
    );
  }
});

test("a cor do ARCO-IRIS anima: a celula de agora nao e a de um segundo atras", () => {
  assert.notEqual(
    corDoArcoIris(3, 4, 0),
    corDoArcoIris(3, 4, 1),
    "a celula ficou da mesma cor com o tempo passando: o arco-iris virou um adesivo"
  );
});

test("a cor do ARCO-IRIS sai da POSICAO: duas celulas vizinhas nao sao gemeas", () => {
  // Se a cor dependesse da ordem de pintura (ou fosse uma so para o quadro
  // inteiro), o desenho inteiro piscaria junto, de uma cor so. O arco-iris
  // precisa de varias cores na tela AO MESMO TEMPO.
  assert.notEqual(corDoArcoIris(3, 4, 0.5), corDoArcoIris(4, 4, 0.5));
  assert.notEqual(corDoArcoIris(3, 4, 0.5), corDoArcoIris(3, 5, 0.5));
});

test("a cor do ARCO-IRIS e um hex de verdade, em qualquer instante", () => {
  // Quem desenha a celula passa esta cor por `clarear` e `rgba`, que so sabem
  // ler hex: um "hsl(...)" aqui viraria BRANCO nas duas.
  for (const t of [0, 0.31, 1.7, 12.9, 359.99, 1000]) {
    for (const [x, y] of [[0, 0], [24, 25], [7, 19]]) {
      assert.match(
        corDoArcoIris(x, y, t),
        /^#[0-9a-f]{6}$/,
        `corDoArcoIris(${x}, ${y}, ${t}) nao saiu hex`
      );
    }
  }
});

test("sem evento — ou com um efeito que ninguem conhece — nao pinta nada", () => {
  for (const efeito of [null, undefined, "", "inventado"]) {
    const { ctx, comandos } = contextoFalso();
    desenharEvento(ctx, efeito, AREA, 1.3);
    assert.deepEqual(
      comandos,
      [],
      `o efeito ${JSON.stringify(efeito)} mexeu no quadro sem ser chamado`
    );
  }
});

// --------------------------------------------------------------------------
// Os efeitos de celula, pelo `corDaCelula`
// --------------------------------------------------------------------------

/** A soma dos canais de um hex — o quanto a cor e clara. */
function claridade(hex) {
  const n = Number.parseInt(hex.slice(1), 16);
  return ((n >> 16) & 255) + ((n >> 8) & 255) + (n & 255);
}

test("sem efeito de celula a cor de quem pintou volta INTACTA", () => {
  // A identidade e o contrato: com um enfeite no ar (ou sem evento nenhum) o
  // renderer pergunta a cor celula a celula, e a resposta tem que ser
  // exatamente a cor que a pessoa escolheu — nao um tom parecido. Todo
  // enfeite PURO entra na lista; os hibridos ficam de fora porque mexem na
  // cor de proposito.
  const puros = NOMES.filter((nome) => !HIBRIDOS.includes(nome));
  for (const efeito of [null, undefined, "", "inventado", ...puros]) {
    assert.equal(
      corDaCelula(efeito, 3, 4, 0.5, "#3d9bff"),
      "#3d9bff",
      `o efeito ${JSON.stringify(efeito)} mexeu na cor de uma celula`
    );
  }
});

test("cada efeito de celula mexe na cor de quem pintou, e devolve hex", () => {
  // A outra metade do contrato da identidade: quem DEVE mudar a cor, muda —
  // e devolve hex, que e o unico formato que `clarear` e `rgba` leem.
  const originais = ["#3d9bff", "#ff3b5c", "#3dff8a"];
  for (const efeito of [...SO_CELULA, ...HIBRIDOS]) {
    for (const original of originais) {
      const cor = corDaCelula(efeito, 3, 4, 0.5, original);
      assert.notEqual(cor, original, `o efeito ${efeito} deixou a cor intacta`);
      assert.match(cor, /^#[0-9a-f]{6}$/, `o efeito ${efeito} nao devolveu hex: ${cor}`);
    }
  }
});

test("o NEGATIVO inverte canal a canal", () => {
  // A definicao do efeito, presa ao numero: quem escolheu #3d9bff ve #c26400.
  assert.equal(corDaCelula("negativo", 0, 0, 0, "#3d9bff"), "#c26400");
  assert.equal(corDaCelula("negativo", 7, 9, 5, "#000000"), "#ffffff");
});

test("todo efeito do config.json desenha alguma coisa na tela", () => {
  // A costura entre os dois lados: o servidor le o catalogo do config.json e
  // manda o `effect` no `event_start`. Se o nome la e o daqui nao baterem, o
  // evento roda com banner e mais nada — e ninguem descobre ate a LIVE. Este
  // teste le o MESMO arquivo que o servidor le.
  const cfg = JSON.parse(
    readFileSync(new URL("../../config.json", import.meta.url), "utf8")
  );
  const catalogo = cfg.events.catalog;
  assert.ok(catalogo.length > 0, "o catalogo de eventos do config esta vazio");

  for (const evento of catalogo) {
    const { ctx, comandos } = contextoFalso();
    desenharEvento(ctx, evento.effect, AREA, 0.7);
    const pintou = pinturas(comandos).length > 0;
    assert.equal(
      pintou,
      !SO_CELULA.includes(evento.effect),
      `"${evento.name}" (effect: ${JSON.stringify(evento.effect)}) ${
        pintou ? "pintou por cima" : "nao pintou nada por cima"
      } — o nome do efeito no config e o desenho aqui nao batem`
    );
  }
});

test("o ARCO-IRIS sai pelo corDaCelula igual a conta da matiz", () => {
  assert.equal(corDaCelula("arco_iris", 3, 4, 0.5, "#3d9bff"), corDoArcoIris(3, 4, 0.5));
});

test("o BRILHO acende a celula sob a faixa — e so ela", () => {
  const original = "#3d9bff";

  // t=0: a faixa esta na diagonal 0. A celula (0,0) esta no miolo dela; a
  // (10,10) esta longe.
  const aceso = corDaCelula("brilho", 0, 0, 0, original);

  assert.notEqual(aceso, original, "a celula sob a faixa saiu com a cor de sempre");
  assert.ok(
    claridade(aceso) > claridade(original),
    `a faixa ESCURECEU a celula: ${aceso} e mais escura que ${original}`
  );
  assert.match(aceso, /^#[0-9a-f]{6}$/, "a cor do brilho nao saiu hex");

  assert.equal(
    corDaCelula("brilho", 10, 10, 0, original),
    original,
    "a luz acendeu uma celula FORA da faixa"
  );
});

test("a faixa do BRILHO atravessa: a mesma celula sai do sol", () => {
  const original = "#3d9bff";
  assert.notEqual(corDaCelula("brilho", 0, 0, 0, original), original, "no inicio, (0,0) esta sob a luz");

  // 1,2s depois a faixa ja andou ~11 celulas e deixou a (0,0) para tras.
  assert.equal(
    corDaCelula("brilho", 0, 0, 1.2, original),
    original,
    "a faixa ficou parada: a celula continua acesa depois de ela passar"
  );
  // E quem esta na posicao nova acende. A faixa anda para a direita na
  // diagonal, entao a celula vizinha de onde ela estava e a proxima a acender.
  assert.notEqual(
    corDaCelula("brilho", 5, 5, 1.2, original),
    original,
    "a faixa nao chegou na diagonal seguinte"
  );
});

test("so o CAOS treme a tela, e ele treme mesmo", () => {
  for (const efeito of [null, "arco_iris", "brilho", "desafio", "rastro", "inventado"]) {
    assert.deepEqual(
      deslocamentoDoEvento(efeito, 0.8),
      { dx: 0, dy: 0 },
      `${efeito} nao pode arrastar a grade`
    );
  }

  // O tremor nao e decorativo: e o mesmo efeito em instantes diferentes que
  // faz a tela parecer que esta apanhando.
  const um = deslocamentoDoEvento("caos", 0);
  const dois = deslocamentoDoEvento("caos", 0.13);
  assert.notEqual(`${um.dx},${um.dy}`, `${dois.dx},${dois.dy}`, "o CAOS ficou parado");

  // E e pequeno: tremer 30px tira a grade de dentro da tela.
  for (const t of [0, 0.13, 1, 2.7, 9.9]) {
    const { dx, dy } = deslocamentoDoEvento("caos", t);
    assert.ok(Math.abs(dx) <= 4 && Math.abs(dy) <= 4, `o CAOS tremeu ${dx},${dy} — longe demais`);
  }
});
