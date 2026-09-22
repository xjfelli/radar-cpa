// Regras de negócio da página — puras, sem DOM, testadas em tests/core.test.mjs.

export const PESO_POR_PORTE = { G: 3, M: 2, P: 1 };
const PESO_AMBAR = 0.5;
const LIMITE_ATENCAO = 0.15;
const LIMITE_FRACO = 0.4;
const GRAVIDADE = { neutro: 0, verde: 1, ambar: 2, vermelho: 3 }; // a notícia ruim prevalece

/** Estado de cada órgão numa data + índice de movimento do dia. */
export function calcularDia(status, orgaos, data) {
  const eventosDoDia = status.eventos.filter((evento) => evento.data === data);
  const porOrgao = new Map(orgaos.map((orgao) => [orgao.id, { nivel: "neutro", eventos: [] }]));

  for (const evento of eventosDoDia) {
    for (const id of evento.orgaos) {
      const atual = porOrgao.get(id);
      if (!atual) continue;
      const nivel = GRAVIDADE[evento.nivel] > GRAVIDADE[atual.nivel] ? evento.nivel : atual.nivel;
      porOrgao.set(id, { nivel, eventos: [...atual.eventos, evento] });
    }
  }

  const indice = calcularIndice(orgaos, porOrgao);
  const temMovimentoExtra = [...porOrgao.values()].some((estado) => estado.nivel === "verde");
  return { data, porOrgao, indice, faixa: faixaDoIndice(indice), temMovimentoExtra };
}

function calcularIndice(orgaos, porOrgao) {
  let total = 0;
  let afetado = 0;
  for (const orgao of orgaos) {
    const peso = PESO_POR_PORTE[orgao.porte] ?? 1;
    const { nivel } = porOrgao.get(orgao.id);
    total += peso;
    if (nivel === "vermelho") afetado += peso;
    if (nivel === "ambar") afetado += peso * PESO_AMBAR;
  }
  return total === 0 ? 0 : afetado / total;
}

function faixaDoIndice(indice) {
  if (indice > LIMITE_FRACO) return "fraco";
  if (indice >= LIMITE_ATENCAO) return "atencao";
  return "normal";
}

const MS_POR_HORA = 3_600_000;

/** Horas inteiras desde o carimbo ISO (com fuso) até `agora`. */
export function horasDesde(carimboIso, agora = new Date()) {
  return Math.floor((agora.getTime() - new Date(carimboIso).getTime()) / MS_POR_HORA);
}

/** Datas com eventos depois dos dias exibidos, cada uma com sua gravidade máxima. */
export function proximasDatas(status) {
  const ultimoDia = status.dias[status.dias.length - 1];
  const porData = new Map();
  for (const evento of status.eventos) {
    if (evento.data <= ultimoDia) continue;
    porData.set(evento.data, [...(porData.get(evento.data) ?? []), evento]);
  }
  return [...porData.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([data, eventos]) => ({ data, eventos, nivel: nivelMaisGrave(eventos) }));
}

function nivelMaisGrave(eventos) {
  return eventos.reduce((pior, e) => (GRAVIDADE[e.nivel] > GRAVIDADE[pior] ? e.nivel : pior), "neutro");
}
