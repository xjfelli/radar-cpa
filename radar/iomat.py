"""Leitura dos atos de ponto facultativo publicados no Diário Oficial de MT (IOMAT).

Entrada: `hits` da busca JSON do IOMAT (`_source.conteudo` é o texto OCR de uma página).
Saída: eventos para o calendário do Executivo estadual ("EST") e cancelamentos de datas transferidas.
"""

import re
from collections.abc import Iterator
from datetime import date

from radar.texto import montar_data, normalizar

URL_PAGINA = "https://www.iomat.mt.gov.br/portal/edicoes/download/{diario_id}/{pagina}"
HORA_LIMITE_ALMOCO = 12  # dispensa que começa depois disso ainda deixa parte do almoço acontecer

_MES = r"(janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
_DECLARACAO = re.compile(
    r"(?:fica declarado|declara-se|declara) ponto facultativo,?(?P<escopo>[^.]{0,200}?)"
    r"(?:o|no|os|nos) dias? (?P<dias>\d{1,2}(?:o|º)?(?:\s*(?:,|e)\s*\d{1,2}(?:o|º)?)*) de " + _MES
    + r"(?: de (?P<ano>\d{4}))?(?P<resto>[^.]{0,80})"
)
# Inciso incluído/alterado no decreto anual: "XVIII - 27 de outubro (segunda feira) - ponto facultativo"
_INCISO = re.compile(
    r"\b[ivxlc]+ ?-? ?(?P<dias>\d{1,2}) de " + _MES + r"(?: de (?P<ano>\d{4}))? ?(?:\([^)]{0,20}\))?"
    r"(?: ?- ?[^;.\"-]{0,80})? ?- ?ponto facultativo(?P<resto>[^;.\"]{0,60})"
)
_A_PARTIR = re.compile(r"a partir das (\d{1,2}) ?(?:h|horas)")
_ATE = re.compile(r"ate as (\d{1,2}) ?(?:h|horas)")
HORA_FIM_ALMOCO = 13  # expediente que acaba até aqui esvazia o almoço
_MUNICIPIO = re.compile(r"(?:situad|sediad|localizad)\w* n[oa] municipio de ([a-z ]+?)(?:,|$| o | os | no | nos )")
MUNICIPIO_DO_CPA = "cuiaba"
_MES_GRUPO = {_DECLARACAO.pattern: 3, _INCISO.pattern: 2}  # posição do grupo sem nome do mês em cada padrão
# Cabeçalho do próprio ato ("DECRETO Nº 1.709, DE ... DE 2025."); citações vêm após artigo ("altera o decreto nº").
_DECRETO_CABECALHO = re.compile(
    r"(?<!\bo )(?<!\bdo )(?<!\bao )(?<!\bno )decreto n[o°º]? ?([\d.]+\d), de \d{1,2}o? de [a-z]+ de \d{4}\."
)
_DIA_ANTIGO = re.compile(r"que divulgou o dia (?P<dias>\d{1,2}) de " + _MES)


def extrair_eventos(hits: list[dict], hoje: date) -> dict:
    eventos, cancelamentos = [], []
    for hit in hits:
        fonte = hit["_source"]
        texto = normalizar(fonte["conteudo"])
        publicado_em = date.fromisoformat(fonte["data"])
        url = URL_PAGINA.format(diario_id=fonte["diario_id"], pagina=fonte["pagina"])
        for achado in _DECLARACAO.finditer(texto):
            if _vale_para_o_cpa(achado["escopo"]):
                eventos.extend(_eventos_do_achado(achado, texto, publicado_em, url, hoje))
        for achado in _INCISO.finditer(texto):
            eventos.extend(_eventos_do_achado(achado, texto, publicado_em, url, hoje))
            cancelamentos.extend(_cancelamentos_da_alteracao(texto, achado.start(), publicado_em, hoje))
    return {"eventos": eventos, "cancelamentos": cancelamentos}


def _cancelamentos_da_alteracao(texto: str, posicao: int, publicado_em: date, hoje: date) -> Iterator[dict]:
    """Um inciso *alterado* substitui a data que o 'considerando' diz ter sido divulgada antes."""
    ato = texto[max(0, posicao - 1500):posicao]
    antigo = _DIA_ANTIGO.search(ato)
    if "fica alterado" not in ato or antigo is None:
        return
    data = montar_data(int(antigo["dias"]), antigo.group(2), None, publicado_em)
    if data is None or data < hoje:
        return
    numero = _numero_do_decreto(texto, posicao)
    yield {
        "data": data.isoformat(),
        "alvo": {"calendario": "EST"},
        "motivo": f"Transferido pelo Decreto {numero}" if numero else "Transferido por decreto estadual",
    }


def _eventos_do_achado(achado: re.Match, texto: str, publicado_em: date, url: str, hoje: date) -> Iterator[dict]:
    ano = int(achado["ano"]) if achado["ano"] else None
    mes = achado.group(_MES_GRUPO[achado.re.pattern])
    nivel, detalhe = _classificar_horario(achado["resto"])
    numero = _numero_do_decreto(texto, achado.start())
    for dia in re.findall(r"\d{1,2}", achado["dias"]):
        data = montar_data(int(dia), mes, ano, publicado_em)
        if data is None or data < hoje:
            continue
        yield {
            "data": data.isoformat(),
            "alvo": {"calendario": "EST"},
            "nivel": nivel,
            "titulo": f"Ponto facultativo — Decreto {numero}" if numero else "Ponto facultativo — decreto estadual",
            "detalhe": detalhe,
            "fonte": {"nome": "Diário Oficial de MT", "url": url, "oficial": True},
            "publicado_em": publicado_em.isoformat(),
            "pode_mudar": False,
        }


def _vale_para_o_cpa(escopo: str) -> bool:
    municipio = _MUNICIPIO.search(escopo)
    return municipio is None or municipio.group(1).strip() == MUNICIPIO_DO_CPA


def _classificar_horario(trecho: str) -> tuple[str, str]:
    ate = _ATE.search(trecho)
    if ate:
        hora = int(ate.group(1))
        nivel = "vermelho" if hora <= HORA_FIM_ALMOCO else "ambar"
        return nivel, f"Expediente até as {hora}h"
    a_partir = _A_PARTIR.search(trecho)
    if a_partir:
        hora = int(a_partir.group(1))
        nivel = "ambar" if hora > HORA_LIMITE_ALMOCO else "vermelho"
        return nivel, f"A partir das {hora}h"
    return "vermelho", "Dia todo"


def _numero_do_decreto(texto: str, posicao: int) -> str | None:
    anteriores = _DECRETO_CABECALHO.findall(texto[:posicao])
    return anteriores[-1] if anteriores else None
