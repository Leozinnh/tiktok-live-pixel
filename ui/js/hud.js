/**
 * O HUD fora do canvas: ranking, feed, estatisticas e o aviso de evento.
 *
 * Tudo aqui e DOM, nao canvas. Texto em HTML sai nitido em qualquer zoom e
 * o OBS escala melhor — e, principalmente, da para o streamer inspecionar
 * com o botao direito quando algo parecer errado.
 *
 * As listas sao reconstruidas so quando o conteudo MUDA (comparacao pela
 * assinatura). Reescrever o `innerHTML` a cada quadro faria o navegador
 * refazer o layout 20 vezes por segundo sem nada ter mudado.
 */

const CORES_DO_NIVEL = [
  "#8ea2c8",
  "#7ee0ff",
  "#7dffb0",
  "#ffd93d",
  "#ff9f45",
  "#ff5fa2",
];

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

export class Hud {
  constructor(doc = document) {
    this.doc = doc;
    this.$ = (id) => doc.getElementById(id);
    this._assinaturas = {};
  }

  _soMudou(nome, valor) {
    const assinatura = JSON.stringify(valor);
    if (this._assinaturas[nome] === assinatura) return false;
    this._assinaturas[nome] = assinatura;
    return true;
  }

  // ------------------------------------------------------------------
  // Estatisticas
  // ------------------------------------------------------------------

  /**
   * A escala do quadro, no cabecalho: "grade 50 x 51".
   *
   * Vem do servidor, e nao do `index.html`, pelo mesmo motivo que tudo o mais
   * aqui: o tamanho da grade e do servidor. Escrito a mao no HTML, ele
   * continuaria dizendo 50x51 no dia em que o mapa crescesse — e um numero
   * errado impresso no cabecalho e pior do que numero nenhum, porque tem
   * cara de conferido.
   */
  grade(cols, rows) {
    if (!cols || !rows) return;
    if (!this._soMudou("grade", [cols, rows])) return;
    this.$("grade-medida").textContent = `${cols} × ${rows}`;
  }

  estatisticas({ filled, total, users, colors }) {
    if (this._soMudou("stats", { filled, total, users, colors })) {
      this.$("stat-pixels").textContent = `${filled}/${total}`;
      this.$("stat-users").textContent = users;
      this.$("stat-colors").textContent = colors;
    }

    const percentual = total > 0 ? (filled / total) * 100 : 0;
    const arredondado = Math.round(percentual * 10) / 10;
    if (this._soMudou("progresso", arredondado)) {
      this.$("progresso-barra").style.width = `${percentual}%`;
      this.$("progresso-texto").textContent = `${arredondado}%`;
    }
  }

  // ------------------------------------------------------------------
  // Ranking
  // ------------------------------------------------------------------

  ranking(itens) {
    if (!this._soMudou("ranking", itens)) return;

    const lista = this.$("ranking-lista");
    if (!itens.length) {
      lista.innerHTML = '<li class="vazio">ninguem pintou ainda</li>';
      return;
    }

    lista.innerHTML = itens
      .map((item) => {
        const cor = item.color || "#8ea2c8";
        const nivel = Number(item.level) || 1;
        const faixa = CORES_DO_NIVEL[Math.min(CORES_DO_NIVEL.length - 1, nivel - 1)];
        return `
          <li class="rank">
            <span class="rank-pos">${item.position}</span>
            <span class="rank-cor" style="--cor:${escapar(cor)}"></span>
            <span class="rank-nome">${escapar(item.name || item.handle)}</span>
            <span class="rank-nivel" style="--faixa:${faixa}">N${nivel}</span>
            <span class="rank-pixels">${item.pixels}</span>
          </li>`;
      })
      .join("");
  }

  // ------------------------------------------------------------------
  // Feed
  // ------------------------------------------------------------------

  feed(itens) {
    if (!this._soMudou("feed", itens)) return;

    const lista = this.$("feed-lista");
    if (!itens.length) {
      lista.innerHTML = '<li class="vazio">as pinturas aparecem aqui</li>';
      return;
    }

    lista.innerHTML = itens
      .map(
        (item) => `
          <li class="feed">
            <span class="feed-cor" style="--cor:${escapar(item.color)}"></span>
            <span class="feed-coord">${escapar(item.coordinate)}</span>
            <span class="feed-user">${escapar(item.user)}</span>
          </li>`
      )
      .join("");
  }

  adicionarAoFeed(item, limite = 6) {
    const lista = this.$("feed-lista");
    const vazio = lista.querySelector(".vazio");
    if (vazio) vazio.remove();

    const li = this.doc.createElement("li");
    li.className = "feed novo";
    li.innerHTML = `
      <span class="feed-cor" style="--cor:${escapar(item.color)}"></span>
      <span class="feed-coord">${escapar(item.coordinate)}</span>
      <span class="feed-user">${escapar(item.user)}</span>`;
    lista.prepend(li);

    while (lista.children.length > limite) lista.lastElementChild.remove();
    this._assinaturas.feed = null;
  }

  // ------------------------------------------------------------------
  // Evento
  // ------------------------------------------------------------------

  evento(evento) {
    const caixa = this.$("evento");

    if (!evento) {
      caixa.classList.remove("aceso");
      caixa.innerHTML = "";
      this._assinaturas.evento = null;
      return;
    }

    caixa.classList.add("aceso");
    // O contador e a barra nascem AQUI, junto com o resto do banner. Eles
    // nao existem em `index.html` — `#evento` e uma secao vazia que so tem
    // conteudo durante um evento. Quando eles foram procurados por id sem
    // serem criados antes, o `null.textContent` estourava dentro do laco de
    // desenho e congelava a tela inteira (ver `dom.test.mjs`).
    caixa.innerHTML = `
      <span class="evento-emoji">${escapar(evento.emoji)}</span>
      <span class="evento-nome">${escapar(evento.name)}</span>
      <span class="evento-bonus">${
        evento.multiplier > 1 ? `PIXELS x${evento.multiplier}` : "PINTE AGORA"
      }</span>
      <span id="evento-tempo"></span>
      <span id="evento-barra"></span>`;

    const restante = Math.max(0, Math.ceil(evento.remaining ?? 0));
    this.$("evento-tempo").textContent = `${restante}s`;
    this.$("evento-barra").style.width = `${
      evento.duration > 0 ? (restante / evento.duration) * 100 : 0
    }%`;
  }

  // ------------------------------------------------------------------
  // Avisos
  // ------------------------------------------------------------------

  aviso(texto, tipo = "info") {
    const caixa = this.$("avisos");
    const div = this.doc.createElement("div");
    div.className = `aviso ${tipo}`;
    div.textContent = texto;
    caixa.prepend(div);
    setTimeout(() => div.remove(), 5200);

    while (caixa.children.length > 4) caixa.lastElementChild.remove();
  }

  // ------------------------------------------------------------------
  // Conexao
  // ------------------------------------------------------------------

  conexao({ conectado, detalhe }) {
    const pilula = this.$("conexao");
    pilula.classList.toggle("fora", !conectado);
    this.$("conexao-texto").textContent = conectado ? "AO VIVO" : "RECONECTANDO";
    // O detalhe e reescrito SEMPRE. Deixar o texto antigo quando ninguem
    // passa um novo deixaria "abrindo o canal" na tela com a LIVE ja no ar.
    this.$("conexao-detalhe").textContent =
      detalhe || (conectado ? "recebendo pinturas" : "tentando de novo");
  }
}
