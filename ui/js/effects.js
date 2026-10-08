/**
 * As particulas e as animacoes de pintura.
 *
 * Um pool fixo, alocado uma vez. Numa LIVE cheia chegam dezenas de pinturas
 * por segundo; criar um objeto por particula faria o coletor de lixo rodar
 * no meio do desenho, e o sintoma seria um engasgo na tela exatamente quando
 * mais gente esta olhando.
 *
 * Quando o pool enche, a particula mais ANTIGA e reciclada. Perder uma
 * faisca antiga e invisivel; perder o quadro nao e.
 */

const PARTICULAS = 400;
const DURACAO_FAISCA = 0.9;
const DURACAO_ONDA = 0.55;
const MAXIMO_ACOES = 24;

export function hexParaRgb(hex) {
  const limpo = String(hex || "").replace("#", "").trim();
  const cheio =
    limpo.length === 3
      ? limpo
          .split("")
          .map((c) => c + c)
          .join("")
      : limpo.padEnd(6, "0").slice(0, 6);
  const n = Number.parseInt(cheio, 16);
  if (!Number.isFinite(n)) return { r: 255, g: 255, b: 255 };
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

export function rgba(hex, alpha) {
  const { r, g, b } = hexParaRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, alpha))})`;
}

export function clarear(hex, quanto = 0.45) {
  const { r, g, b } = hexParaRgb(hex);
  const mistura = (v) => Math.round(v + (255 - v) * quanto);
  return `rgb(${mistura(r)}, ${mistura(g)}, ${mistura(b)})`;
}

export class Efeitos {
  constructor(quantas = PARTICULAS) {
    this.particulas = new Array(quantas);
    for (let i = 0; i < quantas; i += 1) {
      this.particulas[i] = { viva: false, x: 0, y: 0, vx: 0, vy: 0, vida: 0, total: 1, cor: "#fff", tamanho: 2 };
    }
    this.proxima = 0;
    // As pinturas recentes guardam a propria animacao (onda + tinta). O
    // limite existe para que uma rajada de 2000 eventos nao acumule 2000
    // animacoes vivas e derrube o quadro.
    this.acoes = [];
  }

  _pegar() {
    const p = this.particulas[this.proxima];
    this.proxima = (this.proxima + 1) % this.particulas.length;
    return p;
  }

  /** A explosao de faiscas de uma pintura. */
  faiscas(x, y, cor, quantas = 14) {
    for (let i = 0; i < quantas; i += 1) {
      const p = this._pegar();
      const angulo = Math.random() * Math.PI * 2;
      const forca = 40 + Math.random() * 150;
      p.viva = true;
      p.x = x;
      p.y = y;
      p.vx = Math.cos(angulo) * forca;
      p.vy = Math.sin(angulo) * forca;
      p.total = DURACAO_FAISCA * (0.6 + Math.random() * 0.7);
      p.vida = p.total;
      p.cor = cor;
      p.tamanho = 1.5 + Math.random() * 2.5;
    }
  }

  /** A onda que sai do pixel e a tinta que cobre a celula. */
  registrarPintura({ x, y, cor, celula, efeito }) {
    this.faiscas(x, y, cor, efeito ? 26 : 14);
    this.acoes.push({
      x,
      y,
      cor,
      celula,
      efeito,
      vida: DURACAO_ONDA,
      total: DURACAO_ONDA,
    });
    if (this.acoes.length > MAXIMO_ACOES) {
      this.acoes.splice(0, this.acoes.length - MAXIMO_ACOES);
    }
  }

  limpar() {
    for (const p of this.particulas) p.viva = false;
    this.acoes.length = 0;
  }

  atualizar(dt) {
    for (const p of this.particulas) {
      if (!p.viva) continue;
      p.vida -= dt;
      if (p.vida <= 0) {
        p.viva = false;
        continue;
      }
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      // Atrito: sem ele as faiscas atravessam a tela e incomodam.
      p.vx *= 1 - 3.2 * dt;
      p.vy *= 1 - 3.2 * dt;
      p.vy += 26 * dt;
    }

    for (let i = this.acoes.length - 1; i >= 0; i -= 1) {
      const a = this.acoes[i];
      a.vida -= dt;
      if (a.vida <= 0) this.acoes.splice(i, 1);
    }
  }

  desenhar(ctx) {
    // A camada de particulas e um canvas PROPRIO: ela nao herda a limpeza da
    // grade. Sem estas tres linhas nada apaga a faisca que ja morreu, e cada
    // explosao fica queimada no pixel para sempre — o rastro se acumula ate
    // virar um borrao preso, que foi o defeito relatado.
    //
    // A limpeza roda em espaco de APARELHO, nao no de CSS: `clearRect` com a
    // escala do dpr ligada cobriria so `largura` pixels de um canvas que tem
    // `largura * dpr`, deixando uma faixa suja na borda direita e de baixo.
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.restore();

    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    for (const a of this.acoes) {
      const progresso = 1 - a.vida / a.total;
      const raio = a.celula * (0.6 + progresso * 2.4);
      const alpha = (1 - progresso) * 0.55;

      ctx.beginPath();
      ctx.arc(a.x, a.y, raio, 0, Math.PI * 2);
      ctx.strokeStyle = rgba(a.cor, alpha);
      ctx.lineWidth = Math.max(1, a.celula * 0.14 * (1 - progresso));
      ctx.stroke();

      if (progresso < 0.7) {
        ctx.globalAlpha = 1 - progresso / 0.7;
        ctx.fillStyle = clarear(a.cor, 0.8);
        ctx.fillRect(
          a.x - a.celula / 2,
          a.y - a.celula / 2,
          a.celula,
          a.celula
        );
        ctx.globalAlpha = 1;
      }
    }

    for (const p of this.particulas) {
      if (!p.viva) continue;
      const alpha = Math.max(0, p.vida / p.total);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.tamanho * alpha, 0, Math.PI * 2);
      ctx.fillStyle = rgba(p.cor, alpha);
      ctx.fill();
    }

    ctx.restore();
  }
}
