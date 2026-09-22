// Radar CPA — estado e renderização. Regras de negócio ficam em core.js.

import { calcularDia, horasDesde, proximasDatas } from "./core.js";
import { criarFolha } from "./folha.js";
import { criarMapa } from "./mapa.js";

const FUSO = "America/Cuiaba";
const HORAS_PARA_DESATUALIZADO = 14;
const MAX_PROXIMAS_DATAS = 8;
const MAX_SIGLAS_NO_TITULO = 3;
const ALTURA_PEEK = 148;
const ORDEM_NIVEL = { vermelho: 0, ambar: 1, verde: 2, neutro: 3 };
const ROTULO_NIVEL = { vermelho: "Dispensa confirmada", ambar: "Possível ou parcial", verde: "Movimento extra", neutro: "Sem alertas" };
const ROTULO_FAIXA = { normal: "Movimento normal", atencao: "Atenção", fraco: "Movimento fraco" };

const $ = (id) => document.getElementById(id);
const formato = (opcoes) => new Intl.DateTimeFormat("pt-BR", { timeZone: FUSO, ...opcoes });
const FORMATO_SEMANA = formato({ weekday: "short" });
const FORMATO_LONGO = formato({ weekday: "long", day: "numeric", month: "long" });
const FORMATO_CURTO = formato({ weekday: "short", day: "2-digit", month: "2-digit" });
const FORMATO_HORA = formato({ hour: "2-digit", minute: "2-digit" });
const FORMATO_DIA_ISO = formato({ year: "numeric", month: "2-digit", day: "2-digit" });

let estado = { cadastro: null, status: null, dia: null, orgao: null };
let mapa = null;
let folha = null;

function definirEstado(parcial) {
  estado = { ...estado, ...parcial };
  renderizar();
}

async function iniciar() {
  folha = criarFolha({
    folha: $("folha"),
    zonas: [$("alca-area"), $("folha-conteudo")],
    alca: $("alca"),
    pontos: () => ({ peek: ALTURA_PEEK, meio: Math.round(innerHeight * 0.52), cheio: $("folha").offsetHeight }),
    aoMudar: (nome) => {
      $("folha").dataset.estado = nome;
      $("alca").setAttribute("aria-expanded", String(nome !== "peek"));
      $("alca").setAttribute("aria-label", nome === "peek" ? "Expandir lista" : "Recolher lista");
    },
  });
  $("recentrar").addEventListener("click", () => mapa?.enquadrar());
  addEventListener("keydown", (evento) => evento.key === "Escape" && estado.orgao && definirEstado({ orgao: null }));

  try {
    const [cadastro, status] = await Promise.all([buscarJson("dados/orgaos.json"), buscarJson(`dados/status.json?t=${Date.now()}`)]);
    mapa = iniciarMapa(cadastro);
    definirEstado({ cadastro, status, dia: status.dias[0] });
  } catch (erro) {
    mostrarFalha(erro);
  }
}

async function buscarJson(caminho) {
  const resposta = await fetch(caminho, { cache: "no-store" });
  if (!resposta.ok) throw new Error(`${caminho}: HTTP ${resposta.status}`);
  return resposta.json();
}

function iniciarMapa(cadastro) {
  if (!window.maplibregl) {
    $("mapa").append(el("p", { class: "mapa-erro" }, "O mapa não carregou. A lista abaixo continua funcionando."));
    return null;
  }
  return criarMapa($("mapa"), cadastro, {
    aoSelecionar: selecionarOrgao,
    margens: () => ({ topo: document.querySelector(".topo").offsetHeight, base: folha.alturaVisivelAlvo() }),
  });
}

function selecionarOrgao(id) {
  definirEstado({ orgao: id });
  folha.expandirSeFechada();
  mapa?.focar(id);
}

// ---------- Renderização ----------

function renderizar() {
  const { cadastro, status, dia } = estado;
  if (!status) return;
  const calculo = calcularDia(status, cadastro.orgaos, dia);
  renderizarAtualizacao(status);
  renderizarResumo(calculo);
  renderizarDias(status, cadastro);
  mapa?.atualizar(calculo, estado.orgao);
  const orgao = cadastro.orgaos.find((o) => o.id === estado.orgao);
  $("painel-lista").hidden = Boolean(orgao);
  $("painel-detalhe").hidden = !orgao;
  if (orgao) renderizarDetalhe(orgao, calculo);
  else renderizarLista(calculo);
}

function renderizarAtualizacao(status) {
  const horas = horasDesde(status.gerado_em);
  const alvo = $("atualizado");
  const quando = new Date(status.gerado_em);
  const dia = FORMATO_DIA_ISO.format(quando) === FORMATO_DIA_ISO.format(new Date()) ? "hoje" : FORMATO_CURTO.format(quando);
  const desatualizado = horas > HORAS_PARA_DESATUALIZADO;
  alvo.classList.toggle("desatualizado", desatualizado);
  alvo.textContent = desatualizado
    ? `⚠︎ Dados de ${horas}h atrás`
    : `Atualizado ${dia} às ${FORMATO_HORA.format(quando)}`;
}

