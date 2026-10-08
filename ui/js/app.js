/**
 * A costura: WebSocket -> canvas -> HUD.
 *
 * Este arquivo nao sabe desenhar nem sabe ler JSON. Ele so decide QUEM faz o
 * que quando um pacote chega, e mantem o pedaco de estado que a tela precisa:
 * o feed (as ultimas pinturas) e o evento em curso.
 *
 * Duas camadas de canvas: a GRADE e a de PARTICULAS. A grade so redesenha
 * quando um pixel muda; as particulas, todo quadro. Um canvas so obrigaria a
 * redesenhar 1326 celulas 60 vezes por segundo para animar tres faiscas.
 */

import { Efeitos } from "./effects.js";
import { escalaParaCaber } from "./geometry.js";
import { Hud } from "./hud.js";
import { Renderer } from "./renderer.js";
import { Conexao, urlDoWebSocket } from "./ws.js";

const LIMITE_DO_FEED = 6;
const INTERVALO_DO_EVENTO = 250; // a barrinha do evento anda 4x por segundo

export function iniciar(doc = document, janela = window) {
  const palco = doc.getElementById("palco");
  const arena = doc.getElementById("arena");
  const canvasGrade = doc.getElementById("tela");
  const canvasParticulas = doc.getElementById("particulas");

  const hud = new Hud(doc);
  const renderer = new Renderer(canvasGrade);
  const efeitos = new Efeitos();
  const ctxParticulas = canvasParticulas.getContext("2d");

  const estado = {
    feed: [],
    evento: null,
    conectado: false,
    largura: 0,
    altura: 0,
  };

  // ------------------------------------------------------------------
  // Tamanho
  // ------------------------------------------------------------------

  // Segundos desde o primeiro quadro. E o relogio da animacao: o desenho do
  // evento (arco-iris, CAOS, DESAFIO) precisa saber ha quanto tempo esta no ar,
  // e `performance.now()` no meio do Renderer seria um segundo relogio para
  // divergir deste.
  let tempo = 0;

  function ajustar() {
    // O palco PREENCHE a janela, em qualquer janela.
    //
    // O `--escala` existia no CSS desde o primeiro dia, dentro do
    // `transform: scale(var(--escala, 1))` do palco, e NUNCA era escrito por
    // ninguem — entao o palco ficava nos 1080x1920 nominais para sempre. Numa
    // tela menor que isso so havia um jeito de ver o quadro inteiro: dar zoom
    // out no navegador. E era o zoom out que quebrava a grade. O conserto
    // comeca aqui: se a pagina cabe, nao ha por que mexer no zoom.
    //
    // Sao DUAS medidas, e as duas saem da mesma conta. `--escala` e a altura;
    // `--largura-projeto` e quanto de largura a janela pede naquele tamanho.
    // Juntas elas fazem o palco cobrir a janela exatamente, sem faixa preta
    // nas laterais e sem cortar o cabecalho ou o rodape — que e o que "100% no
    // navegador" quer dizer. A largura sobra para a ARENA, entao a grade
    // cresce junto com a janela em vez de ficar boiando no meio.
    //
    // `--largura-projeto` e escrito em PX: a conta devolve um numero sem
    // unidade, e uma varial de CSS sem unidade nao serve para `width`.
    const { escala, larguraProjeto } = escalaParaCaber(
      janela.innerWidth,
      janela.innerHeight
    );
    palco.style.setProperty("--escala", String(escala));
    palco.style.setProperty("--largura-projeto", `${larguraProjeto}px`);

    // A medida vem DEPOIS das duas variaveis: elas mudam o layout, e ler antes
    // daria a arena do tamanho antigo — um canvas de 1080 numa caixa de 607,
    // maior do que o espaco que ele tem.
    //
    // `offsetWidth`, e nao `getBoundingClientRect()`. Os dois parecem
    // intercambiaveis e nao sao: o `getBoundingClientRect` responde no espaco
    // da TELA, ja com o `transform: scale()` do palco aplicado, e o canvas e
    // posicionado no espaco do PALCO. Numa janela de 1366x768 a arena mede
    // 3415 no layout e 1366 na tela; escrevendo 1366 no `style.width` o canvas
    // cobria 40% da arena, colado na esquerda, e a grade ia desenhada num
    // canto. O `offsetWidth` e a resposta de layout, que e a que se quer aqui —
    // e o `escala` vai junto para o buffer sair no tamanho da TELA.
    estado.largura = arena.offsetWidth;
    estado.altura = arena.offsetHeight;

    renderer.redimensionar(estado.largura, estado.altura, escala);

    const dpr = renderer.dpr;
    canvasParticulas.width = Math.round(estado.largura * dpr);
    canvasParticulas.height = Math.round(estado.altura * dpr);
    canvasParticulas.style.width = `${estado.largura}px`;
    canvasParticulas.style.height = `${estado.altura}px`;
    // As particulas sao posicionadas em pixels de projeto, mas o canvas tem
    // `tamanho * dpr` de espaco de sobra, e o `dpr` ja inclui a escala do palco.
    // Sem esta escala elas nasciam no lugar certo so quando os dois eram 1 —
    // num monitor de Windows a 125%, ou com a pagina encolhida, a explosao saia
    // deslocada do pixel que a pessoa acabou de pintar.
    ctxParticulas.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Redesenha AGORA, e nao no proximo quadro: mudar `canvas.width` esvazia
    // o canvas na hora, e entre isso e o proximo quadro a grade fica em
    // branco. O OBS recarrega a fonte ao trocar de cena, entao essa janela
    // cai justamente quando a tela esta sendo olhada.
    renderer.desenhar(tempo);
  }

  janela.addEventListener("resize", ajustar);

  /**
   * Troca o evento em curso: o HUD, o estado e a TELA, num lugar so.
   *
   * O `renderer.efeito` e o pedaco que faltava. O servidor manda `effect` no
   * `event_start` desde o primeiro dia, o navegador guardava o campo — e
   * ninguem desenhava nada com ele. O ARCO-IRIS era um banner com um contador.
   *
   * Escrevendo o efeito AQUI, os tres caminhos que trocam de evento (o aviso
   * ao vivo, o fim dele, e o `estado` de quem conecta no meio) nao podem
   * divergir: os tres passam por esta funcao.
   */
  function definirEvento(evento) {
    estado.evento = evento;
    renderer.efeito = (evento && evento.effect) || null;
    hud.evento(evento);
  }

  // ------------------------------------------------------------------
  // Pacotes do servidor
  // ------------------------------------------------------------------

  function aoMensagem(pacote) {
    switch (pacote.type) {
      // O lote e HETEROGENEO. O servidor junta tudo que nao e estado no mesmo
      // envelope `pixels` para nao mandar 1326 mensagens por quadro — entao
      // `toast`, `event_start` e `event_end` chegam como ITENS de dentro dele,
      // nunca como o tipo do envelope. Despachar pelo tipo do pacote fazia o
      // aviso da rosa, o "NAO ENTENDI" e o banner de evento sumirem sem deixar
      // rastro: o espectador pintava e nao via retorno nenhum.
      case "pixels":
        for (const item of pacote.items || []) aoMensagem(item);
        break;

      case "pixel_painted":
      case "pixel_cleared":
        aplicar(pacote);
        break;

      // O botao LIMPAR do painel. O servidor ja esvaziou o quadro dele; esta
      // metade e a que faz a TELA concordar — sem ela o quadro do OBS
      // continuaria cheio enquanto o do servidor esta vazio, e as duas telas
      // parecem certas.
      case "grid_cleared":
        renderer.definirCanvas(renderer.cols, renderer.rows, []);
        // As faiscas e as ondas vivem ate um segundo DEPOIS da pintura. Sem
        // isto elas continuariam estourando num quadro que ja nao tem aquele
        // pixel: explosao saindo do nada, e o streamer com razao achando que
        // o botao nao funcionou.
        efeitos.limpar();
        renderer.moverCursor(null, null);
        estado.feed = [];
        hud.feed(estado.feed);
        hud.estatisticas({ ...ultimasStats(), filled: 0 });
        break;

      case "hello":
        renderer.definirTela(pacote.tela || {});
        // A faixa de instrucoes e DOM, nao canvas: o tamanho dela e uma
        // variavel de CSS, em px de PROJETO — o palco encolhe tudo junto com o
        // `--escala`, entao o numero da config vale em qualquer janela.
        document.documentElement.style.setProperty(
          "--fonte-instrucoes",
          `${Number((pacote.tela || {}).fonte_instrucoes) || 22}px`
        );
        // A base do texto do RODAPE. Tudo la e um multiplo dela (ver o
        // `#rodape` no style.css), entao este numero sozinho aumenta o rodape
        // inteiro de uma vez.
        document.documentElement.style.setProperty(
          "--fonte-rodape",
          `${Number((pacote.tela || {}).fonte_rodape) || 20}px`
        );
        renderer.definirCanvas(
          pacote.canvas.cols,
          pacote.canvas.rows,
          pacote.canvas.cells
        );
        ajustar();
        hud.estatisticas(pacote.stats);
        hud.ranking(pacote.ranking || []);
        estado.feed = (pacote.feed || []).slice(0, LIMITE_DO_FEED);
        hud.feed(estado.feed);
        // Quem conecta no meio de um evento perdeu o `event_start` que ja
        // passou. Sem isto o telao fica mudo com o multiplicador valendo — e
        // sem o efeito, porque a tela nunca soube que o evento existe.
        definirEvento(pacote.event || null);
        break;

      case "stats":
        hud.estatisticas(pacote);
        break;

      case "ranking":
        hud.ranking(pacote.top || []);
        break;

      case "event_start":
        definirEvento({ ...pacote, remaining: pacote.duration });
        break;

      case "event_end":
        definirEvento(null);
        break;

      case "toast":
        hud.aviso(pacote.text, pacote.kind === "error" ? "erro" : "info");
        break;

      default:
        break;
    }
  }

  function aplicar(item) {
    if (item.type === "pixel_painted") {
      const primeiro = !renderer.cells.has(`${item.x},${item.y}`);
      renderer.pintar(item);

      if (estado.largura > 0) {
        const centro = renderer.centro(item.x, item.y);
        efeitos.registrarPintura({
          x: centro.x,
          y: centro.y,
          cor: item.color,
          celula: renderer.grade.celula,
          efeito: item.effect,
        });
      }

      renderer.moverCursor(item.x, item.y);
      estado.feed = [
        { coordinate: item.coordinate, color: item.color, user: item.user },
        ...estado.feed,
      ].slice(0, LIMITE_DO_FEED);
      hud.adicionarAoFeed(estado.feed[0], LIMITE_DO_FEED);
      if (primeiro) hud.estatisticas({ ...ultimasStats(), filled: renderer.cells.size });
      return;
    }

    if (item.type === "pixel_cleared") {
      renderer.apagar(item);
    }
  }

  function ultimasStats() {
    const total = renderer.cols * renderer.rows;
    return {
      filled: renderer.cells.size,
      total,
      users: Number(doc.getElementById("stat-users").textContent) || 0,
      colors: Number(doc.getElementById("stat-colors").textContent) || 0,
    };
  }

  // ------------------------------------------------------------------
  // Laco de desenho
  // ------------------------------------------------------------------

  let anterior = performance.now();
  let desdeEvento = 0;

  function quadro(agora) {
    const dt = Math.min(0.1, (agora - anterior) / 1000);
    anterior = agora;
    tempo += dt;

    // Um quadro que estoura NAO pode levar o laco junto. O
    // `requestAnimationFrame` esta no fim de proposito — e o que faz o laco
    // ser uma corrente — e por isso qualquer excecao aqui no meio deixava a
    // tela congelada para sempre, sem erro visivel, com o HUD ainda correto
    // (ele e HTML, nao canvas). Foi assim que o `#evento-tempo` inexistente
    // derrubou a transmissao inteira parecendo um problema de tamanho.
    // A tela do OBS fica horas no ar sem ninguem olhando o console.
    try {
      if (renderer.grade) {
        renderer.desenhar(tempo);
        efeitos.atualizar(dt);
        efeitos.desenhar(ctxParticulas);
      }

      if (estado.evento) {
        desdeEvento += dt * 1000;
        if (desdeEvento >= INTERVALO_DO_EVENTO) {
          desdeEvento = 0;
          estado.evento.remaining = Math.max(
            0,
            estado.evento.remaining - INTERVALO_DO_EVENTO / 1000
          );
          hud.evento(estado.evento);
        }
      }
    } catch (erro) {
      console.error("quadro falhou", erro);
    }

    janela.requestAnimationFrame(quadro);
  }

  // ------------------------------------------------------------------
  // Conexao
  // ------------------------------------------------------------------

  const conexao = new Conexao(urlDoWebSocket(janela.location), {
    aoMensagem,
    // A TELA nao mostra mais o estado do canal — a placa "AO VIVO" saiu do
    // cabecalho. Ele continua guardado no `estado`, que e o que o `iniciar()`
    // devolve para inspecao.
    aoStatus: (s) => {
      estado.conectado = s.conectado;
    },
  });

  ajustar();
  conexao.conectar();
  janela.requestAnimationFrame(quadro);

  return { estado, conexao, renderer, efeitos, hud, aoMensagem };
}

if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => iniciar());
  } else {
    iniciar();
  }
}
