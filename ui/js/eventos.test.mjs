/**
 * O desenho dos eventos, na tela.
 *
 * Este teste existe porque o servidor MANDA o efeito e a tela nao desenhava
 * nada com ele: `event_start` carregava `effect: "arco_iris"` desde o primeiro
 * dia, chegava inteiro no navegador, e ninguem lia. O ARCO-IRIS era um banner
 * com um contador e mais nada.
 *
 * Um canvas nao tem outra coisa observavel alem da sequencia de comandos que
 * ele recebe — entao e isso que o teste olha. As tres perguntas sao as que
 * importam: o efeito DESENHA, ele ANIMA, e um evento sem efeito nao pinta
 * nada por cima do quadro.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { desenharEvento, deslocamentoDoEvento } from "./eventos.js";

const AREA = { x: 55, y: 111, w: 1000, h: 1020 };

/** Um contexto que so anota o que mandaram ele fazer. */
function contextoFalso() {
  const comandos = [];
  const anotar = (nome) => (...args) => comandos.push([nome, ...args]);

  return {
    comandos,
    ctx: {
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
      globalCompositeOperation: "source-over",
      globalAlpha: 1,
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
    },
  };
}

/** Tudo que o efeito mandou pintar, na ordem. */
function pinturas(comandos) {
  return comandos
    .filter((c) => c[0] === "fillRect" || c[0] === "strokeRect")
    .map((c) => c.join(" "));
}

test("cada efeito pinta alguma coisa por cima do quadro", () => {
  for (const efeito of ["arco_iris", "caos", "desafio"]) {
    const { ctx, comandos } = contextoFalso();
    desenharEvento(ctx, efeito, AREA, 0.7);

    assert.ok(
      pinturas(comandos).length > 0,
      `o efeito ${efeito} nao pintou nada: e um banner com contador e so`
    );
  }
});

test("o efeito ANIMA: a tinta de agora nao e a de um segundo atras", () => {
  for (const efeito of ["arco_iris", "caos", "desafio"]) {
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

test("so o CAOS treme a tela, e ele treme mesmo", () => {
  for (const efeito of [null, "arco_iris", "desafio", "inventado"]) {
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
