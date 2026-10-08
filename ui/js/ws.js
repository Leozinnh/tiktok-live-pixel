/**
 * A conexao com o servidor.
 *
 * Duas coisas aqui importam mais que o resto:
 *
 * 1. **Reconectar sozinho.** Isto e uma tela que fica aberta por horas. Uma
 *    queda de rede de dois segundos nao pode virar um canvas congelado ate
 *    alguem perceber — e quem percebe e a audiencia, no comentario.
 *
 * 2. **Nunca mandar pintura.** O cliente so ESCUTA (spec §12). A unica coisa
 *    que sai daqui e `ping`. Pintura nasce de evento do TikTok ou do painel,
 *    e e isso que impede alguem de abrir o endereco do streamer e desenhar
 *    de graca.
 *
 * O atraso entre tentativas cresce ate um teto. Sem o teto, um servidor
 * fora do ar viraria mil tentativas por segundo; sem o crescimento, a
 * reconexao martelaria o servidor enquanto ele ainda esta subindo.
 */

const ESPERA_INICIAL = 500;
const ESPERA_MAXIMA = 8000;
const INTERVALO_PING = 20000;

export class Conexao {
  constructor(url, { aoMensagem, aoStatus } = {}) {
    this.url = url;
    this.aoMensagem = aoMensagem || (() => {});
    this.aoStatus = aoStatus || (() => {});
    this.espera = ESPERA_INICIAL;
    this.tentativas = 0;
    this.fechado = false;
    this.ws = null;
    this._ping = null;
    this._relogio = null;
  }

  conectar() {
    if (this.fechado) return;

    let ws;
    try {
      ws = new WebSocket(this.url);
    } catch (erro) {
      this._reagendar();
      return;
    }

    this.ws = ws;

    ws.onopen = () => {
      this.espera = ESPERA_INICIAL;
      this.tentativas = 0;
      this.aoStatus({ conectado: true });
      this._ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, INTERVALO_PING);
    };

    ws.onmessage = (evento) => {
      let pacote;
      try {
        pacote = JSON.parse(evento.data);
      } catch {
        return; // Um pacote ilegivel nao pode derrubar a tela.
      }
      if (pacote && typeof pacote.type === "string") this.aoMensagem(pacote);
    };

    ws.onclose = () => {
      this._limparRelogio();
      this.aoStatus({ conectado: false });
      this._reagendar();
    };

    ws.onerror = () => {
      // O `onclose` vem logo atras e e quem reagenda. Fechar aqui tambem
      // agendaria duas vezes a mesma tentativa.
    };
  }

  _reagendar() {
    if (this.fechado) return;
    clearTimeout(this._relogio);
    this._relogio = setTimeout(() => this.conectar(), this.espera);
    this.tentativas += 1;
    this.espera = Math.min(ESPERA_MAXIMA, Math.round(this.espera * 1.7));
  }

  _limparRelogio() {
    clearInterval(this._ping);
    this._ping = null;
  }

  fechar() {
    this.fechado = true;
    clearTimeout(this._relogio);
    this._limparRelogio();
    if (this.ws) {
      this.ws.onclose = null; // Senao o fechamento agendaria reconexao.
      this.ws.close();
    }
  }
}

/** `ws://` ou `wss://` a partir do endereco da propria pagina. */
export function urlDoWebSocket(location) {
  const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocolo}//${location.host}/ws`;
}
