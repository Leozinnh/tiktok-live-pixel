/**
 * O desenho da grade.
 *
 * Duas camadas de canvas, separadas de proposito: a GRADE aqui e a de
 * PARTICULAS em `effects.js`. Um canvas so obrigaria a repintar o quadro
 * inteiro 60 vezes por segundo para animar tres faiscas — e o OBS ainda esta
 * encodando a LIVE.
 *
 * Toda coordenada que este arquivo desenha passa por `bordasDaGrade`. Nao e
 * cerimonia: um monitor de Windows a 125% tem `devicePixelRatio = 1.25`, e um
 * traco de 1px numa coordenada inteira de CSS cai no meio de um pixel do
 * aparelho e se dissolve em dois. Como a cor da grade e quase transparente,
 * os tracos que se dissolvem somem — e a grade fica com uns quadrados de
 * borda visivel e outros sem. Era esse o defeito.
 */

import {
  bordasDaGrade,
  calcularGrade,
  ehMarco,
  faixasParaFonte,
  fonteDoRotulo,
  rotuloDaColuna,
} from "./geometry.js";
import { clarear, rgba } from "./effects.js";
import { corDaCelula, desenharEvento, deslocamentoDoEvento } from "./eventos.js";

const FUNDO = "#05060a";
const GRADE_VAZIA = "rgba(255, 255, 255, 0.045)";
const BORDA = "rgba(120, 220, 255, 0.10)";

// A regua e impressa em AMBAR, uma tinta so dela.
//
// A coordenada e a unica coisa que a audiencia precisa LER na tela: a pessoa
// olha o quadro, acha a coluna, e escreve "H5" no chat. Antes ela era azul
// acinzentado a 55% — a mesma familia de cor da grade e do fundo, no meio de
// um quadro que ja e azul. Com 50 rotulos apertados de 20 em 20 pixels, o que
// separa uma letra da vizinha nao e o espaco, e a tinta.
//
// O ambar resolve isso do jeito que um mapa resolve: em carta impressa, o
// quadro e uma tinta e a grade de referencia e outra. Ninguem confunde a
// margem com o terreno. O que e quente aqui so pode ser leitura; o que e
// frio e o desenho da comunidade.
const REGUA_CAMPO = "rgba(255, 193, 77, 0.055)"; // o papel da margem
const REGUA_FIO = "rgba(255, 193, 77, 0.34)"; // tracinho de marco
const REGUA_FIO_FRACO = "rgba(255, 193, 77, 0.16)"; // tracinho comum
// O rotulo e a INFORMACAO; o tracinho e so o grao da regua. Na primeira
// versao estava invertido — tracinhos a 45% e letras a 66% faziam uma fileira
// de riscos de 2px pesar mais que as letras de 12px ao lado, e o olho pousava
// no risco em vez de pousar na letra. Quem manda no contraste e quem carrega
// o recado.
const REGUA_TEXTO = "rgba(255, 200, 105, 0.88)";
const REGUA_TEXTO_MARCO = "rgba(255, 222, 165, 1)";
const REGUA_ACESO = "#38f5ff"; // o endereco que acabou de ser pintado

export class Renderer {
  constructor(canvas, { cols = 26, rows = 51 } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.cols = cols;
    this.rows = rows;
    this.cells = new Map(); // "x,y" -> {color, effect}
    this.cursor = null; // {x, y}
    this.grade = null;
    this.dpr = 1;
    // O efeito do evento em curso (`arco_iris`, `caos`, `desafio`), ou null.
    // Quem escreve aqui e o `app.js`, a partir do `event_start`.
    this.efeito = null;

    // Os limites da fonte da regua, do `config.json` (`tela.*`). Chegam pelo
    // `hello`; antes disso valem os padroes historicos.
    this.tela = { min: 9, max: 15 };
    this.fonteRegua = 15;
  }

  /**
   * Os tamanhos que vem do `config.json`, no `hello`.
   *
   * As chaves chegam com o nome do ARQUIVO (`fonte_regua_min`), de proposito:
   * e o formato que o servidor manda, e traduzir aqui so criaria um segundo
   * nome para a mesma coisa. Quem chama isto precisa reajustar o palco depois
   * (`ajustar()` no `app.js`): a fonte decide a margem da regua, e a margem
   * decide o tamanho da grade.
   */
  definirTela({ fonte_regua_min: min = 9, fonte_regua_max: max = 15 } = {}) {
    this.tela = { min: Number(min) || 9, max: Number(max) || 15 };
  }

