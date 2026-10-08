/**
 * Os testes da geometria. `node --test ui/js/geometry.test.mjs`.
 *
 * Sao poucos de proposito: se `rotuloDe` ou `calcularGrade` errarem, o
 * desenho na tela e a coordenada que o backend entende deixam de ser a
 * mesma conta — e a pessoa pinta H5 vendo o pixel aparecer em outro lugar.
 * Nao ha bug pior neste projeto que esse, entao e o que se testa.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  analisarRotulo,
  bordasDaGrade,
  calcularGrade,
  celulaParaPixel,
  ehMarco,
  escalaParaCaber,
  faixasParaFonte,
  fonteDoRotulo,
  pixelParaCelula,
  rotuloDaColuna,
  rotuloDe,
} from "./geometry.js";

test("a coluna segue a indexacao de planilha, igual ao backend", () => {
  assert.equal(rotuloDaColuna(0), "A");
  assert.equal(rotuloDaColuna(7), "H");
  assert.equal(rotuloDaColuna(25), "Z");
  assert.equal(rotuloDaColuna(26), "AA");
  assert.equal(rotuloDaColuna(27), "AB");
  assert.equal(rotuloDaColuna(51), "AZ");
  assert.equal(rotuloDaColuna(52), "BA");
});

test("o rotulo completo e letra mais numero", () => {
  assert.equal(rotuloDe(7, 5), "H5");
  assert.equal(rotuloDe(0, 0), "A0");
  assert.equal(rotuloDe(25, 50), "Z50");
});

test("a grade calculada cabe na area e nao estoura", () => {
  const grade = calcularGrade({
    cols: 26,
    rows: 51,
    largura: 1080,
    altura: 1370,
  });

  assert.equal(grade.larguraGrade, grade.celula * 26);
  assert.equal(grade.alturaGrade, grade.celula * 51);
  assert.ok(grade.origemX >= grade.faixaNumeros, "a grade invade a faixa dos numeros");
  assert.ok(
    grade.origemX + grade.larguraGrade <= 1080,
    "a grade sai pela direita"
  );
  assert.ok(grade.origemY >= grade.faixaLetras, "a grade invade a faixa das letras");
  assert.ok(
    grade.origemY + grade.alturaGrade <= 1370,
    "a grade sai por baixo"
  );
});

test("expandir o mapa encolhe a celula em vez de estourar a tela", () => {
  const area = { largura: 1080, altura: 1370 };
  const pequeno = calcularGrade({ cols: 26, rows: 51, ...area });
  const grande = calcularGrade({ cols: 100, rows: 100, ...area });

  assert.ok(grande.celula < pequeno.celula);
  assert.ok(grande.origemX + grande.larguraGrade <= 1080);
  assert.ok(grande.origemY + grande.alturaGrade <= 1370);
});

test("celula e pixel sao inversos um do outro", () => {
  const grade = calcularGrade({ cols: 26, rows: 51, largura: 1080, altura: 1370 });

  for (const [x, y] of [
    [0, 0],
    [7, 5],
    [25, 50],
    [13, 26],
  ]) {
    const { px, py } = celulaParaPixel(grade, x, y);
    // O centro da celula, que e onde o dedo de quem toca cai.
    const volta = pixelParaCelula(grade, px + grade.celula / 2, py + grade.celula / 2);
    assert.deepEqual(volta, { x, y }, `(${x}, ${y}) nao voltou`);
  }
});

test("o rotulo escrito a mao vira celula, nas mesmas formas que a audiencia usa", () => {
  // O painel do operador precisa ler "H5" EXATAMENTE como o parser do backend
  // le. Se divergirem, o painel inspeciona um pixel e o jogo pinta outro — e
  // quem olha o painel conclui que o jogo esta errado.
  // Esta lista e a MESMA de `tests/test_coordinates.py::test_formas_aceitas_
  // resolvem_para_h5`. As duas listas andam juntas de proposito: o que o
  // backend pinta e o que o painel precisa saber ler sao a mesma coisa.
  for (const texto of [
    "H5",
    "h5",
    "H 5",
    "h 5",
    "H-5",
    "  H5  ",
    "H\t5",
    "/H5",
    "/pixel H5",
    "/pintar H5",
    "/p H5",
    "/PINTAR h5",
  ]) {
    assert.deepEqual(analisarRotulo(texto), { x: 7, y: 5 }, `${texto} nao virou H5`);
  }

  assert.deepEqual(analisarRotulo("A0"), { x: 0, y: 0 });
  assert.deepEqual(analisarRotulo("AA5"), { x: 26, y: 5 });
  assert.deepEqual(analisarRotulo("z50"), { x: 25, y: 50 });
});

test("o que nao e coordenada devolve null em vez de um chute", () => {
  // A regra do spec e "nunca adivinhar": pintar o pixel errado e pior do que
  // mostrar um erro. Cada um destes aqui tem que virar erro visivel.
  for (const texto of [
    "",
    "   ",
    "1H",       // numero antes da letra
    "ABC",      // sem numero
    "H",        // so letra
    "5",        // so numero
    "H5X",      // letra sobrando
    "girafa",   // comentario comum
    "H-5-6",    // dois tracos nao sao separador
    "H--5",     // idem
    "/pixel",   // comando sem coordenada
    // Sem o tamanho do canvas nao da para recusar "/pintar 5 5": a sobra
    // ("PINTAR55") e uma coluna bem formada, so grande demais. Quem recusa
    // esse e o teste da tabela compartilhada, que passa o tamanho.
    null,
    undefined,
  ]) {
    assert.equal(analisarRotulo(texto), null, `${texto} deveria ser recusado`);
  }
});

test("com o tamanho do canvas, o painel responde igual ao backend", () => {
  // A coluna da direita e a resposta LITERAL de
  // `game/coordinates.py:parse_coordenada` para o mesmo canvas 50x51 —
  // conferida rodando os dois lado a lado. O painel do operador passa o
  // tamanho do canvas de proposito: sem ele, "/pintar 5 5" viraria a coluna
  // PINTAR (indice enorme) e o painel diria que a coordenada existe.
  const tabela = [
    ["H5", { x: 7, y: 5 }],
    ["h5", { x: 7, y: 5 }],
    ["H 5", { x: 7, y: 5 }],
    ["h 5", { x: 7, y: 5 }],
    ["H-5", { x: 7, y: 5 }],
    ["  H5  ", { x: 7, y: 5 }],
    ["H\t5", { x: 7, y: 5 }],
    ["/H5", { x: 7, y: 5 }],
    ["/pixel H5", { x: 7, y: 5 }],
    ["/pintar H5", { x: 7, y: 5 }],
    ["/p H5", { x: 7, y: 5 }],
    ["/PINTAR h5", { x: 7, y: 5 }],
    ["A51", null],
    ["AA5", { x: 26, y: 5 }],
    ["1H", null],
    ["ABC", null],
    ["H", null],
    ["", null],
    ["H5extra", null],
    ["girafa", null],
    ["H-5-6", null],
    ["H--5", null],
    ["/pixel", null],
    ["/pintar 5 5", null],
  ];

  for (const [texto, esperado] of tabela) {
    assert.deepEqual(
      analisarRotulo(texto, 50, 51),
      esperado,
      `"${texto}" divergiu do backend`
    );
  }
});

test("o rotulo da coluna encolhe quando a coluna tem duas letras", () => {
  // Com 50 colunas a celula fica em 20px e o rotulo passa a ter duas letras
  // ("AA"). Na mesma fonte que servia para "H", "AA" encosta na celula ao
  // lado — e a audiencia precisa LER a coluna para saber o que comentar.
  assert.equal(fonteDoRotulo(23, 1), 15, "26 colunas: uma letra, fonte cheia");
  assert.equal(fonteDoRotulo(20, 1), 14, "50 colunas, letra unica: ainda cheia");
  assert.equal(fonteDoRotulo(20, 2), 12, "50 colunas, duas letras: encolhe");
});

test("as marcas da regua caem de cinco em cinco", () => {
  // A regua tem duas testas: o tracinho comprido na margem e o rotulo aceso.
  // As duas perguntam a MESMA funcao, e e isso que este teste protege — se uma
  // delas divergir da outra, a regua passa a mentir sobre onde estao os marcos,
  // e quem conta de cinco em cinco para achar a coluna H conta errado.
  assert.equal(ehMarco(0), true, "a primeira coluna e um marco");
  assert.equal(ehMarco(5), true);
  assert.equal(ehMarco(50), true, "a ultima linha da grade e um marco");
  assert.equal(ehMarco(1), false);
  assert.equal(ehMarco(7), false);
  assert.equal(ehMarco(-5), false, "fora da grade nao e marco");

  // E o marco e as LETRAS que a audiencia escreve: H5 nao cai num marco, mas
  // as linhas 5, 10 e 50 caem — que sao as que alguem conta de cabeca.
  for (const y of [5, 10, 35, 50]) assert.ok(ehMarco(y), `a linha ${y} deveria ser marco`);
});

test("a fonte do rotulo nunca fica ilegivel nem gigante", () => {
  assert.equal(fonteDoRotulo(4, 3), 9, "celula minuscula nao vira fonte de 1px");
  assert.equal(fonteDoRotulo(80, 1), 15, "celula enorme nao vira letreiro");
});

test("os limites da fonte vem da config, e sem ela nada muda", () => {
  // O teto de 15 era do tempo da grade de 50 colunas. Numa grade de 25 a
  // celula tem 40px e a conta sozinha pediria 34 — o teto cortava a letra
  // pela metade, e depois do encode do TikTok ela virava um borrao. Com o
  // teto vindo da config, quem transmite decide o tamanho que da para ler.
  assert.equal(fonteDoRotulo(40, 1, { max: 26 }), 26, "o teto novo deixa a letra crescer");
  assert.equal(
    fonteDoRotulo(40, 1),
    15,
    "sem config, o padrao historico continua valendo"
  );
  assert.equal(
    fonteDoRotulo(8, 1, { min: 12, max: 26 }),
    12,
    "o piso vence a celula apertada"
  );
  assert.equal(
    fonteDoRotulo(40, 3, { min: 12, max: 26 }),
    Math.floor((40 - 4) / (0.62 * 3)),
    "o encaixe na largura ainda manda quando e menor que o teto"
  );
});

test("a margem da regua cresce com a fonte, e nunca encolhe do que ja era", () => {
  // O rotulo grande sem margem grande sairia desenhado por cima do quadro —
  // a coordenada sairia justamente de fora do desenho, que e onde ela precisa
  // estar. E a fonte pequena nao pode encolher a margem que ja existia: as
  // faixas de hoje sao o minimo.
  const grande = faixasParaFonte(26, 40);
  assert.ok(grande.faixaLetras > 34, `faixa de cima ficou em ${grande.faixaLetras}`);
  assert.ok(grande.faixaNumeros > 42, `faixa da esquerda ficou em ${grande.faixaNumeros}`);

  assert.deepEqual(
    faixasParaFonte(12, 20),
    { faixaLetras: 34, faixaNumeros: 42 },
    "fonte pequena mantem a margem de sempre"
  );
});

test("pixel fora da grade devolve null em vez de uma celula inventada", () => {
  const grade = calcularGrade({ cols: 26, rows: 51, largura: 1080, altura: 1370 });

  assert.equal(pixelParaCelula(grade, 0, 0), null);
  assert.equal(pixelParaCelula(grade, 1079, 1369), null);
  assert.equal(
    pixelParaCelula(grade, grade.origemX + grade.larguraGrade + 5, grade.origemY),
    null
  );
});

// ---------------------------------------------------------------------
// As bordas da grade
//
// Estes testes existem por causa de um relato de tela: "alguns quadrado
// estao com border diferentes dos outros, tem quadrados com e sem".
//
// O desenho da grade usa `origemX + x * celula`, e a celula e um inteiro em
// pixels de CSS. Parece redondo — mas o canvas do OBS roda com
// `ctx.scale(dpr, dpr)`, e um monitor com escala de 125% no Windows tem
// `devicePixelRatio = 1.25`. Nesse mundo, um traco de 1px numa coordenada
// inteira de CSS cai no meio de um pixel do aparelho: metade da tinta num
// pixel, metade no vizinho. Uns tracos caem em cheio e ficam nitidos, outros
// se dissolvem em dois — e como a cor da grade ja e quase transparente, os
// que se dissolvem simplesmente SOMEM. Era isso que fazia uns quadrados
// terem borda e outros nao.

test("toda borda de celula cai em cima de um pixel do aparelho", () => {
  // 1.25 e a escala real de um monitor de Windows a 125% — o caso que
  // produziu o defeito.
  for (const dpr of [1, 1.25, 1.5, 2]) {
    const grade = calcularGrade({ cols: 50, rows: 51, largura: 1080, altura: 1220 });
    const { xs, ys } = bordasDaGrade(grade, dpr);

    for (const valor of [...xs, ...ys]) {
      assert.equal(
        Number.isInteger(valor * dpr),
        true,
        `borda ${valor} nao cai no pixel do aparelho com dpr ${dpr}: o traco sai borrado`
      );
    }
  }
});

test("com dpr 1 as bordas sao exatamente as de antes", () => {
  // No OBS a pagina roda a 1. O conserto nao pode mexer no que ja estava certo.
  const grade = calcularGrade({ cols: 50, rows: 51, largura: 1080, altura: 1220 });
  const { xs, ys } = bordasDaGrade(grade, 1);

  assert.equal(xs.length, 51);
  assert.equal(ys.length, 52);
  assert.equal(xs[0], grade.origemX);
  assert.equal(ys[0], grade.origemY);
  assert.equal(xs[50], grade.origemX + grade.larguraGrade);
  assert.equal(ys[51], grade.origemY + grade.alturaGrade);
});

test("toda celula tem o MESMO tamanho, e a grade cabe, em qualquer zoom", () => {
  const LARGURA = 1080;
  const ALTURA = 1220;

  // Os `dpr` que um navegador produz de verdade: os niveis de zoom do Chrome
  // (25% a 300%) vezes a escala do Windows (100%, 125%, 150%). O 0.625 e o
  // 0.9 sao os que doiam — a celula caia no meio de um pixel do aparelho e as
  // colunas alternavam de largura, umas com borda e outras sem.
  const NIVEIS = [
    0.25, 0.33, 0.5, 0.625, 0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 2, 2.5, 3,
  ];

  for (const dpr of NIVEIS) {
    const grade = calcularGrade({
      cols: 50,
      rows: 51,
      largura: LARGURA,
      altura: ALTURA,
      dpr,
    });
    const { xs, ys } = bordasDaGrade(grade, dpr);

    const larguras = new Set();
    for (let x = 0; x < grade.cols; x += 1) {
      larguras.add(Math.round((xs[x + 1] - xs[x]) * dpr));
    }
    assert.equal(
      larguras.size,
      1,
      `dpr ${dpr}: as colunas sairam de ${[...larguras].sort().join("/")} pixels do aparelho`
    );

    const alturas = new Set();
    for (let y = 0; y < grade.rows; y += 1) {
      alturas.add(Math.round((ys[y + 1] - ys[y]) * dpr));
    }
    assert.equal(
      alturas.size,
      1,
      `dpr ${dpr}: as linhas sairam de ${[...alturas].sort().join("/")} pixels do aparelho`
    );

    // A grade encolhe para caber, mas NUNCA vaza da area que tem: vazar
    // significa coluna escondida atras do rotulo, ou celula fora da tela.
    assert.ok(
      xs[0] >= 0 && xs[grade.cols] <= LARGURA,
      `dpr ${dpr}: a grade vazou na horizontal, de ${xs[0]} a ${xs[grade.cols]} em ${LARGURA}`
    );
    assert.ok(
      ys[0] >= 0 && ys[grade.rows] <= ALTURA,
      `dpr ${dpr}: a grade vazou na vertical, de ${ys[0]} a ${ys[grade.rows]} em ${ALTURA}`
    );

    // E toda fronteira cai em cima de um pixel do aparelho — e o que faz o fio
    // de 1px existir em vez de se dissolver em dois e sumir.
    for (const valor of xs) {
      assert.ok(
        Math.abs(valor * dpr - Math.round(valor * dpr)) < 1e-6,
        `dpr ${dpr}: a fronteira ${valor} nao caiu em pixel do aparelho`
      );
    }
  }
});

test("o palco cobre a janela EXATAMENTE, em qualquer formato", () => {
  const palco = [1080, 1920];
  const JANELAS = [
    [1080, 1920], // o OBS, no tamanho nominal
    [540, 960], // metade, mesmo formato
    [2160, 3840], // o dobro
    [900, 1700], // vertical, mais alta que 9:16
    [1000, 1600], // vertical, mais larga que 9:16
    [1366, 768], // tela de PC deitada
    [2560, 1440],
    [500, 2000], // uma tira
  ];

  for (const [larguraJanela, alturaJanela] of JANELAS) {
    const { escala, larguraProjeto } = escalaParaCaber(larguraJanela, alturaJanela, ...palco);

    // O que "100% no navegador" quer dizer, em duas contas: depois da escala,
    // a largura do palco E a altura do palco tem que dar o tamanho da janela.
    // Se sobrar, aparecem faixas pretas; se passar, corta o titulo ou o rodape.
    assert.ok(
      Math.abs(escala * palco[1] - alturaJanela) < 1e-9,
      `janela ${larguraJanela}x${alturaJanela}: a altura deu ${escala * palco[1]}, ` +
        `nao ${alturaJanela}`
    );
    assert.ok(
      Math.abs(escala * larguraProjeto - larguraJanela) < 1e-9,
      `janela ${larguraJanela}x${alturaJanela}: a largura deu ` +
        `${escala * larguraProjeto}, nao ${larguraJanela}`
    );
  }
});

test("no formato do design nada muda: 1080x1920 continua 1:1", () => {
  const { escala, larguraProjeto } = escalaParaCaber(1080, 1920, 1080, 1920);

  assert.equal(escala, 1, "a escala do OBS tem que continuar 1");
  assert.equal(larguraProjeto, 1080, "e a largura de projeto, 1080");
});

test("janela sem layout nao vira NaN", () => {
  // Antes de o navegador ter layout — 0x0, ou no instante em que o OBS troca
  // de cena — a resposta certa e "nao mexe", e nao NaN: com NaN no `scale`,
  // o palco inteiro desaparece.
  for (const [l, a] of [[0, 0], [0, 1920], [1080, 0], [NaN, NaN], [undefined, undefined], [-5, -5]]) {
    const { escala, larguraProjeto } = escalaParaCaber(l, a, 1080, 1920);

    assert.equal(escala, 1, `janela ${l}x${a} deu escala invalida`);
    assert.equal(larguraProjeto, 1080, `janela ${l}x${a} deu largura invalida`);
  }
});
