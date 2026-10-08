/**
 * O painel de controle.
 *
 * Ele fala com a API por HTTP puro e nao abre WebSocket nenhum de proposito:
 * a tela do OBS ja esta conectada, e uma segunda conexao so para o operador
 * ler numeros nao paga o proprio peso. Uma leitura de `/api/estado` a cada
 * 1,5s e mais que suficiente para acompanhar um ranking.
 *
 * O alfabeto das colunas vem de `ui/js/geometry.js`, o MESMO arquivo que a
 * tela usa. Duas implementacoes de "H vira 7" acabariam divergindo, e o
 * sintoma seria o pior possivel: o painel mostrando um pixel e o jogo
 * pintando outro.
 */

import { analisarRotulo, rotuloDe } from "/ui/js/geometry.js";

const INTERVALO = 1500;

const CATALOGO = [
  ["hora_do_pixel", "🎨 HORA DO PIXEL"],
  ["arco_iris", "🌈 ARCO-ÍRIS"],
  ["pixel_turbo", "⚡ PIXEL TURBO"],
  ["caos", "💥 CAOS"],
  ["desafio", "🎯 DESAFIO"],
];

const doc = document;
const $ = (id) => doc.getElementById(id);

let ultimoEstado = null;
let pixelAtual = null;

// ----------------------------------------------------------------------
// Rede
// ----------------------------------------------------------------------

async function pedir(metodo, caminho, corpo) {
  const opcoes = { method: metodo, headers: {} };
  if (corpo !== undefined) {
    opcoes.headers["Content-Type"] = "application/json";
    opcoes.body = JSON.stringify(corpo);
  }

  const resposta = await fetch(caminho, opcoes);
  let dados = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null;
  }

  if (!resposta.ok) {
    const detalhe = dados && dados.detail ? dados.detail : resposta.statusText;
    throw new Error(`${resposta.status} — ${detalhe}`);
  }
  return dados;
}

function mostrarErro(texto) {
  const caixa = $("erro");
  if (!texto) {
    caixa.hidden = true;
    caixa.textContent = "";
    return;
  }
  caixa.hidden = false;
  caixa.textContent = texto;
}

/** Roda uma acao e conta o que deu errado — sem derrubar o laco de leitura. */
async function tentar(rotulo, acao) {
  try {
    mostrarErro("");
    const resultado = await acao();
    await atualizar();
    return resultado;
  } catch (erro) {
    mostrarErro(`${rotulo}: ${erro.message}`);
    return null;
  }
}

// ----------------------------------------------------------------------
// Leitura do estado
// ----------------------------------------------------------------------

async function atualizar() {
  let dados;
  try {
    dados = await pedir("GET", "/api/estado");
  } catch (erro) {
    $("vivo").className = "morto";
    $("vivo-texto").textContent = "servidor fora do ar";
    mostrarErro(`Não consegui ler o estado: ${erro.message}`);
    return;
  }

  ultimoEstado = dados;

  const canvas = dados.canvas || {};
  const fonte = dados.fonte || {};

  $("m-modo").querySelector("b").textContent = dados.modo_teste ? "TESTE" : "LIVE";
  $("m-fonte").querySelector("b").textContent = fonte.connected ? "ON" : "OFF";
  $("m-fila").querySelector("b").textContent = dados.fila ?? 0;
  $("m-canvas").querySelector("b").textContent = `${canvas.percent ?? 0}%`;
  $("m-users").querySelector("b").textContent = dados.users ?? 0;

  $("vivo").className = "vivo";
  $("vivo-texto").textContent = fonte.detail
    ? String(fonte.detail)
    : "servidor respondendo";

  desenharRanking(dados.ranking || []);
  desenharFeed(dados.feed || []);
  desenharEvento(dados.event);
  desenharUsuarios(dados);
  atualizarBotoes(dados.modo_teste, fonte);
}

