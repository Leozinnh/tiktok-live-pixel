/**
 * A camada de particulas tem que ser LIMPA a cada quadro.
 *
 * Este teste existe por causa de um relato de tela: "os efeito de explosao
 * fica parado um tempao no pixel e nunca sai".
 *
 * E eram duas coisas somadas. O `desenhar` pintava as faiscas por cima do que
 * ja estava la, e NINGUEM limpava o canvas de particulas — o unico
 * `clearRect` do projeto era o da grade. Como a camada de particulas e um
 * canvas proprio, separado, ela nao herda a limpeza da outra: cada faisca que
 * morria continuava acesa na tela para sempre, e o rastro se acumulava ate
 * virar um borrao preso naquele pixel.
 *
 * Um canvas nao tem outra coisa observavel alem da sequencia de comandos que
 * ele recebe — entao e isso que o teste olha.
 */

import test from "node:test";
import assert from "node:assert/strict";

import { Efeitos } from "./effects.js";

/** Um contexto que so anota o que mandaram ele fazer. */
function contextoFalso(largura = 800, altura = 600) {
  const comandos = [];
  const anotar = (nome) => (...args) => comandos.push([nome, ...args]);

  return {
    comandos,
    ctx: {
      canvas: { width: largura, height: altura },
      save: anotar("save"),
      restore: anotar("restore"),
      setTransform: anotar("setTransform"),
      clearRect: anotar("clearRect"),
      beginPath: anotar("beginPath"),
      arc: anotar("arc"),
      fill: anotar("fill"),
      stroke: anotar("stroke"),
      fillRect: anotar("fillRect"),
      globalCompositeOperation: "source-over",
      globalAlpha: 1,
      fillStyle: "",
      strokeStyle: "",
      lineWidth: 1,
    },
  };
}

test("a camada de particulas e limpa antes de desenhar", () => {
  const { ctx, comandos } = contextoFalso();
  const efeitos = new Efeitos();

  efeitos.desenhar(ctx);

  const limpeza = comandos.find((c) => c[0] === "clearRect");
  assert.ok(limpeza, "nada limpa o canvas de particulas: as faiscas ficam presas na tela");
  assert.deepEqual(
    limpeza.slice(1),
    [0, 0, 800, 600],
    "a limpeza tem que cobrir o canvas inteiro, nao um pedaco"
  );
});

test("a limpeza vem ANTES de qualquer desenho", () => {
  const { ctx, comandos } = contextoFalso();
  const efeitos = new Efeitos();

  // Uma pintura viva, para que haja o que desenhar.
  efeitos.registrarPintura({ x: 100, y: 100, cor: "#FF0000", celula: 20, efeito: null });
  efeitos.desenhar(ctx);

  const posicaoDaLimpeza = comandos.findIndex((c) => c[0] === "clearRect");
  const primeiroDesenho = comandos.findIndex(
    (c) => c[0] === "arc" || c[0] === "stroke" || c[0] === "fillRect"
  );

  assert.ok(posicaoDaLimpeza >= 0, "nada limpa o canvas de particulas");
  assert.ok(
    posicaoDaLimpeza < primeiroDesenho,
    "limpar depois de desenhar apaga justamente o quadro que acabou de sair"
  );
});

test("depois que as faiscas morrem, a tela fica limpa", () => {
  const { ctx, comandos } = contextoFalso();
  const efeitos = new Efeitos();

  efeitos.registrarPintura({ x: 100, y: 100, cor: "#00FF00", celula: 20, efeito: null });

  // Tempo de sobra para tudo morrer (a maior faisca dura 0.9 * 1.3 e a onda 0.55).
  for (let i = 0; i < 200; i += 1) efeitos.atualizar(1 / 60);

  comandos.length = 0;
  efeitos.desenhar(ctx);

  const desenhou = comandos.some((c) => c[0] === "arc" || c[0] === "fillRect");
  assert.equal(desenhou, false, "sobrou coisa viva depois do tempo de vida acabar");
});
