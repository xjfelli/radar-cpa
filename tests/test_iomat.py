import json
import unittest
from datetime import date
from pathlib import Path

from radar import iomat

FIXTURES = Path(__file__).parent / "fixtures" / "iomat"


def carregar(*nomes):
    return [json.loads((FIXTURES / f"{nome}.json").read_text()) for nome in nomes]


class ExtrairEventosDoDiarioOficial(unittest.TestCase):
    def test_ponto_facultativo_a_partir_das_13h_vira_ambar_para_o_estado(self):
        resultado = iomat.extrair_eventos(carregar("decreto_1980_a_partir_13h_extra"), hoje=date(2026, 4, 1))

        self.assertEqual(len(resultado["eventos"]), 1)
        evento = resultado["eventos"][0]
        self.assertEqual(evento["data"], "2026-04-02")
        self.assertEqual(evento["alvo"], {"calendario": "EST"})
        self.assertEqual(evento["nivel"], "ambar")
        self.assertIn("13h", evento["detalhe"])
        self.assertIn("1.980", evento["titulo"])
        self.assertEqual(evento["publicado_em"], "2026-04-01")
        self.assertTrue(evento["fonte"]["oficial"])
        self.assertEqual(evento["fonte"]["url"], "https://www.iomat.mt.gov.br/portal/edicoes/download/19020/1")

    def test_expediente_ate_as_13h_vira_vermelho_com_o_horario_no_detalhe(self):
        [hit] = carregar("decreto_1980_a_partir_13h_extra")
        conteudo = hit["_source"]["conteudo"].replace("a partir das 13 horas", "com expediente até as 13 horas")
        ate_13h = {**hit, "_source": {**hit["_source"], "conteudo": conteudo}}

        [evento] = iomat.extrair_eventos([ate_13h], hoje=date(2026, 4, 1))["eventos"]

        self.assertEqual(evento["nivel"], "vermelho")
        self.assertEqual(evento["detalhe"], "Expediente até as 13h")

    def test_decreto_so_para_cuiaba_vale_para_o_cpa_o_dia_todo(self):
        resultado = iomat.extrair_eventos(carregar("decreto_1981_so_cuiaba"), hoje=date(2026, 4, 6))

        [evento] = resultado["eventos"]
        self.assertEqual(evento["data"], "2026-04-08")
        self.assertEqual(evento["nivel"], "vermelho")
        self.assertEqual(evento["detalhe"], "Dia todo")

    def test_decreto_para_outro_municipio_e_ignorado(self):
        [hit] = carregar("decreto_1981_so_cuiaba")
        conteudo = hit["_source"]["conteudo"].replace("município de Cuiabá", "município de Rondonópolis")
        outro_municipio = {**hit, "_source": {**hit["_source"], "conteudo": conteudo}}

        resultado = iomat.extrair_eventos([outro_municipio], hoje=date(2026, 4, 6))

        self.assertEqual(resultado["eventos"], [])

    def test_inciso_acrescentado_ao_calendario_anual_vira_ponto_facultativo(self):
        resultado = iomat.extrair_eventos(carregar("decreto_1709_acrescenta_inciso"), hoje=date(2025, 10, 23))

        [evento] = resultado["eventos"]
        self.assertEqual(evento["data"], "2025-10-27")
        self.assertEqual(evento["nivel"], "vermelho")
        self.assertIn("1.709", evento["titulo"])

    def test_decreto_com_dois_incisos_gera_as_duas_datas(self):
        resultado = iomat.extrair_eventos(carregar("decreto_1784_dois_incisos"), hoje=date(2025, 12, 11))

        self.assertEqual([e["data"] for e in resultado["eventos"]], ["2025-12-24", "2025-12-31"])

    def test_alteracao_do_calendario_anual_transfere_a_data(self):
        resultado = iomat.extrair_eventos(carregar("decreto_1504_transfere_dia_servidor_2022"), hoje=date(2022, 10, 25))

        [evento] = resultado["eventos"]
        self.assertEqual(evento["data"], "2022-11-14")
        self.assertIn("1.504", evento["titulo"])
        [cancelamento] = resultado["cancelamentos"]
        self.assertEqual(cancelamento["data"], "2022-10-28")
        self.assertEqual(cancelamento["alvo"], {"calendario": "EST"})
        self.assertIn("1.504", cancelamento["motivo"])

    def test_textos_que_so_citam_ponto_facultativo_nao_geram_nada(self):
        resultado = iomat.extrair_eventos(
            carregar("ruido_licitacao_cita_decreto", "ruido_decreto_municipal"), hoje=date(2025, 10, 1)
        )

        self.assertEqual(resultado, {"eventos": [], "cancelamentos": []})

    def test_datas_que_ja_passaram_sao_descartadas(self):
        resultado = iomat.extrair_eventos(carregar("decreto_2178_jogo_brasil"), hoje=date(2026, 6, 30))

        self.assertEqual(resultado["eventos"], [])


if __name__ == "__main__":
    unittest.main()