function desenharUsuarios(dados) {
  const nomes = new Set();
  for (const item of dados.ranking || []) {
    if (item.handle) nomes.add(item.handle.replace(/^@/, ""));
  }
  for (const item of dados.feed || []) {
    if (item.user) nomes.add(item.user.replace(/^@/, ""));
  }

  const lista = $("usuarios-conhecidos");
  const atual = [...lista.options].map((o) => o.value);
  const novos = [...nomes].filter((n) => !atual.includes(n));
  if (!novos.length && atual.length === nomes.size) return;

  lista.innerHTML = [...nomes].map((n) => `<option value="${escapar(n)}"></option>`).join("");
}

function desenharRanking(itens) {
  const lista = $("ranking-lista");
  if (!itens.length) {
    lista.innerHTML = '<li class="vazio-linha" style="color:#8b9ab8">ninguém pintou ainda</li>';
    return;
  }

  lista.innerHTML = itens
    .map(
      (item) => `
      <li>
        <span class="pos">${item.position}</span>
        <span class="amostra" style="background:${escapar(item.color || "#8ea2c8")}"></span>
        <span class="nome">${escapar(item.name || item.handle)}</span>
        <span class="num">N${Number(item.level) || 1}</span>
        <span class="num">${item.pixels}</span>
      </li>`
    )
    .join("");
}

function desenharFeed(itens) {
  const lista = $("feed-lista");
  if (!itens.length) {
    lista.innerHTML = '<li style="color:#8b9ab8">as pinturas aparecem aqui</li>';
    return;
  }

  lista.innerHTML = itens
    .map(
      (item) => `
      <li>
        <span class="amostra" style="background:${escapar(item.color || "#8ea2c8")}"></span>
        <span class="coord">${escapar(item.coordinate)}</span>
        <span class="nome">${escapar(item.user)}</span>
      </li>`
    )
    .join("");
}

function desenharEvento(evento) {
  const caixa = $("evento-ativo");
  if (!evento) {
    caixa.className = "vazio";
    caixa.textContent = "nenhum evento no ar";
    return;
  }
  caixa.className = "";
  caixa.textContent = `${evento.emoji || ""} ${evento.name} — x${evento.multiplier} — ${
    Math.max(0, Math.ceil(evento.remaining ?? 0))
  }s restantes`;
}

function atualizarBotoes(modoTeste, fonte) {
  // A simulacao so existe em MODO TESTE. Desabilitar e melhor que deixar o
  // streamer clicar e receber um 409: o botao ja diz "isto nao e para agora".
  const travar = !modoTeste;
  $("btn-simular").disabled = travar;
  $("btn-burst").disabled = travar;
  $("cartao-simular").style.opacity = travar ? "0.55" : "1";
  $("cartao-simular").title = travar
    ? "Simulação só existe em MODO TESTE (--test)."
    : "";

  if (travar && fonte && fonte.connected) {
    $("cartao-simular").title = "A LIVE está conectada — não dá para inventar evento nela.";
  }
}

// ----------------------------------------------------------------------
// Acoes
// ----------------------------------------------------------------------

function lerCoordenada(texto) {
  // Com o tamanho do canvas, o painel responde IGUAL ao backend — inclusive
  // recusando o que so o limite separa de uma coordenada valida.
  const canvas = (ultimoEstado && ultimoEstado.canvas) || {};
  const alvo = analisarRotulo(texto, canvas.cols ?? null, canvas.rows ?? null);
  if (!alvo) {
    mostrarErro(
      `Não entendi "${texto}". Use uma coordenada como H5 — a mesma que a audiência comenta.`
    );
    return null;
  }
  return alvo;
}

function montarSimulacao() {
  const tipo = $("sim-tipo").value;
  const usuario = $("sim-usuario").value.trim();
  if (!usuario) {
    mostrarErro("Falta o usuário: sem autor não há a quem creditar o pixel.");
    return null;
  }

  const corpo = { type: tipo, user: usuario };

  if (tipo === "comentario") {
    const texto = $("sim-texto").value.trim();
    if (!texto) {
      mostrarErro("Comentário sem texto não tem o que o parser leia.");
      return null;
    }
    corpo.text = texto;
  } else if (tipo === "presente") {
    corpo.gift = $("campo-gift").value;
    corpo.quantity = Number($("sim-quantidade").value) || 1;
  } else if (tipo === "curtida") {
    corpo.quantity = Number($("sim-quantidade").value) || 1;
  }

  return corpo;
}