function renderizarResumo(calculo) {
  const afetados = [...calculo.porOrgao.values()].filter((e) => e.nivel === "vermelho" || e.nivel === "ambar").length;
  $("resumo").dataset.faixa = calculo.faixa;
  $("resumo-titulo").textContent = ROTULO_FAIXA[calculo.faixa];
  const partes = [
    `${rotuloDoDia(calculo.data)}`,
    afetados ? `${afetados} ${afetados === 1 ? "órgão" : "órgãos"} com alerta` : "nenhum órgão com alerta",
  ];
  if (calculo.indice > 0) partes.push(`${Math.round(calculo.indice * 100)}% do movimento em risco`);
  if (calculo.temMovimentoExtra) partes.push("possível movimento extra");
  $("resumo-detalhe").textContent = partes.join(" · ");
  $("medidor-barra").style.width = `${Math.max(calculo.indice * 100, calculo.indice > 0 ? 4 : 0)}%`;
}

function renderizarDias(status, cadastro) {
  const nav = $("dias");
  const botoes = status.dias.map((data) => {
    const { faixa } = calcularDia(status, cadastro.orgaos, data);
    const selecionado = data === estado.dia;
    const botao = el("button", {
      class: "dia", type: "button", role: "tab", "aria-selected": String(selecionado), "data-faixa": faixa,
      "aria-label": `${FORMATO_LONGO.format(meioDia(data))}: ${ROTULO_FAIXA[faixa]}`,
    },
    el("span", { class: "dia-semana" }, FORMATO_SEMANA.format(meioDia(data)).replace(".", "")),
    el("span", { class: "dia-numero" }, data.slice(8)),
    el("span", { class: "dia-ponto", "aria-hidden": "true" }));
    botao.addEventListener("pointerdown", () => data !== estado.dia && definirEstado({ dia: data }));
    botao.addEventListener("click", () => data !== estado.dia && definirEstado({ dia: data }));
    return botao;
  });
  nav.replaceChildren(...botoes);
}

function renderizarLista(calculo) {
  const { cadastro, status } = estado;
  const comAlerta = cadastro.orgaos
    .filter((o) => calculo.porOrgao.get(o.id).nivel !== "neutro")
    .sort((a, b) => ORDEM_NIVEL[calculo.porOrgao.get(a.id).nivel] - ORDEM_NIVEL[calculo.porOrgao.get(b.id).nivel]);
  const semAlerta = cadastro.orgaos.filter((o) => calculo.porOrgao.get(o.id).nivel === "neutro");

  $("painel-lista").replaceChildren(
    el("h2", {}, capitalizar(rotuloDoDia(calculo.data, true))),
    el("p", { class: "sub" }, comAlerta.length ? `${comAlerta.length} com alerta de ${cadastro.orgaos.length} órgãos` : "Nenhum alerta para este dia"),
    comAlerta.length ? listaDeOrgaos(comAlerta, calculo) : el("div", { class: "lista vazio" }, "Todos os órgãos com expediente normal previsto."),
    ...secaoProximasDatas(status),
    el("h3", {}, `Sem alertas (${semAlerta.length})`),
    listaDeOrgaos(semAlerta, calculo),
    rodape(status),
  );
}

function listaDeOrgaos(orgaos, calculo) {
  return el("ul", { class: "lista" }, ...orgaos.map((orgao) => {
    const { nivel } = calculo.porOrgao.get(orgao.id);
    const botao = el("button", { class: `linha nivel-${nivel}`, type: "button" },
      el("span", { class: "linha-ponto", "aria-hidden": "true" }),
      el("span", { class: "linha-textos" }, el("strong", {}, orgao.sigla), el("span", {}, orgao.nome)),
      el("span", { class: "linha-estado" }, ROTULO_NIVEL[nivel]));
    botao.addEventListener("click", () => selecionarOrgao(orgao.id));
    return el("li", {}, botao);
  }));
}

function secaoProximasDatas(status) {
  const proximas = proximasDatas(status).slice(0, MAX_PROXIMAS_DATAS);
  if (!proximas.length) return [];
  const itens = proximas.map(({ data, eventos, nivel }) => {
    const orgaos = new Set(eventos.flatMap((e) => e.orgaos)).size;
    const principal = [...eventos].sort((a, b) => b.orgaos.length - a.orgaos.length)[0];
    const quem = principal.orgaos.length <= MAX_SIGLAS_NO_TITULO ? `${siglas(principal.orgaos)} · ` : "";
    return el("li", {}, el("div", { class: `linha nivel-${nivel}` },
      el("span", { class: "linha-ponto", "aria-hidden": "true" }),
      el("span", { class: "linha-textos" }, el("strong", {}, capitalizar(FORMATO_CURTO.format(meioDia(data)).replace(".", ""))), el("span", {}, quem + principal.titulo)),
      el("span", { class: "linha-estado sem-seta" }, `${orgaos} ${orgaos === 1 ? "órgão" : "órgãos"}`)));
  });
  return [el("h3", {}, "Próximas datas conhecidas"), el("ul", { class: "lista" }, ...itens)];
}

