// Mapa vetorial (MapLibre GL + OpenFreeMap, sem chave de API) com um pin por órgão.

const ESTILO = { claro: "https://tiles.openfreemap.org/styles/positron", escuro: "https://tiles.openfreemap.org/styles/dark" };
const ZOOM_ROTULOS_TODOS = 17;
const ZOOM_ROTULOS_ALERTA = 16;
const ZOOM_FOCO = 16.5;
const DURACAO_FOCO_MS = 600;
const DESTAQUE = { vermelho: 30, ambar: 20, verde: 10, neutro: 0 };
const TEXTO_NIVEL = { vermelho: "dispensa confirmada", ambar: "possível ou parcial", verde: "movimento extra", neutro: "sem alertas" };
const ICONE_RESTAURANTE =
  '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 2a1 1 0 0 1 1 1v6a1 1 0 0 0 1 1V3a1 1 0 1 1 2 0v7a3 3 0 0 1-2 2.83V21a1 1 0 1 1-2 0v-8.17A3 3 0 0 1 5 10V3a1 1 0 0 1 2 0v7a1 1 0 0 0 1-1V3a1 1 0 0 1-1-1Zm10 0c1.66 0 3 2.24 3 5v5a2 2 0 0 1-2 2v7a1 1 0 1 1-2 0V3a1 1 0 0 1 1-1Z"/></svg>';

/**
 * @param {HTMLElement} elemento
 * @param {{ orgaos: Array<{id:string,sigla:string,nome:string,lat:number,lng:number}>, restaurante: {lat:number,lng:number} }} cadastro
 * @param {{ aoSelecionar: (id: string) => void, margens: () => {topo:number, base:number} }} opcoes
 */
export function criarMapa(elemento, cadastro, { aoSelecionar, margens }) {
  const maplibregl = window.maplibregl;
  const movimentoReduzido = matchMedia("(prefers-reduced-motion: reduce)");
  const escuro = matchMedia("(prefers-color-scheme: dark)");
  const limites = cadastro.orgaos.reduce(
    (caixa, o) => caixa.extend([o.lng, o.lat]),
    new maplibregl.LngLatBounds([cadastro.restaurante.lng, cadastro.restaurante.lat], [cadastro.restaurante.lng, cadastro.restaurante.lat]),
  );

  const mapa = new maplibregl.Map({
    container: elemento,
    style: escuro.matches ? ESTILO.escuro : ESTILO.claro,
    bounds: limites,
    fitBoundsOptions: { padding: preenchimento(margens()) },
    attributionControl: false,
    dragRotate: false,
    pitchWithRotate: false,
    touchPitch: false,
    maxZoom: 19,
  });
  mapa.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
  mapa.touchZoomRotate.disableRotation();
  mapa.keyboard.disableRotation();
  escuro.addEventListener("change", () => mapa.setStyle(escuro.matches ? ESTILO.escuro : ESTILO.claro));

  const pins = new Map(cadastro.orgaos.map((orgao) => [orgao.id, criarPin(maplibregl, orgao, aoSelecionar).addTo(mapa)]));
  new maplibregl.Marker({ element: elementoRestaurante(), anchor: "center" })
    .setLngLat([cadastro.restaurante.lng, cadastro.restaurante.lat])
    .addTo(mapa);

  const atualizarRotulos = () => {
    elemento.classList.toggle("mapa--rotulos", mapa.getZoom() >= ZOOM_ROTULOS_TODOS);
    elemento.classList.toggle("mapa--rotulos-alerta", mapa.getZoom() >= ZOOM_ROTULOS_ALERTA);
  };
  mapa.on("zoom", atualizarRotulos);
  atualizarRotulos();

  function enquadrar() {
    mapa.fitBounds(limites, { padding: preenchimento(margens()), animate: !movimentoReduzido.matches, duration: DURACAO_FOCO_MS });
  }

  function focar(id) {
    const pin = pins.get(id);
    if (!pin) return;
    const { topo, base } = margens();
    const camera = { center: pin.getLngLat(), zoom: Math.max(mapa.getZoom(), ZOOM_FOCO), padding: { top: topo, bottom: base, left: 0, right: 0 } };
    if (movimentoReduzido.matches) mapa.jumpTo(camera);
    else mapa.easeTo({ ...camera, duration: DURACAO_FOCO_MS });
  }

  function atualizar(dia, selecionado) {
    for (const [id, pin] of pins) {
      const { nivel } = dia.porOrgao.get(id);
      const envoltorio = pin.getElement();
      const eSelecionado = id === selecionado;
      envoltorio.querySelector(".pin").className = `pin pin--${nivel}${eSelecionado ? " pin--selecionado" : ""}`;
      envoltorio.style.zIndex = String(DESTAQUE[nivel] + (eSelecionado ? 100 : 0));
      envoltorio.setAttribute("aria-label", `${envoltorio.dataset.titulo}: ${TEXTO_NIVEL[nivel]}`);
    }
  }

  return { enquadrar, focar, atualizar };
}

function preenchimento({ topo, base }) {
  return { top: topo + 24, bottom: base + 24, left: 28, right: 28 };
}

function criarPin(maplibregl, orgao, aoSelecionar) {
  const envoltorio = document.createElement("div");
  envoltorio.className = "marcador";
  envoltorio.tabIndex = 0;
  envoltorio.setAttribute("role", "button");
  envoltorio.dataset.titulo = `${orgao.sigla} — ${orgao.nome}`;

  const raiz = document.createElement("div");
  raiz.className = "pin pin--neutro";
  const pulso = document.createElement("span");
  pulso.className = "pin-pulso";
  pulso.style.animationDelay = `${-(Math.random() * 2).toFixed(2)}s`; // pinos não pulsam em uníssono
  const ponto = document.createElement("span");
  ponto.className = "pin-ponto";
  const rotulo = document.createElement("span");
  rotulo.className = "pin-rotulo";
  rotulo.textContent = orgao.sigla;
  raiz.append(pulso, ponto, rotulo);
  envoltorio.append(raiz);

  envoltorio.addEventListener("click", (evento) => {
    evento.stopPropagation();
    aoSelecionar(orgao.id);
  });
  envoltorio.addEventListener("keydown", (evento) => {
    if (evento.key !== "Enter" && evento.key !== " ") return;
    evento.preventDefault();
    aoSelecionar(orgao.id);
  });
  return new maplibregl.Marker({ element: envoltorio, anchor: "center" }).setLngLat([orgao.lng, orgao.lat]);
}

function elementoRestaurante() {
  const raiz = document.createElement("div");
  raiz.className = "restaurante";
  raiz.setAttribute("role", "img");
  raiz.setAttribute("aria-label", "Restaurante");
  raiz.innerHTML = ICONE_RESTAURANTE; // SVG constante, sem dado externo
  return raiz;
}