  /**
   * Da ao canvas o tamanho da area que ele desenha.
   *
   * `largura` e `altura` sao medidas no espaco do PALCO — o mesmo em que este
   * canvas e posicionado, e o mesmo em que tudo aqui e desenhado. `escala` e o
   * `transform: scale()` que o palco leva por cima (o `--escala` da pagina).
   *
   * Os dois numeros que saem daqui vivem em espacos diferentes, e trocar um
   * pelo outro encolhe o canvas duas vezes:
   *
   *   `style.width`  -> comprimento de LAYOUT, lido dentro do palco;
   *   `canvas.width` -> o BUFFER, em pixels do aparelho ja na tela.
   *
   * Por isso a medida de fora (`getBoundingClientRect`, que devolve o tamanho
   * DEPOIS da escala) nao serve para o `style.width`: ela descreve a tela, e o
   * estilo descreve o palco. Quem responde pelo layout e o `offsetWidth` da
   * arena, que a escala nao toca.
   */
  redimensionar(largura, altura, escala = 1) {
    // `devicePixelRatio`: no OBS a pagina roda a 1, mas num navegador de
    // verdade o canvas borraria sem isto. O limite de 2 e de MEMORIA: o buffer
    // e `largura * dpr` de lado, e num monitor 4K isso e dezenas de megabytes.
    //
    // A escala do palco multiplica o `devicePixelRatio` em vez de substitui-lo,
    // porque as duas encolhem pelo mesmo caminho: um pixel de projeto vira
    // `escala` pixels de CSS na tela, e cada um deles vira `devicePixelRatio`
    // pixels do aparelho.
    this.dpr = Math.min(2, window.devicePixelRatio || 1) * escala;
    this.canvas.width = Math.round(largura * this.dpr);
    this.canvas.height = Math.round(altura * this.dpr);
    this.canvas.style.width = `${largura}px`;
    this.canvas.style.height = `${altura}px`;

    // O `dpr` entra na conta da grade, e nao so no tamanho do canvas: e o que
    // faz a celula valer um numero INTEIRO de pixels do aparelho. Sem ele a
    // celula de 20 de CSS vale 12,5 pixels num zoom de 50% com a tela a 125%,
    // e as colunas ficam alternadamente largas e estreitas. Com o palco
    // encolhido o mesmo vale para a escala: a celula de 67 no espaco do palco
    // vale 26,8 na tela com escala 0,4, e a fronteira que nao cai em pixel
    // inteiro some quando a cor da grade ja e quase transparente.
    // A fonte depende da celula, e a MARGEM da regua depende da fonte: um
    // rotulo maior precisa de mais margem, e mais margem encolhe a celula. As
    // duas contas se olham, entao sao duas passadas. A segunda so roda quando
    // a fonte pediu mais margem do que o padrao — com os limites de sempre ela
    // nunca pede, e a grade sai exatamente como saia antes. Uma passada extra
    // basta: a margem so cresce na segunda, entao a celula so encolhe, e o
    // pedido seguinte seria menor — nunca maior.
    const letras = rotuloDaColuna(this.cols - 1).length;
    const medidas = {
      cols: this.cols,
      rows: this.rows,
      largura,
      altura,
      dpr: this.dpr,
    };

    let grade = calcularGrade(medidas);
    let fonte = fonteDoRotulo(grade.celula, letras, this.tela);
    const faixas = faixasParaFonte(fonte, grade.celula);

    if (faixas.faixaLetras > grade.faixaLetras || faixas.faixaNumeros > grade.faixaNumeros) {
      grade = calcularGrade({ ...medidas, ...faixas });
      fonte = fonteDoRotulo(grade.celula, letras, this.tela);
    }

    this.grade = grade;
    // Guardado, e nao recalculado na hora de desenhar: foi ESTE numero que
    // dimensionou a margem logo acima. Recalcular la poderia divergir da
    // margem que ja foi reservada no layout.
    this.fonteRegua = fonte;
  }