function renderizarDetalhe(orgao, calculo) {
  const { nivel, eventos } = calculo.porOrgao.get(orgao.id);
  const voltar = el("button", { class: "voltar", type: "button" }, "‹ Todos os órgãos");
  voltar.addEventListener("click", () => definirEstado({ orgao: null }));
  const cartoes = eventos.length
    ? [...eventos].sort((a, b) => ORDEM_NIVEL[a.nivel] - ORDEM_NIVEL[b.nivel]).map(cartaoDeNoticia)
    : [el("div", { class: "noticia vazio" }, "Nenhuma notícia que afete o almoço neste dia.")];
  $("painel-detalhe").replaceChildren(
    voltar,
    el("h2", {}, orgao.sigla),
    el("p", { class: "sub" }, orgao.nome + (orgao.posicao_aproximada ? " · posição aproximada no mapa" : "")),
    el("span", { class: `chip nivel-${nivel}` }, `${ROTULO_NIVEL[nivel]} · ${rotuloDoDia(calculo.data)}`),
    ...cartoes,
  );
}

function cartaoDeNoticia(evento) {
  const link = /^https:\/\//.test(evento.fonte.url)
    ? el("a", { href: evento.fonte.url, target: "_blank", rel: "noopener noreferrer" }, `${evento.fonte.nome} ↗`)
    : el("span", {}, evento.fonte.nome);
  const publicado = evento.publicado_em ? ` · publicado em ${FORMATO_CURTO.format(meioDia(evento.publicado_em)).replace(".", "")}` : "";
  return el("article", { class: `noticia nivel-${evento.nivel}` },
    el("span", { class: "chip" }, ROTULO_NIVEL[evento.nivel]),
    evento.pode_mudar ? el("span", { class: "chip nivel-neutro pode-mudar" }, "pode mudar") : "",
    el("h4", {}, evento.titulo),
    el("p", {}, `${evento.detalhe || ""}${publicado}`),
    link);
}

function rodape(status) {
  const fora = status.fontes.filter((f) => !f.ok).map((f) => f.nome);
  return el("p", { class: "rodape" },
    el("strong", {}, "Levantamento automático. "),
    "Junta o Diário Oficial de MT, calendários oficiais dos órgãos e notícias da imprensa. Pode conter erros: confira sempre a fonte. ",
    "Vermelho só aparece com fonte oficial; notícia de jornal fica em âmbar. ",
    fora.length ? `Fora do ar na última coleta: ${fora.join(", ")}.` : "Todas as fontes responderam na última coleta.");
}

function mostrarFalha(erro) {
  $("atualizado").textContent = "";
  $("resumo-titulo").textContent = "Não foi possível carregar";
  $("resumo-detalhe").textContent = "Verifique a conexão e tente de novo.";
  const tentar = el("button", { class: "tentar", type: "button" }, "Tentar de novo");
  tentar.addEventListener("click", () => location.reload());
  $("painel-lista").replaceChildren(el("p", { class: "sub" }, String(erro.message || erro)), tentar);
}

// ---------- Utilitários ----------

function meioDia(dataIso) {
  return new Date(`${dataIso}T12:00:00-04:00`);
}

function rotuloDoDia(dataIso, longo = false) {
  const hoje = FORMATO_DIA_ISO.format(new Date()).split("/").reverse().join("-");
  const amanha = FORMATO_DIA_ISO.format(new Date(Date.now() + 86_400_000)).split("/").reverse().join("-");
  const extenso = longo ? FORMATO_LONGO.format(meioDia(dataIso)) : FORMATO_CURTO.format(meioDia(dataIso)).replace(".", "");
  if (dataIso === hoje) return longo ? `Hoje, ${extenso}` : "hoje";
  if (dataIso === amanha) return longo ? `Amanhã, ${extenso}` : "amanhã";
  return extenso;
}

function siglas(ids) {
  const porId = new Map(estado.cadastro.orgaos.map((o) => [o.id, o.sigla]));
  return ids.map((id) => porId.get(id) ?? id).join(", ");
}

function capitalizar(texto) {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** Cria elementos com texto sempre via textContent — nada vindo do status.json vira HTML. */
function el(tag, atributos, ...filhos) {
  const elemento = document.createElement(tag);
  for (const [nome, valor] of Object.entries(atributos)) elemento.setAttribute(nome, valor);
  elemento.append(...filhos.filter((f) => f !== "" && f != null));
  return elemento;
}

iniciar();