function ligarCampos() {
  const tipo = $("sim-tipo");
  const texto = $("campo-texto");
  const presente = $("campo-presente");

  const ajustar = () => {
    const qual = tipo.value;
    texto.hidden = qual !== "comentario";
    presente.hidden = qual !== "presente" && qual !== "curtida";
    $("campo-presente").querySelector("label").textContent =
      qual === "curtida" ? "Quantas curtidas" : "Presente";
    $("campo-gift").hidden = qual !== "presente";
  };

  tipo.addEventListener("change", ajustar);
  ajustar();
}

function ligarCoordenadas() {
  // Os atalhos nascem do proprio canvas: se o mapa virar 50x100, a lista
  // acompanha sem ninguem editar HTML.
  const caixa = $("atalhos-coord");
  const canvas = (ultimoEstado && ultimoEstado.canvas) || { cols: 26, rows: 51 };
  const colunas = Math.min(canvas.cols, 8);
  const linhas = [5, 6, 14, 25];

  const alvos = [];
  for (const y of linhas) {
    for (let x = 0; x < colunas && alvos.length < 10; x += 1) {
      alvos.push(rotuloDe(x, Math.min(y, canvas.rows - 1)));
    }
  }

  caixa.innerHTML = alvos
    .map((rotulo) => `<button class="mini" data-coord="${rotulo}">${rotulo}</button>`)
    .join("");
}

function ligarBotoes() {
  $("btn-simular").addEventListener("click", () => {
    const corpo = montarSimulacao();
    if (!corpo) return;
    tentar("Simular", async () => {
      const r = await pedir("POST", "/api/simular", corpo);
      $("sim-texto").value = "";
      return r;
    });
  });

  $("btn-burst").addEventListener("click", () =>
    tentar("Rajada", () =>
      pedir("POST", "/api/burst", {
        count: Math.max(0, Math.min(5000, Number($("burst").value) || 0)),
      })
    )
  );

  $("btn-inventario").addEventListener("click", () => {
    const usuario = $("inv-usuario").value.trim();
    if (!usuario) {
      mostrarErro("Falta o usuário para cravar o saldo.");
      return;
    }
    tentar("Inventário", () =>
      pedir("POST", "/api/inventario", {
        user: usuario,
        pixels: Math.max(0, Number($("inv-pixels").value) || 0),
      })
    );
  });

  $("btn-inspecionar").addEventListener("click", () => inspecionar($("px-coord").value));

  $("btn-apagar").addEventListener("click", () => {
    if (!pixelAtual) {
      mostrarErro("Inspecione um pixel antes de apagar.");
      return;
    }
    const { x, y } = pixelAtual;
    const rotulo = rotuloDe(x, y);
    tentar("Apagar", async () => {
      const r = await pedir("DELETE", `/api/pixel/${x}/${y}`);
      await inspecionar(rotulo);
      return r;
    });
  });

  $("btn-limpar").addEventListener("click", () => {
    // A confirmacao nao e cerimonia: esta e a unica acao do painel que nao
    // tem desfazer. O numero de pixels vai no texto de proposito — quem clica
    // em "apagar 421 pixels" sabe o que esta perdendo; quem clica em "apagar"
    // so descobre depois.
    const canvas = (ultimoEstado && ultimoEstado.canvas) || {};
    const quantos = canvas.filled || 0;

    const aviso = quantos
      ? `Apagar TODOS os ${quantos} pixels do quadro?\n\n` +
        "O desenho da comunidade some e não tem volta.\n" +
        "O ranking e o histórico ficam."
      : "O quadro já está vazio.\n\nLimpar mesmo assim? Isto mata as animações que estiverem na tela.";

    if (!window.confirm(aviso)) return;

    tentar("Limpar", async () => {
      const resultado = await pedir("DELETE", "/api/canvas");

      // A inspecao apontava para um pixel que acabou de deixar de existir.
      // Deixar o painel mostrando "H5 — @joao — #FF3B5C" ao lado de um quadro
      // em branco e o painel mentindo sobre o proprio jogo.
      pixelAtual = null;
      $("px-coord").value = "";
      $("pixel-detalhe").className = "vazio";
      $("pixel-detalhe").textContent = "nenhum pixel escolhido";

      const apagados = resultado && resultado.cleared ? resultado.cleared : 0;
      const caixa = $("limpar-status");
      caixa.className = "";
      caixa.textContent = apagados
        ? `${apagados} pixels apagados — o quadro está em branco`
        : "quadro já estava em branco; as animações foram limpas";

      return resultado;
    });
  });

  doc.addEventListener("click", (evento) => {
    const alvo = evento.target.closest("[data-coord]");
    if (alvo) {
      const rotulo = alvo.dataset.coord;
      $("sim-texto").value = rotulo;
      $("px-coord").value = rotulo;
      inspecionar(rotulo);
      return;
    }

    const valor = evento.target.closest("[data-valor]");
    if (valor) {
      $("inv-pixels").value = valor.dataset.valor;
      return;
    }

    const eventoBotao = evento.target.closest("[data-evento]");
    if (eventoBotao) {
      tentar("Evento", () =>
        pedir("POST", "/api/evento", { key: eventoBotao.dataset.evento })
      );
    }
  });
}

