/**
 * A matematica da grade.
 *
 * Tudo aqui e puro: entra numero, sai numero. Nada de DOM, nada de canvas,
 * nada de estado. E o que permite rodar `node --test` neste arquivo sem
 * navegador — e o que garante que o desenho na tela e a coordenada que o
 * backend entende sao a MESMA conta.
 *
 * O tamanho da celula e CALCULADO, nunca fixo. Trocar 26x51 por 50x100 no
 * config encolhe as celulas e o desenho continua cabendo. Um `CELL = 26`
 * espalhado pelo codigo quebraria essa promessa na primeira expansao.
 */

/** A=0 … Z=25, AA=26. Mesma indexacao de planilha que o backend usa. */
export function rotuloDaColuna(x) {
  let n = Math.floor(x);
  if (!Number.isFinite(n) || n < 0) return "?";
  let saida = "";
  do {
    saida = String.fromCharCode(65 + (n % 26)) + saida;
    n = Math.floor(n / 26) - 1;
  } while (n >= 0);
  return saida;
}

export function rotuloDe(x, y) {
  return `${rotuloDaColuna(x)}${y}`;
}

const FORMATO = /^([a-z]+)(\d+)$/;
const PREFIXOS = new Set(["p", "pixel", "pintar"]);

/**
 * Tira os separadores que a audiencia escreve sem pensar: espaco e UM traco.
 *
 * "H 5", "H\t5" e "H-5" sao a mesma coordenada. Dois tracos nao sao
 * separador — "H-5-6" e outra coisa e vira `null`.
 */
function semSeparadores(texto) {
  const limpo = texto.replace(/\s+/g, "");
  if (!limpo.includes("-")) return limpo;
  if (limpo.split("-").length !== 2) return null;
  return limpo.replace(/-/g, "");
}

function parsePuro(texto, cols, rows) {
  const limpo = semSeparadores(texto);
  if (!limpo) return null;

  const achado = FORMATO.exec(limpo);
  if (!achado) return null;

  const [, letras, digitos] = achado;

  // Base 26 com A=1, nao A=0: e o que faz "AA" ser 27 e cair em x=26.
  let n = 0;
  for (const letra of letras) n = n * 26 + (letra.charCodeAt(0) - 96);

  const x = n - 1;
  const y = Number(digitos);

  // Sem o tamanho do canvas nao ha o que comparar — quem responde entao e o
  // servidor, com 404. Com o tamanho em maos, o painel responde IGUAL ao
  // backend, inclusive nos casos em que so o limite separa uma coordenada de
  // um comando mal escrito: "/pintar 5 5" vira "PINTAR55", que sem o limite
  // passaria por uma coluna enorme.
  if (cols !== null && (x < 0 || x >= cols)) return null;
  if (rows !== null && (y < 0 || y >= rows)) return null;

  return { x, y };
}

/**
 * O inverso de `rotuloDe`: "H5" vira `{x: 7, y: 5}`.
 *
 * Aceita:  H5  h5  H 5  h 5  H-5  /H5  /pixel H5  /pintar H5  /p H5
 * Recusa:  A51  AA5 (em canvas de 26)  1H  ABC  H  ""  H5extra
 *
 * Sem limites de canvas de proposito. Quem sabe o tamanho do mapa e o
 * servidor, e ele ja responde 404 nomeando o tamanho quando a coordenada
 * nao existe — repetir a conta aqui so criaria uma segunda fonte de verdade
 * para divergir da primeira.
 *
 * Devolve `null` para tudo que nao for coordenada. Nao existe "chute
 * razoavel": pintar o pixel errado e pior que mostrar um erro, e quem digita
 * no painel esta olhando para a tela quando erra.
 *
 * Esta funcao e um ESPELHO de `game/coordinates.py:parse_coordenada`, e o
 * painel do operador a usa justamente para ler igual ao backend. Quando as
 * duas divergiram — o backend aceitava "H-5" e "/p H5" e o painel nao — o
 * streamer nao conseguia inspecionar uma coordenada que a audiencia tinha
 * pintado de verdade. As listas de formas aceitas nos dois arquivos de teste
 * sao a mesma lista, de proposito.
 */
