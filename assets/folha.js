// Folha inferior no estilo "Designing Fluid Interfaces" (WWDC 2018):
// rastreio 1:1, projeção de momento, rubber-band nas bordas e mola interrompível.

const DESACELERACAO = 0.998; // mesma curva da rolagem do sistema
const LIMIAR_ARRASTO_PX = 6; // histerese antes de decidir que é arrasto
const JANELA_VELOCIDADE_MS = 100;
const CONSTANTE_ELASTICO = 0.55;
const VELOCIDADE_DE_ARREMESSO = 500; // px/s: acima disso a mola ganha um leve quique
const MOLA_PADRAO = { amortecimento: 1, resposta: 0.35 };
const MOLA_ARREMESSO = { amortecimento: 0.82, resposta: 0.3 };
const ORDEM = ["peek", "meio", "cheio"];

/**
 * @param {{ folha: HTMLElement, zonas: HTMLElement[], alca: HTMLElement,
 *           pontos: () => Record<string, number>, aoMudar: (nome: string) => void }} opcoes
 */
export function criarFolha({ folha, zonas, alca, pontos, aoMudar }) {
  const movimentoReduzido = matchMedia("(prefers-reduced-motion: reduce)");
  let atual = "peek";
  let y = 0;
  let animacao = null;
  let gesto = null;

  const altura = () => folha.offsetHeight;
  const yDe = (nome) => Math.max(0, altura() - pontos()[nome]);
  const aplicar = (valor) => {
    y = valor;
    folha.style.transform = `translate3d(0, ${valor}px, 0)`;
  };

  function irPara(nome, velocidade = 0) {
    animacao?.parar();
    const destino = yDe(nome);
    if (nome !== atual) {
      atual = nome;
      aoMudar(nome);
    }
    if (movimentoReduzido.matches) {
      aplicar(destino);
      return;
    }
    const mola = Math.abs(velocidade) > VELOCIDADE_DE_ARREMESSO ? MOLA_ARREMESSO : MOLA_PADRAO;
    animacao = animarMola(y, destino, velocidade, mola, aplicar);
  }

  function aoPressionar(evento) {
    if (evento.button > 0) return;
    // Aberta por inteiro, o conteúdo rola nativamente; só a alça arrasta.
    if (atual === "cheio" && evento.currentTarget.hasAttribute("data-rola-quando-cheia")) return;
    animacao?.parar(); // interrompe no valor que está na tela, sem salto
    gesto = { id: evento.pointerId, inicioY: evento.clientY, origem: y, arrastando: false, historico: [], alvo: evento.currentTarget };
  }

  function aoMover(evento) {
    if (!gesto || evento.pointerId !== gesto.id) return;
    const deslocamento = evento.clientY - gesto.inicioY;
    if (!gesto.arrastando) {
      if (Math.abs(deslocamento) < LIMIAR_ARRASTO_PX) return;
      gesto.arrastando = true;
      capturar(gesto.alvo, evento.pointerId);
    }
    aplicar(comElastico(gesto.origem + deslocamento, yDe("cheio"), yDe("peek"), altura()));
    gesto.historico = [...gesto.historico, { t: evento.timeStamp, y }].filter(
      (ponto) => evento.timeStamp - ponto.t <= JANELA_VELOCIDADE_MS,
    );
  }

  function aoSoltar(evento) {
    if (!gesto || evento.pointerId !== gesto.id) return;
    const { arrastando, historico } = gesto;
    gesto = null;
    if (!arrastando) return; // toque simples: o clique segue para o botão
    const velocidade = velocidadeDe(historico);
    const projetado = y + projetar(velocidade);
    irPara(maisProximo(projetado, yDe), velocidade);
  }

  function aoCancelar() {
    if (gesto?.arrastando) irPara(atual);
    gesto = null;
  }

  for (const zona of zonas) {
    zona.addEventListener("pointerdown", aoPressionar);
    zona.addEventListener("pointermove", aoMover);
    zona.addEventListener("pointerup", aoSoltar);
    zona.addEventListener("pointercancel", aoCancelar);
  }
  // Um arrasto que termina sobre um botão não deve virar clique nele.
  folha.addEventListener("click", (evento) => {
    if (Math.abs(y - yDe(atual)) > LIMIAR_ARRASTO_PX) evento.stopPropagation();
  }, true);
  alca.addEventListener("click", () => irPara(atual === "peek" ? "meio" : "peek"));
  addEventListener("resize", () => aplicar(yDe(atual)));

  aplicar(yDe(atual));
  return {
    irPara,
    estado: () => atual,
    expandirSeFechada: () => atual === "peek" && irPara("meio"),
    alturaVisivelAlvo: () => pontos()[atual],
  };
}

function animarMola(de, para, velocidadeInicial, { amortecimento, resposta }, aplicar) {
  const rigidez = (2 * Math.PI / resposta) ** 2;
  const atrito = (4 * Math.PI * amortecimento) / resposta;
  const SUBPASSOS = 4;
  let posicao = de;
  let velocidade = velocidadeInicial;
  let anterior = performance.now();
  let quadro = requestAnimationFrame(passo);

  function passo(agora) {
    const dt = Math.min(0.032, (agora - anterior) / 1000) / SUBPASSOS;
    anterior = agora;
    for (let i = 0; i < SUBPASSOS; i += 1) {
      const aceleracao = -rigidez * (posicao - para) - atrito * velocidade;
      velocidade += aceleracao * dt;
      posicao += velocidade * dt;
    }
    if (Math.abs(posicao - para) < 0.5 && Math.abs(velocidade) < 20) {
      aplicar(para);
      return;
    }
    aplicar(posicao);
    quadro = requestAnimationFrame(passo);
  }

  return { parar: () => cancelAnimationFrame(quadro) };
}

/** A captura só melhora o rastreio fora da zona; se o ponteiro já sumiu, seguimos sem ela. */
function capturar(alvo, idPonteiro) {
  try {
    alvo.setPointerCapture(idPonteiro);
  } catch (erro) {
    if (erro.name !== "NotFoundError" && erro.name !== "InvalidStateError") throw erro;
  }
}

function comElastico(valor, minimo, maximo, dimensao) {
  if (valor < minimo) return minimo - elastico(minimo - valor, dimensao);
  if (valor > maximo) return maximo + elastico(valor - maximo, dimensao);
  return valor;
}

function elastico(excesso, dimensao) {
  return (excesso * dimensao * CONSTANTE_ELASTICO) / (dimensao + CONSTANTE_ELASTICO * excesso);
}

function velocidadeDe(historico) {
  if (historico.length < 2) return 0;
  const primeiro = historico[0];
  const ultimo = historico[historico.length - 1];
  const dt = (ultimo.t - primeiro.t) / 1000;
  return dt > 0 ? (ultimo.y - primeiro.y) / dt : 0;
}

function projetar(velocidade) {
  return ((velocidade / 1000) * DESACELERACAO) / (1 - DESACELERACAO);
}

function maisProximo(alvoY, yDe) {
  return ORDEM.reduce((melhor, nome) => (Math.abs(yDe(nome) - alvoY) < Math.abs(yDe(melhor) - alvoY) ? nome : melhor));
}