  definirCanvas(cols, rows, cells = []) {
    this.cols = cols;
    this.rows = rows;
    this.cells = new Map();
    for (const c of cells) {
      this.cells.set(`${c.x},${c.y}`, { color: c.color, effect: c.effect });
    }
  }

  pintar({ x, y, color, effect }) {
    this.cells.set(`${x},${y}`, { color, effect });
  }

  apagar({ x, y }) {
    this.cells.delete(`${x},${y}`);
  }

  moverCursor(x, y) {
    this.cursor = x === null || y === null ? null : { x, y };
  }

  /**
   * As fronteiras das celulas, ja encaixadas no pixel do aparelho.
   *
   * Recalculado a cada quadro de proposito: sao 102 arredondamentos contra
   * 1326 preenchimentos, e guardar em cache abriria a porta para um quadro
   * desenhado com a grade de antes depois de um redimensionamento.
   */
  bordas() {
    return bordasDaGrade(this.grade, this.dpr);
  }

  /** O centro da celula em pixels — onde as particulas nascem. */
  centro(x, y) {
    const { xs, ys } = this.bordas();
    return { x: (xs[x] + xs[x + 1]) / 2, y: (ys[y] + ys[y + 1]) / 2 };
  }

  desenhar(t = 0) {
    const ctx = this.ctx;
    const { celula, larguraGrade, alturaGrade } = this.grade;
    const { xs, ys } = this.bordas();

    // O fio de cabelo que separa duas celulas: UM pixel do aparelho, na
    // fronteira encaixada. `+ 0.5 / dpr` empurra o traco para o centro do
    // pixel do aparelho — sem isso o proprio fio cai na fronteira e volta a
    // se dissolver em dois, que e o defeito que estas contas existem para
    // matar.
    const fino = 1 / this.dpr;
    const meio = 0.5 / this.dpr;

    ctx.save();
    ctx.scale(this.dpr, this.dpr);

    // O apagador trabalha em PIXELS DO APARELHO, e por isso vem antes da
    // escala: `canvas.width` e o tamanho do canvas no aparelho, e daqui para
    // baixo tudo ja esta no espaco de CSS. Misturar os dois multiplicava o
    // tamanho por `dpr` uma segunda vez — com dpr 0,625 so os primeiros 62% do
    // quadro eram apagados, e o resto ia acumulando quadro a quadro.
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    ctx.restore();

    // O fundo cobre o quadro inteiro em pixels de CSS. O `Math.ceil` nao e
    // enfeite: `canvas.width` foi arredondado na criacao e num dpr fracionario
    // pode ficar meio pixel maior que `largura * dpr` — e essa metade de pixel
    // ficaria de fora do fundo para sempre, mostrando o que havia antes.
    const larguraCss = Math.ceil(this.canvas.width / this.dpr);
    const alturaCss = Math.ceil(this.canvas.height / this.dpr);

    // O CAOS sacode a GRADE — nao o enfeite. Por isso o deslocamento fica
    // neste `save` interno, que fecha antes do desenho do evento: uma faixa
    // de arco-iris tremendo junto seria o CAOS sacudindo o proprio efeito.
    ctx.save();
    const { dx, dy } = deslocamentoDoEvento(this.efeito, t);
    if (dx || dy) ctx.translate(dx, dy);

    // A folga existe pelo mesmo tremor: com a grade deslocada, um fundo
    // pintado a partir de (0,0) deixaria uma faixa transparente na borda de
    // onde ele saiu.
    const folga = 4;

    // Fundo do campo, com um brilho frio no centro.
    const meioX = xs[0] + larguraGrade / 2;
    const meioY = ys[0] + alturaGrade / 2;
    const brilho = ctx.createRadialGradient(
      meioX,
      meioY,
      celula,
      meioX,
      meioY,
      Math.max(larguraGrade, alturaGrade) * 0.75
    );
    brilho.addColorStop(0, "rgba(30, 70, 120, 0.22)");
    brilho.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = FUNDO;
    ctx.fillRect(-folga, -folga, larguraCss + folga * 2, alturaCss + folga * 2);
    ctx.fillStyle = brilho;
    ctx.fillRect(-folga, -folga, larguraCss + folga * 2, alturaCss + folga * 2);

    this._desenharRegua(xs, ys);

    // A grade: uma linha por fronteira, num caminho so. Antes eram 1326
    // retangulos — metade dos tracos, o mesmo desenho, e cada linha cai
    // agora exatamente em cima de um pixel do aparelho.
    ctx.beginPath();
    for (let x = 0; x <= this.cols; x += 1) {
      const px = xs[x] + meio;
      ctx.moveTo(px, ys[0]);
      ctx.lineTo(px, ys[this.rows]);
    }
    for (let y = 0; y <= this.rows; y += 1) {
      const py = ys[y] + meio;
      ctx.moveTo(xs[0], py);
      ctx.lineTo(xs[this.cols], py);
    }
    ctx.strokeStyle = GRADE_VAZIA;
    ctx.lineWidth = fino;
    ctx.stroke();

    // Quem decide a cor de cada celula e `corDaCelula`: o ARCO-IRIS gira a cor
    // das celulas JA pintadas, e o feixe do BRILHO as acende. Nenhum dos dois
    // passa uma faixa POR CIMA do quadro — a faixa antiga do arco-iris tapava
    // o desenho, e a audiencia via um retangulo colorido de passagem em vez do
    // pixel que tinha acabado de pagar. Sem efeito de celula (com um enfeite
    // no ar, ou sem evento nenhum) a cor da pessoa volta intacta.
    //
    // As celulas pintadas usam as MESMAS fronteiras da linha. Se cada uma
    // calculasse o proprio tamanho a partir de `celula`, as duas contas
    // divergiriam por um pixel e apareceria um fio de fundo entre dois pixels
    // vizinhos — o desenho da comunidade rachado em quadradinhos soltos.
    for (const [chave, dados] of this.cells) {
      if (!dados.color) continue;
      const [x, y] = chave.split(",").map(Number);
      const px = xs[x];
      const py = ys[y];
      const largura = xs[x + 1] - xs[x];
      const altura = ys[y + 1] - ys[y];

      // Tudo o que a celula desenha (o brilho do efeito e o fio de cima) sai
      // da MESMA variavel, para a celula nao sair com duas cores diferentes
      // no meio de uma troca.
      const cor = corDaCelula(this.efeito, x, y, t, dados.color);

      ctx.fillStyle = cor;
      ctx.fillRect(px, py, largura, altura);

      if (dados.effect) {
        ctx.save();
        ctx.globalAlpha = 0.5;
        ctx.fillStyle = clarear(cor, 0.6);
        ctx.fillRect(px, py, largura, altura * 0.28);
        ctx.restore();
      }

      // Um fio claro no topo da celula: da volume sem custo nenhum.
      ctx.fillStyle = rgba(cor, 0.35);
      ctx.fillRect(px, py, largura, fino);
    }

    // A moldura do quadro, encaixada como todas as outras bordas.
    ctx.strokeStyle = BORDA;
    ctx.lineWidth = 2 * fino;
    ctx.strokeRect(
      xs[0] - fino,
      ys[0] - fino,
      xs[this.cols] - xs[0] + 2 * fino,
      ys[this.rows] - ys[0] + 2 * fino
    );

    this._desenharCursor(xs, ys);
    ctx.restore(); // fecha o tremor

    // O enfeite do evento, por ultimo e por cima de tudo. Ele e desenhado no
    // espaco de CSS — o mesmo da grade — e nao no do aparelho: quem cuida do
    // encaixe nas bordas e o `bordasDaGrade`, e o enfeite nao tem borda. O
    // `cols`/`rows` vao junto porque a chuva da HORA DO PIXEL cai em pixels
    // do tamanho de uma celula.
    desenharEvento(
      ctx,
      this.efeito,
      {
        x: xs[0],
        y: ys[0],
        w: xs[this.cols] - xs[0],
        h: ys[this.rows] - ys[0],
        cols: this.cols,
        rows: this.rows,
      },
      t
    );

    ctx.restore();
  }