export function analisarRotulo(texto, cols = null, rows = null) {
  if (typeof texto !== "string") return null;

  const cru = texto.trim();
  if (!cru) return null;

  if (!cru.startsWith("/")) return parsePuro(cru.toLowerCase(), cols, rows);

  // Comando: "/pintar H5". O prefixo autoriza; o argumento e que e a pintura.
  const corpo = cru.slice(1).trim();
  const partes = corpo.split(/\s+/);

  // O comando vem PRIMEIRO. O backend tenta o corpo inteiro antes disso, mas
  // so precisa dessa ordem para "/H5" — e em "/pintar 5 5" ele escapa do
  // chute apenas porque compara com o tamanho do canvas.
  if (partes.length === 2 && PREFIXOS.has(partes[0].toLowerCase())) {
    return parsePuro(partes[1].toLowerCase(), cols, rows);
  }

  return parsePuro(corpo.toLowerCase(), cols, rows);
}

/**
 * O tamanho da fonte dos rotulos de coluna.
 *
 * Com 26 colunas o rotulo e uma letra so e cabe folgado. Com 50 ele passa a
 * ter duas ("AA"), e a mesma fonte que servia para "H" faz "AA" encostar na
 * celula vizinha — justo na tela em que a audiencia precisa LER a coluna
 * para saber o que comentar. Quanto mais letras o rotulo tiver, menor ele
 * fica; `min` e `max` existem para a letra nao virar um letreiro numa grade
 * pequena nem um borrao ilegivel numa grade gigante.
 *
 * Os dois limites vem da config (`tela.fonte_regua_min/max`), e nao de
 * constantes: o teto de 15 era do tempo da grade de 50 colunas, e ele continuava
 * cortando a letra numa grade de 25, onde a celula tem 40px e a conta sozinha
 * pediria 34. A tela passa por um encode de video antes de chegar ao publico, e
 * traco fino nao sobrevive a ele — quem transmite e quem sabe o tamanho que le.
 *
 * A largura de um caractere monoespacado e ~0,62 da fonte.
 */
export function fonteDoRotulo(celula, letras = 1, { min = 9, max = 15 } = {}) {
  const porAltura = celula - 6;
  const porLargura = (celula - 4) / (0.62 * Math.max(1, letras));
  return Math.max(min, Math.min(max, Math.floor(Math.min(porAltura, porLargura))));
}

/**
 * A margem da regua que cabe uma fonte deste tamanho.
 *
 * A faixa precisa segurar DUAS coisas: o tracinho, que se estica junto com a
 * celula (`comprido` no `renderer`), e o rotulo inteiro, com dois digitos na
 * coluna da esquerda. Uma fonte maior sem margem maior desenha o rotulo por
 * cima do quadro — a coordenada sairia justamente de onde ela precisa estar:
 * fora do desenho.
 *
 * As faixas de hoje (34 e 42) continuam sendo o MINIMO: uma fonte pequena nao
 * encolhe a margem que ja existia.
 */
export function faixasParaFonte(fonte, celula, { minimoLetras = 34, minimoNumeros = 42 } = {}) {
  const recuo = Math.max(9, celula * 0.5) + 6;
  // O rotulo e centrado no recuo (`textBaseline: middle`), e o que sobe a
  // partir dele e meia altura de MAIUSCULA — 0,72 da fonte, e sem descida,
  // porque rotulo so tem letra maiuscula e algarismo.
  const altura = Math.ceil(recuo + fonte * 0.36 + 3);
  // Dois digitos: "0" a "99". E o que a grade usa hoje, e um rotulo de tres
  // digitos so aparece numa grade de 100 linhas, que nao cabe na tela.
  const largura = Math.ceil(recuo + fonte * 0.62 * 2 + 3);
  return {
    faixaLetras: Math.max(minimoLetras, altura),
    faixaNumeros: Math.max(minimoNumeros, largura),
  };
}

/**
 * Este indice cai num marco da regua?
 *
 * A regua tem duas testas para cada marco: o tracinho mais comprido na margem
 * e o rotulo mais aceso. As duas perguntam AQUI, de proposito — se cada uma
 * fizesse a propria conta, um dia elas divergiriam e a regua passaria a mentir
 * sobre onde estao os marcos. Quem conta de cinco em cinco pelas marcas para
 * achar a coluna H contaria errado.
 *
 * O `i >= 0` nao e teoria: `-5 % 5` e `-0`, e `-0 === 0` e verdadeiro, entao
 * sem a guarda um indice negativo — que nao existe na grade — seria "marco".
 */