async function inspecionar(rotulo) {
  const alvo = lerCoordenada(rotulo);
  if (!alvo) return;

  try {
    mostrarErro("");
    const dados = await pedir("GET", `/api/pixel/${alvo.x}/${alvo.y}`);
    pixelAtual = alvo;
    $("px-coord").value = dados.coordinate || rotuloDe(alvo.x, alvo.y);
    desenharPixel(dados);
  } catch (erro) {
    pixelAtual = null;
    $("pixel-detalhe").className = "vazio";
    $("pixel-detalhe").textContent = "nenhum pixel escolhido";
    mostrarErro(`Inspecionar: ${erro.message}`);
  }
}

function desenharPixel(dados) {
  const caixa = $("pixel-detalhe");
  caixa.className = "";

  const cor = dados.color || "";
  const quem = dados.user || dados.owner || "";
  const corpo = cor
    ? `<div class="pixel-topo">
         <span class="pixel-cor" style="background:${escapar(cor)}"></span>
         <span class="pixel-coord">${escapar(dados.coordinate)}</span>
         <span class="nome">${quem ? escapar(quem) : "—"}</span>
         <span class="num">${escapar(cor)}</span>
       </div>`
    : `<div class="pixel-topo">
         <span class="pixel-coord">${escapar(dados.coordinate)}</span>
         <span class="nome">virgem — ninguém pintou aqui</span>
       </div>`;

  const historico = dados.history || [];
  const lista = historico.length
    ? `<ul class="historico">${historico
        .map(
          (h) => `<li>
            <span class="quando">${escapar(hora(h.timestamp))}</span>
            <span class="amostra" style="background:${escapar(h.color || "#8ea2c8")}"></span>
            <span class="quem">${escapar(h.user || "")}</span>
          </li>`
        )
        .join("")}</ul>`
    : "";

  caixa.innerHTML = corpo + lista;
}

function hora(segundos) {
  if (!segundos) return "";
  const d = new Date(Number(segundos) * 1000);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

// ----------------------------------------------------------------------
// Partida
// ----------------------------------------------------------------------

function montarBotoesDeEvento() {
  $("botoes-evento").innerHTML = CATALOGO.map(
    ([chave, rotulo]) =>
      `<button class="botao-evento" data-evento="${chave}">${rotulo}</button>`
  ).join("");
}

function iniciar() {
  montarBotoesDeEvento();
  ligarCampos();
  ligarBotoes();
  atualizar();
  ligarCoordenadas();
  setInterval(atualizar, INTERVALO);
}

if (doc.readyState === "loading") {
  doc.addEventListener("DOMContentLoaded", iniciar);
} else {
  iniciar();
}
