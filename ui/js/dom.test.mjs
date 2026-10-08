/**
 * O contrato de DOM entre as paginas e o JavaScript que as opera.
 *
 * Dois defeitos graves nasceram exatamente aqui. O `hud.evento()` procurava
 * `#evento-tempo` e `#evento-barra`, que nao existiam em `index.html`: o
 * `null.textContent` estourava DENTRO do laco de desenho, e o laco morre
 * quando um quadro estoura — a tela congelava sem erro visivel nenhum, e
 * parecia problema de tamanho de canvas.
 *
 * Nao da para pegar isso com um DOM falso. Um `getElementById` de mentira
 * devolve `null` tanto para o elemento que falta quanto para o que o proprio
 * JS cria por `innerHTML`, entao o teste passaria nos dois casos — inclusive
 * no quebrado. O que da para verificar, e que e o que interessa, e que todo
 * id pedido pelo JS existe em algum lugar: na pagina, ou no HTML que o
 * proprio JS escreve.
 *
 * Roda com `node --test ui/js/dom.test.mjs`.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const RAIZ = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const PAGINAS = [
  {
    nome: "tela do OBS",
    html: "ui/index.html",
    scripts: ["ui/js/hud.js", "ui/js/app.js"],
  },
  {
    nome: "painel de controle",
    html: "control/index.html",
    scripts: ["control/control.js"],
  },
];

const ler = (relativo) => readFileSync(join(RAIZ, relativo), "utf8");

const ids = (fonte) =>
  new Set([...fonte.matchAll(/id="([^"]+)"/g)].map((achado) => achado[1]));

function pedidos(fonte) {
  const nomes = [];
  for (const achado of fonte.matchAll(/\$\("([^"]+)"\)|getElementById\("([^"]+)"\)/g)) {
    nomes.push(achado[1] || achado[2]);
  }
  return [...new Set(nomes)];
}

for (const pagina of PAGINAS) {
  test(`todo id que o JS procura existe na ${pagina.nome}`, () => {
    const naPagina = ids(ler(pagina.html));
    const fonte = pagina.scripts.map(ler).join("\n");
    // O JS pode CRIAR o elemento que depois procura (banner montado por
    // `innerHTML`). Isso conta como existir.
    const criados = ids(fonte);

    const faltando = pedidos(fonte).filter(
      (id) => !naPagina.has(id) && !criados.has(id)
    );

    assert.deepEqual(
      faltando,
      [],
      `o JS procura por id que nao existe em lugar nenhum: ${faltando.join(", ")}`
    );
  });
}