  /**
   * A regua: a margem impressa em volta do quadro.
   *
   * Sao tres coisas, e cada uma responde por uma pergunta diferente de quem
   * esta contando:
   *
   *   o CAMPO    — cinza-quente por fora da moldura: "isto aqui nao e o
   *                desenho, e a margem";
   *   o TRACINHO — liga cada rotulo a celula exata a que ele se refere, e o
   *                comprido marca de cinco em cinco: "voce esta na K, faltam
   *                duas para a M", que e como alguem conta de cabeca;
   *   o ROTULO   — a letra, em ambar.
   *
   * Os tres saem da MESMA posicao (`xs[x]` e `xs[x+1]`), e o marco sai da
   * mesma funcao para o tracinho e para a tinta do rotulo. Se um dia
   * divergirem, a regua passa a apontar para a celula errada e a pessoa
   * escreve um H5 que o servidor pinta em outro lugar.
   */
  _desenharRegua(xs, ys) {
    const ctx = this.ctx;
    const { celula, cols, rows, faixaLetras, faixaNumeros } = this.grade;
    const cursor = this.cursor;
    const fino = 1 / this.dpr;

    // O tamanho saiu do `redimensionar`: foi ele que dimensionou a margem da
    // regua para esta fonte caber. A conta passa pelas letras MAIS LARGAS da
    // grade, entao a regua inteira sai do mesmo tamanho — uma letra de 14 e
    // outra de 12 na mesma fileira parece defeito.
    //
    // Em NEGRITO de proposito: a tela passa por um encode de video antes de
    // chegar ao publico, e um traco fino a 88% de opacidade nao sobrevive a
    // ele. O peso e o que segura a letra depois da compressao.
    //
    // A MESMA monoespacada do feed, e nao a `ui-monospace` generica: os dois
    // lugares imprimem a mesma coordenada, e o mesmo "H5" desenhado em duas
    // fontes diferentes parece dois enderecos diferentes.
    ctx.font = `bold ${this.fonteRegua}px "Cascadia Mono", Consolas, ui-monospace, monospace`;
    ctx.textBaseline = "middle";

    // Quanto o rotulo se afasta da moldura. Preso ao comprimento do tracinho
    // para o rotulo nunca encostar nele, e preso a faixa para nao transbordar
    // para fora do campo da margem. Os dois eixos usam o MESMO recuo: e o que
    // deixa o canto da regua quadrado.
    const comprido = Math.max(9, celula * 0.5);
    const curto = Math.max(4, celula * 0.22);
    const recuo = Math.max(comprido + 6, faixaLetras * 0.62);

    const x0 = xs[0];
    const y0 = ys[0];
    const x1 = xs[this.cols];
    const y1 = ys[this.rows];

    // ------------------------------------------------------------------
    // 1. O campo da margem
    // ------------------------------------------------------------------
    // Onde o campo encosta na moldura a moldura ja esta desenhada, entao nao
    // ha fio nenhum a acrescentar: a propria borda da grade e a aresta de
    // dentro da regua.
    ctx.fillStyle = REGUA_CAMPO;
    ctx.fillRect(x0 - faixaNumeros, y0 - faixaLetras, x1 - x0 + faixaNumeros, faixaLetras);
    ctx.fillRect(x0 - faixaNumeros, y0, faixaNumeros, y1 - y0);

    // ------------------------------------------------------------------
    // 2. Os tracinhos
    // ------------------------------------------------------------------
    // Meio da celula, e nao a fronteira: e onde o rotulo esta e onde o pixel
    // vai nascer. Um tracinho na fronteira apontaria para o meio de duas
    // celulas, que e exatamente a duvida que a regua existe para tirar.
    const passo = celula < 14 ? 2 : 1;
    const menor = [];
    const maior = [];
    const acesos = [];

    for (let x = 0; x < cols; x += passo) {
      const cx = (xs[x] + xs[x + 1]) / 2;
      const marco = ehMarco(x);
      (marco ? maior : menor).push([cx, y0 - 1, cx, y0 - (marco ? comprido : curto)]);
    }
    for (let y = 0; y < rows; y += passo) {
      const cy = (ys[y] + ys[y + 1]) / 2;
      const marco = ehMarco(y);
      (marco ? maior : menor).push([x0 - 1, cy, x0 - (marco ? comprido : curto), cy]);
    }

    const tracar = (lista, cor, largura) => {
      if (!lista.length) return;
      ctx.beginPath();
      for (const [ax, ay, bx, by] of lista) {
        ctx.moveTo(ax, ay);
        ctx.lineTo(bx, by);
      }
      ctx.strokeStyle = cor;
      ctx.lineWidth = largura;
      ctx.stroke();
    };

    tracar(menor, REGUA_FIO_FRACO, fino);
    tracar(maior, REGUA_FIO, 2 * fino);

    // O tracinho do endereco aceso e a metade da resposta que o rotulo nao da:
    // o rotulo diz QUAL coluna, o tracinho diz ONDE ela esta. Com 50 colunas
    // de 20 pixels, achar a letra acesa no meio das outras 49 e o trabalho
    // mais chato de acompanhar uma pintura ao vivo.
    if (cursor) {
      if (cursor.x >= 0 && cursor.x < cols) {
        const cx = (xs[cursor.x] + xs[cursor.x + 1]) / 2;
        acesos.push([cx, y0 - 1, cx, y0 - comprido]);
      }
      if (cursor.y >= 0 && cursor.y < rows) {
        const cy = (ys[cursor.y] + ys[cursor.y + 1]) / 2;
        acesos.push([x0 - 1, cy, x0 - comprido, cy]);
      }
    }
    tracar(acesos, REGUA_ACESO, 2 * fino);

    // ------------------------------------------------------------------
    // 3. Os rotulos
    // ------------------------------------------------------------------
    ctx.textAlign = "center";
    for (let x = 0; x < cols; x += passo) {
      const aceso = cursor && cursor.x === x;
      // O endereco aceso escapa do `passo`: numa grade apertada o rotulo que
      // importa e justamente o que o passo ia pular.
      if (!aceso && x % passo !== 0) continue;
      ctx.fillStyle = aceso
        ? REGUA_ACESO
        : ehMarco(x)
          ? REGUA_TEXTO_MARCO
          : REGUA_TEXTO;
      ctx.fillText(rotuloDaColuna(x), (xs[x] + xs[x + 1]) / 2, y0 - recuo);
    }

    // Os numeros vao encostados na DIREITA. Nao e capricho: alinhados pela
    // direita os algarismos das unidades ficam na mesma coluna, e "9" e "50"
    // se leem como uma escala. Centrados, cada numero comeca num lugar e a
    // fileira vira uma escada.
    ctx.textAlign = "right";
    for (let y = 0; y < rows; y += passo) {
      const aceso = cursor && cursor.y === y;
      if (!aceso && y % passo !== 0) continue;
      ctx.fillStyle = aceso
        ? REGUA_ACESO
        : ehMarco(y)
          ? REGUA_TEXTO_MARCO
          : REGUA_TEXTO;
      ctx.fillText(String(y), x0 - recuo, (ys[y] + ys[y + 1]) / 2);
    }
  }

