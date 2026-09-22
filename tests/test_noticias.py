import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import noticias

RAIZ = Path(__file__).parent.parent
RSS = Path(__file__).parent / "fixtures" / "rss"
CADASTRO = json.loads((RAIZ / "dados" / "orgaos.json").read_text())
CUIABA = timezone(timedelta(hours=-4))
AGORA = datetime(2026, 9, 22, 20, 0, tzinfo=CUIABA)


def google_news():
    return noticias.ler_rss((RSS / "google_news_2026-09-22.xml").read_bytes(), fonte="Google Notícias")


def eventos_por_alvo(eventos):
    return {json.dumps(e["alvo"], sort_keys=True): e for e in eventos}


class ExtrairEventosDasNoticias(unittest.TestCase):
    def test_tjmt_com_expediente_suspenso_hoje_vira_ambar(self):
        eventos = noticias.extrair_eventos(google_news(), CADASTRO, agora=AGORA)

        tjmt = eventos_por_alvo(eventos)['{"calendario": "TJMT"}']
        self.assertEqual(tjmt["data"], "2026-09-22")
        self.assertEqual(tjmt["nivel"], "ambar")
        self.assertFalse(tjmt["fonte"]["oficial"])
        self.assertTrue(tjmt["fonte"]["url"].startswith("https://"))
        self.assertIn("TJ", tjmt["titulo"])

    def test_so_orgaos_do_cpa_aparecem_e_nunca_em_vermelho(self):
        eventos = noticias.extrair_eventos(google_news(), CADASTRO, agora=AGORA)

        # Greve da Caixa/Correios, notícias do MS e "servidores ameaçam greve" ficam de fora
        self.assertEqual(
            set(eventos_por_alvo(eventos)), {'{"calendario": "TJMT"}', '{"calendario": "DPE"}'}
        )
        self.assertNotIn("vermelho", {e["nivel"] for e in eventos})

    def test_noticia_de_ontem_sobre_ontem_nao_aparece(self):
        eventos = noticias.extrair_eventos(google_news(), CADASTRO, agora=AGORA + timedelta(days=1))

        self.assertEqual(eventos, [])

    def test_amanha_e_dia_entre_parenteses_viram_datas(self):
        publicado = datetime(2026, 9, 29, 19, 0, tzinfo=CUIABA)
        itens = [
            item("ALMT terá ponto facultativo amanhã", publicado),
            item("Seduc suspende expediente nesta sexta-feira (2)", publicado),
        ]

        eventos = eventos_por_alvo(noticias.extrair_eventos(itens, CADASTRO, agora=publicado))

        self.assertEqual(eventos['{"calendario": "ALMT"}']["data"], "2026-09-30")
        self.assertEqual(eventos['{"orgaos": ["seduc"]}']["data"], "2026-10-02")


class LerRss(unittest.TestCase):
    def test_feed_malformado_ainda_rende_itens(self):
        itens = noticias.ler_rss((RSS / "midianews_malformado.xml").read_bytes(), fonte="MidiaNews")

        self.assertGreater(len(itens), 10)
        self.assertTrue(all(i["publicado"].tzinfo for i in itens))

    def test_feed_iso_8859_1_mantem_acentos(self):
        feed = (
            '<?xml version="1.0" encoding="iso-8859-1"?><rss><channel><item>'
            "<title>Assembleia suspende expediente na sessão</title><link>https://exemplo.com.br/a</link>"
            "<pubDate>Tue, 22 Sep 2026 10:00:00 -0400</pubDate></item></channel></rss>"
        ).encode("iso-8859-1")

        [lido] = noticias.ler_rss(feed, fonte="Teste")

        self.assertEqual(lido["titulo"], "Assembleia suspende expediente na sessão")


def item(titulo, publicado):
    return {"titulo": titulo, "resumo": "", "link": "https://exemplo.com.br/n", "publicado": publicado, "fonte": "Teste"}


if __name__ == "__main__":
    unittest.main()