export function ehMarco(i, passo = 5) {
  return i >= 0 && i % passo === 0;
}

/**
 * Onde a grade fica dentro da area disponivel.
 *
 * Devolve o tamanho da celula e o deslocamento da grade inteira — os
 * rotulos (letras em cima, numeros a esquerda) vivem nesse deslocamento.
 */
export function calcularGrade({
  cols,
  rows,
  largura,
  altura,
  dpr = 1,
  folga = 10,
  // As faixas sao a MARGEM da regua, e por isso sao mais largas do que o
  // rotulo precisa: dentro delas cabem o rotulo E a fileira de tracinhos que
  // liga o rotulo a celula. Sem esse espaco o tracinho encostaria na letra e
  // as duas coisas virariam um borrao.
  //
  // Alargar as faixas custa largura da grade, entao vale a conta: com 1080 de
  // largura sobram 1018 para 50 colunas = 20,36 — a celula continua 20, que e
  // o tamanho aprovado. Na altura sobra muito mais (1166 para 51 linhas), e
  // por isso a largura manda. Mais um pixel de faixa e a celula cairia para
  // 19, e a grade inteira encolheria por causa de enfeite.
  faixaLetras = 34,
  faixaNumeros = 42,
  maximo = 64,
}) {
  if (cols < 1 || rows < 1) throw new Error("grade sem celulas");

  const disponivelX = largura - folga * 2 - faixaNumeros;
  const disponivelY = altura - folga * 2 - faixaLetras;

  // A celula e escolhida em PIXELS DO APARELHO, e nao em pixels de CSS.
  //
  // A conta obvia — `floor(disponivel / cols)`, que da um numero redondo de
  // CSS — tem uma falha que so aparece quando alguem da zoom: com
  // `devicePixelRatio = 0.625`, uma celula de 20 de CSS vale 12,5 pixels do
  // aparelho. Nao existe meio pixel, entao as fronteiras arredondadas caem
  // ora em 12 ora em 13 — e as colunas ficam ALTERNADAMENTE mais largas e
  // mais estreitas. Numa grade de 50x51 isso nao e um detalhe de meio pixel:
  // e a grade inteira parecendo torta, com uns quadrados de borda e outros
  // sem. Era o defeito que aparecia ao dar zoom out para a pagina caber.
  //
  // Escolhendo o tamanho em pixels do aparelho e dividindo pelo dpr depois,
  // a celula vale um numero INTEIRO de pixels do aparelho por construcao, em
  // qualquer zoom. Com dpr 1 a conta e identica a de antes, entao no OBS
  // (que roda a 1) nada muda.
  const celulaAparelho = Math.max(
    1,
    Math.min(
      Math.floor((disponivelX * dpr) / cols),
      Math.floor((disponivelY * dpr) / rows),
      Math.floor(maximo * dpr)
    )
  );

  const celula = celulaAparelho / dpr;
  const larguraGrade = celula * cols;
  const alturaGrade = celula * rows;

  return {
    cols,
    rows,
    celula,
    faixaLetras,
    faixaNumeros,
    larguraGrade,
    alturaGrade,
    // Centraliza a grade INTEIRA (com as faixas de rotulo) na area. A origem
    // tambem e encaixada no pixel do aparelho: alinhar as CELULAS sem alinhar
    // o ponto de partida deixaria a grade inteira meio pixel fora — que e o
    // mesmo defeito, so que uniforme.
    origemX: encaixar(
      (largura - larguraGrade - faixaNumeros) / 2 + faixaNumeros,
      dpr
    ),
    origemY: encaixar(
      (altura - alturaGrade - faixaLetras) / 2 + faixaLetras,
      dpr
    ),
  };
}