  _desenharCursor(xs, ys) {
    const cursor = this.cursor;
    if (!cursor) return;

    const ctx = this.ctx;
    const x = cursor.x;
    const y = cursor.y;
    const px = xs[x];
    const py = ys[y];
    const largura = xs[x + 1] - xs[x];
    const altura = ys[y + 1] - ys[y];
    const fino = 1 / this.dpr;

    ctx.save();

    // A mira larga e translucida: e um brilho, nao uma linha. Borrar nao
    // incomoda aqui.
    ctx.strokeStyle = "rgba(56, 245, 255, 0.16)";
    ctx.lineWidth = this.grade.celula;
    ctx.beginPath();
    ctx.moveTo(px + largura / 2, ys[0]);
    ctx.lineTo(px + largura / 2, ys[this.rows]);
    ctx.moveTo(xs[0], py + altura / 2);
    ctx.lineTo(xs[this.cols], py + altura / 2);
    ctx.stroke();

    // Ja a caixa que marca O pixel precisa ser nitida: ela fica acesa por
    // segundos, parada, e um retangulo borrado parece defeito.
    ctx.strokeStyle = "#38f5ff";
    ctx.lineWidth = 2 * fino;
    ctx.strokeRect(
      px + fino,
      py + fino,
      largura - 2 * fino,
      altura - 2 * fino
    );

    ctx.restore();
  }
}
