import assert from "node:assert/strict";
import { test } from "node:test";

import { calcularDia, estaDesatualizado, horasDesde, proximasDatas } from "../assets/core.js";

const orgaos = [
  { id: "seduc", porte: "G" }, // peso 3
  { id: "sefaz", porte: "G" }, // peso 3
  { id: "tce", porte: "M" }, // peso 2
  { id: "iomat", porte: "P" }, // peso 1
  { id: "secom", porte: "P" }, // peso 1
];

function evento(orgaosDoEvento, nivel, data = "2026-10-28") {
  return { id: `${nivel}-${orgaosDoEvento.join()}`, data, orgaos: orgaosDoEvento, nivel, titulo: "t", fonte: {} };
}

test("sem eventos o dia é normal e todos os órgãos ficam neutros", () => {
  const dia = calcularDia({ eventos: [] }, orgaos, "2026-10-28");

  assert.equal(dia.faixa, "normal");
  assert.equal(dia.indice, 0);
  assert.equal(dia.porOrgao.get("seduc").nivel, "neutro");
});

test("a notícia ruim prevalece sobre as outras no mesmo órgão", () => {
  const status = { eventos: [evento(["seduc"], "verde"), evento(["seduc"], "vermelho"), evento(["seduc"], "ambar")] };

  const seduc = calcularDia(status, orgaos, "2026-10-28").porOrgao.get("seduc");

  assert.equal(seduc.nivel, "vermelho");
  assert.equal(seduc.eventos.length, 3);
});

test("índice pondera porte: dois órgãos grandes fora (6 de 10) é movimento fraco", () => {
  const dia = calcularDia({ eventos: [evento(["seduc", "sefaz"], "vermelho")] }, orgaos, "2026-10-28");

  assert.equal(dia.indice, 0.6);
  assert.equal(dia.faixa, "fraco");
});

test("âmbar conta metade; 15% já é atenção e 40% ainda é atenção", () => {
  const quinze = { eventos: [evento(["iomat"], "vermelho"), evento(["secom"], "ambar")] }; // 1 + 0,5 = 1,5/10
  const quarenta = { eventos: [evento(["tce", "iomat", "secom"], "vermelho")] }; // 4/10

  assert.equal(calcularDia(quinze, orgaos, "2026-10-28").faixa, "atencao");
  assert.equal(calcularDia(quarenta, orgaos, "2026-10-28").faixa, "atencao");
});

test("eventos de outro dia não afetam a data consultada", () => {
  const dia = calcularDia({ eventos: [evento(["seduc"], "vermelho", "2026-10-29")] }, orgaos, "2026-10-28");

  assert.equal(dia.porOrgao.get("seduc").nivel, "neutro");
});

test("verde não pesa no índice mas sinaliza movimento extra", () => {
  const dia = calcularDia({ eventos: [evento(["tce"], "verde")] }, orgaos, "2026-10-28");

  assert.equal(dia.indice, 0);
  assert.equal(dia.temMovimentoExtra, true);
});

test("horas desde a atualização usam o fuso do próprio carimbo", () => {
  const agora = new Date("2026-09-23T09:07:00-04:00");

  assert.equal(horasDesde("2026-09-22T19:07-04:00", agora), 14);
});

test("próximas datas agrupam eventos depois dos dias exibidos, em ordem", () => {
  const status = {
    dias: ["2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28"],
    eventos: [
      evento(["seduc"], "vermelho", "2026-09-23"),
      evento(["tce"], "vermelho", "2026-10-12"),
      evento(["seduc", "sefaz"], "vermelho", "2026-10-12"),
      evento(["iomat"], "ambar", "2026-10-05"),
    ],
  };

  const proximas = proximasDatas(status);

  assert.deepEqual(proximas.map((d) => d.data), ["2026-10-05", "2026-10-12"]);
  assert.equal(proximas[1].eventos.length, 2);
  assert.equal(proximas[1].nivel, "vermelho");
});

test("dado fica desatualizado assim que passa de 14h, sem esperar a hora cheia", () => {
  const carimbo = "2026-09-22T19:07-04:00";

  assert.equal(estaDesatualizado(carimbo, new Date("2026-09-23T09:06:00-04:00")), false); // 13h59
  assert.equal(estaDesatualizado(carimbo, new Date("2026-09-23T09:37:00-04:00")), true); // 14h30
});