/**
 * O tamanho do palco para ele preencher a janela INTEIRA.
 *
 * O palco tem uma ALTURA de projeto fixa (1920) e uma largura que se ajusta.
 * A altura manda porque e ela que decide o tamanho de tudo que e desenhado: o
 * cabecalho, o rodape e a arena sao medidas dela, entao a composicao vertical
 * sai identica em qualquer janela — o rodape sempre ocupa os mesmos 560px, e
 * a arena todo o resto. O que sobra de largura vira ARENA, e a grade se centra
 * nela.
 *
 * A alternativa — encaixar o palco inteiro, mantendo 1080x1920 — deixava
 * faixas pretas nas laterais de qualquer janela que nao fosse exatamente 9:16,
 * e quem assiste pelo navegador ve a faixa. Aqui nao sobra nada:
 *
 *   escala * alturaPalco    = altura da janela
 *   escala * larguraProjeto = largura da janela
 *
 * As duas contas juntas sao "100% no navegador", e sao o que o
 * `geometry.test.mjs` cobra em oito formatos de janela diferentes.
 *
 * Escala maior que 1 e esperada: numa janela maior que o palco nominal a tela
 * CRESCE. Nao borra — o canvas e redesenhado no tamanho novo, e o `--escala` e
 * um `transform`, que o navegador rasteriza de novo na resolucao final.
 *
 * Sem layout ainda (0x0, ou no instante da troca de cena) a resposta e o palco
 * nominal, e nao `NaN` — com `NaN` num `scale`, o palco inteiro desaparece da
 * tela.
 */
export function escalaParaCaber(
  larguraJanela,
  alturaJanela,
  larguraPalco = 1080,
  alturaPalco = 1920
) {
  if (!(larguraJanela > 0) || !(alturaJanela > 0)) {
    return { escala: 1, larguraProjeto: larguraPalco };
  }

  const escala = alturaJanela / alturaPalco;
  return { escala, larguraProjeto: larguraJanela / escala };
}

/** Encaixa um valor no pixel mais proximo do aparelho. */
function encaixar(valor, dpr = 1) {
  return Math.round(valor * dpr) / dpr;
}

/**
 * As fronteiras de todas as celulas, encaixadas no pixel do APARELHO.
 *
 * Um monitor de Windows a 125% tem `devicePixelRatio = 1.25`, e o canvas roda
 * com `ctx.scale(dpr, dpr)`. Nesse mundo um traco de 1px numa coordenada
 * inteira de CSS cai no MEIO de um pixel do aparelho: metade da tinta num
 * pixel, metade no vizinho. Como a cor da grade e quase transparente, os
 * tracos que se dissolvem em dois simplesmente somem — e a grade fica com uns
 * quadrados de borda visivel e outros sem, que foi o defeito relatado.
 *
 * O passo e UNICO, e nao arredondado fronteira a fronteira. Arredondar cada
 * uma por si deixava o erro ir para lados diferentes e as celulas sairem
 * desiguais: com dpr 0.625 a celula de 20 de CSS vale 12,5 pixels do aparelho,
 * e o arredondamento alternava 12, 13, 12, 13 pela grade inteira. Um passo so
 * — o mesmo para todas — e o que garante que toda celula seja do mesmo
 * tamanho. Quem escolhe esse passo e `calcularGrade`, que ja o entrega em
 * pixels do aparelho.
 *
 * Devolve `cols + 1` posicoes em X e `rows + 1` em Y — as BORDAS, nao as
 * celulas: uma celula e o espaco entre duas bordas vizinhas. Usar as mesmas
 * bordas para a linha e para o preenchimento e o que impede um fio de fundo
 * de aparecer entre dois pixels pintados lado a lado.
 */
export function bordasDaGrade(grade, dpr = 1) {
  const passo = encaixar(grade.celula, dpr);
  const x0 = encaixar(grade.origemX, dpr);
  const y0 = encaixar(grade.origemY, dpr);

  const xs = [];
  for (let x = 0; x <= grade.cols; x += 1) {
    xs.push(encaixar(x0 + x * passo, dpr));
  }

  const ys = [];
  for (let y = 0; y <= grade.rows; y += 1) {
    ys.push(encaixar(y0 + y * passo, dpr));
  }

  return { xs, ys };
}

/** Canto superior esquerdo da celula, em pixels do canvas. */
export function celulaParaPixel(grade, x, y) {
  return {
    px: grade.origemX + x * grade.celula,
    py: grade.origemY + y * grade.celula,
  };
}

/** O inverso. Devolve `null` fora da grade. */
export function pixelParaCelula(grade, px, py) {
  const x = Math.floor((px - grade.origemX) / grade.celula);
  const y = Math.floor((py - grade.origemY) / grade.celula);
  if (x < 0 || y < 0 || x >= grade.cols || y >= grade.rows) return null;
  return { x, y };
}

/** A regiao da grade inteira, para o brilho de fundo. */
export function retanguloDaGrade(grade) {
  return {
    x: grade.origemX,
    y: grade.origemY,
    w: grade.larguraGrade,
    h: grade.alturaGrade,
  };
}
