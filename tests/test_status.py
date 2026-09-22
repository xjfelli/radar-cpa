import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import status

RAIZ = Path(__file__).parent.parent
CADASTRO = json.loads((RAIZ / "dados" / "orgaos.json").read_text())
CUIABA = timezone(timedelta(hours=-4))
TERCA = datetime(2026, 9, 22, 19, 7, tzinfo=CUIABA)
ORGAOS_DO_ESTADO = {o["id"] for o in CADASTRO["orgaos"] if o["calendario"] == "EST"}
DECRETO_ANUAL = {"nome": "Decreto 1.787/2025", "url": "https://www.iomat.mt.gov.br/x", "oficial": True}


def evento(data, alvo, nivel="vermelho", fonte=DECRETO_ANUAL, **extra):
    return {
        "data": data, "alvo": alvo, "nivel": nivel, "titulo": "Ponto facultativo", "detalhe": "Dia todo",
        "fonte": fonte, "publicado_em": None, "pode_mudar": True, **extra,
    }


def montar(calendario=(), eventos=(), cancelamentos=(), agora=TERCA):
    extras = {"eventos": list(eventos), "cancelamentos": list(cancelamentos)}
    return status.montar(list(calendario), extras, CADASTRO, agora=agora, fontes=[])


class MontarStatus(unittest.TestCase):
    def test_evento_do_calendario_estadual_acende_todos_os_orgaos_do_estado(self):
        resultado = montar(calendario=[evento("2026-10-28", {"calendario": "EST"})])

        [ponto] = resultado["eventos"]
        self.assertEqual(set(ponto["orgaos"]), ORGAOS_DO_ESTADO)
        self.assertEqual(ponto["nivel"], "vermelho")
        self.assertTrue(ponto["pode_mudar"])

    def test_mostra_cinco_dias_uteis_a_partir_de_hoje(self):
        self.assertEqual(
            montar()["dias"], ["2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-28"]
        )

    def test_no_fim_de_semana_comeca_na_segunda(self):
        sabado = datetime(2026, 9, 26, 8, 0, tzinfo=CUIABA)

        self.assertEqual(montar(agora=sabado)["dias"][0], "2026-09-28")

    def test_feriado_nacional_acende_todos_e_orgao_especifico_so_ele(self):
        resultado = montar(
            calendario=[evento("2026-10-12", {"todos": True})],
            eventos=[evento("2026-09-23", {"orgaos": ["seduc"]}, nivel="ambar")],
        )

        por_data = {e["data"]: e for e in resultado["eventos"]}
        self.assertEqual(len(por_data["2026-10-12"]["orgaos"]), len(CADASTRO["orgaos"]))
        self.assertEqual(por_data["2026-09-23"]["orgaos"], ["seduc"])

    def test_eventos_passados_e_muito_distantes_ficam_de_fora(self):
        resultado = montar(
            calendario=[
                evento("2026-09-21", {"calendario": "EST"}),
                evento("2026-11-02", {"todos": True}),
                evento("2027-01-01", {"todos": True}),
            ]
        )

        self.assertEqual([e["data"] for e in resultado["eventos"]], ["2026-11-02"])

    def test_decreto_que_transfere_a_data_apaga_so_o_ponto_do_estado(self):
        resultado = montar(
            calendario=[
                evento("2026-10-28", {"calendario": "EST"}),
                evento("2026-10-28", {"calendario": "FED"}),
            ],
            cancelamentos=[{"data": "2026-10-28", "alvo": {"calendario": "EST"}, "motivo": "Transferido pelo Decreto 2.300"}],
        )

        [restante] = resultado["eventos"]
        self.assertEqual(restante["orgaos"], ["receita"])

    def test_eventos_repetidos_viram_um_so_e_cada_um_tem_id_unico(self):
        noticia = evento("2026-09-22", {"calendario": "TJMT"}, nivel="ambar", fonte={"nome": "G1", "url": "https://g1.globo.com/a", "oficial": False})

        resultado = montar(eventos=[noticia, dict(noticia), evento("2026-09-23", {"todos": True})])

        ids = [e["id"] for e in resultado["eventos"]]
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 2)


class ValidarStatus(unittest.TestCase):
    def test_status_montado_normalmente_e_valido(self):
        status.validar(montar(calendario=[evento("2026-10-28", {"calendario": "EST"})]), CADASTRO)

    def test_vermelho_sem_fonte_oficial_e_recusado(self):
        imprensa = {"nome": "G1", "url": "https://g1.globo.com/a", "oficial": False}
        invalido = montar(eventos=[evento("2026-09-23", {"calendario": "EST"}, fonte=imprensa)])

        with self.assertRaisesRegex(ValueError, "vermelho"):
            status.validar(invalido, CADASTRO)

    def test_orgao_desconhecido_e_recusado(self):
        invalido = montar(eventos=[evento("2026-09-23", {"orgaos": ["nao-existe"]}, nivel="ambar")])

        with self.assertRaisesRegex(ValueError, "nao-existe"):
            status.validar(invalido, CADASTRO)

    def test_link_que_nao_e_https_e_recusado(self):
        perigoso = {"nome": "X", "url": "javascript:alert(1)", "oficial": False}
        invalido = montar(eventos=[evento("2026-09-23", {"orgaos": ["seduc"]}, nivel="ambar", fonte=perigoso)])

        with self.assertRaisesRegex(ValueError, "url"):
            status.validar(invalido, CADASTRO)


if __name__ == "__main__":
    unittest.main()
