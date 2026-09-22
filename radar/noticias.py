"""Notícias (RSS) → eventos âmbar/verde por órgão. Imprensa nunca gera vermelho (regra de confiança)."""

import html
import json
import re
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime

from radar.texto import montar_data, normalizar

JANELA_NOTICIA = timedelta(days=10)
HORIZONTE = timedelta(days=30)

_ITEM = re.compile(r"<item\b.*?>(.*?)</item>", re.S | re.I)
_CAMPO = r"<{tag}\b[^>]*>(.*?)</{tag}>"
_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
_TAGS = re.compile(r"<[^>]+>")
_ENCODING = re.compile(rb'encoding=["\']([\w-]+)["\']')

_NEGATIVO = re.compile(
    r"ponto facultativo|suspend\w* (?:o |os )?expediente|expediente (?:suspenso|cancelado|reduzido)"
    r"|suspensao (?:do |de )?expediente|sem expediente|cancela\w* (?:o )?expediente|nao (?:havera|tera) expediente"
    r"|recesso|\bgreve\b|paralisac|teletrabalho|falta de (?:agua|energia)|sem (?:agua|energia)|apagao"
)
_POSITIVO = re.compile(r"mutirao|feirao|(?:evento|feira|festival)\b.{0,40}centro politico")
_DESCARTAR = re.compile(
    r"nega\w* ponto facultativo|descart\w* ponto facultativo|nao (?:havera|tera) ponto facultativo"
    r"|expediente normal|retoma\w* (?:o )?expediente|retomada do expediente|ameac\w*|indicativo de greve|cogita"
)
_OUTRO_ESTADO = re.compile(r"mato grosso do sul|campo grande|\bms\b")

_DIA_SEMANA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
_DIA_ENTRE_PARENTESES = re.compile(r"(?:segunda|terca|quarta|quinta|sexta|sabado|domingo)(?:-feira)? \((\d{1,2})\)")
_DIA_BARRA_MES = re.compile(r"\b(\d{1,2})/(\d{1,2})\b")
_DIA_POR_EXTENSO = re.compile(r"\b(\d{1,2}) de (janeiro|fevereiro|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b")
_NESTA_DIA = re.compile(r"(?:nesta|neste|na proxima|no proximo) (segunda|terca|quarta|quinta|sexta)")


def ler_rss(conteudo: bytes, fonte: str) -> list[dict]:
    """Parser tolerante (regex): feeds reais vêm com XML malformado e codificações variadas."""
    texto = conteudo.decode(_codificacao(conteudo), errors="replace")
    itens = []
    for bruto in _ITEM.findall(texto):
        titulo = _campo(bruto, "title")
        link = _campo(bruto, "link")
        publicado = _data_rss(_campo(bruto, "pubDate"))
        if titulo and link and publicado:
            itens.append({
                "titulo": titulo,
                "resumo": _campo(bruto, "description"),
                "link": link,
                "publicado": publicado,
                "fonte": _campo(bruto, "source") or fonte,
            })
    return itens


def extrair_eventos(itens: list[dict], cadastro: dict, agora: datetime) -> list[dict]:
    apelidos = _indice_de_apelidos(cadastro)
    hoje = agora.date()
    por_chave: dict[tuple, dict] = {}
    for item in sorted(itens, key=lambda i: i["publicado"], reverse=True):
        if agora - item["publicado"] > JANELA_NOTICIA:
            continue
        for evento in _eventos_do_item(item, apelidos, agora):
            data = date.fromisoformat(evento["data"])
            if not hoje <= data <= hoje + HORIZONTE:
                continue
            chave = (evento["data"], json.dumps(evento["alvo"], sort_keys=True), evento["nivel"])
            por_chave.setdefault(chave, evento)  # o mais recente vence
    return list(por_chave.values())


def _eventos_do_item(item: dict, apelidos: list[tuple[str, dict]], agora: datetime) -> Iterator[dict]:
    texto = normalizar(f"{item['titulo']} {_sem_html(item['resumo'])}")
    if _DESCARTAR.search(texto) or (_OUTRO_ESTADO.search(texto) and "cuiaba" not in texto):
        return
    if _NEGATIVO.search(texto):
        nivel = "ambar"
    elif _POSITIVO.search(texto):
        nivel = "verde"
    else:
        return
    alvos = {
        json.dumps(alvo, sort_keys=True): alvo
        for apelido, alvo in apelidos
        if re.search(rf"\b{re.escape(apelido)}\b", texto)
    }
    if not alvos:
        return
    data = _data_do_evento(texto, item["publicado"].astimezone(agora.tzinfo))
    for alvo in alvos.values():
        yield {
            "data": data.isoformat(),
            "alvo": alvo,
            "nivel": nivel,
            "titulo": _titulo_limpo(item["titulo"]),
            "detalhe": "Notícia na imprensa — confira a fonte",
            "fonte": {"nome": item["fonte"], "url": item["link"], "oficial": False},
            "publicado_em": item["publicado"].astimezone(agora.tzinfo).date().isoformat(),
            "pode_mudar": True,
        }


def _indice_de_apelidos(cadastro: dict) -> list[tuple[str, dict]]:
    """Apelidos mais longos primeiro; grupo inteiro (calendário) ou órgão específico."""
    pares = [(normalizar(a), {"calendario": codigo}) for codigo, g in cadastro["grupos"].items() for a in g["apelidos"]]
    pares += [(normalizar(a), {"orgaos": [o["id"]]}) for o in cadastro["orgaos"] for a in o["apelidos"]]
    return sorted(pares, key=lambda par: len(par[0]), reverse=True)


def _data_do_evento(texto: str, publicado: datetime) -> date:
    referencia = publicado.date()
    if m := _DIA_ENTRE_PARENTESES.search(texto):
        return _proximo_dia_do_mes(int(m.group(1)), referencia)
    if m := _DIA_POR_EXTENSO.search(texto):
        return montar_data(int(m.group(1)), m.group(2), None, referencia) or referencia
    if m := _DIA_BARRA_MES.search(texto):
        try:
            return _ajustar_ano(date(referencia.year, int(m.group(2)), int(m.group(1))), referencia)
        except ValueError:
            pass  # "31/02" e afins: segue para os próximos formatos de data
    if "amanha" in texto:
        return referencia + timedelta(days=1)
    if m := _NESTA_DIA.search(texto):
        alvo = _DIA_SEMANA.index(m.group(1))
        return referencia + timedelta(days=(alvo - referencia.weekday()) % 7)
    return referencia


def _proximo_dia_do_mes(dia: int, referencia: date) -> date:
    try:
        candidato = referencia.replace(day=dia)
    except ValueError:
        return referencia
    if (referencia - candidato).days > 7:  # "(2)" citado no fim do mês é o dia 2 do mês seguinte
        proximo_mes = (referencia.replace(day=1) + timedelta(days=32)).replace(day=1)
        try:
            return proximo_mes.replace(day=dia)
        except ValueError:
            return referencia
    return candidato


def _ajustar_ano(candidato: date, referencia: date) -> date:
    return candidato.replace(year=candidato.year + 1) if (referencia - candidato).days > 7 else candidato


def _codificacao(conteudo: bytes) -> str:
    declarada = _ENCODING.search(conteudo[:200])
    return declarada.group(1).decode() if declarada else "utf-8"


def _campo(bruto: str, tag: str) -> str:
    achado = re.search(_CAMPO.format(tag=tag), bruto, re.S | re.I)
    if not achado:
        return ""
    valor = _CDATA.sub(r"\1", achado.group(1))
    return html.unescape(valor).strip()


def _sem_html(valor: str) -> str:
    return _TAGS.sub(" ", html.unescape(valor))


def _data_rss(valor: str) -> datetime | None:
    try:
        data = parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None
    return data if data.tzinfo else None


def _titulo_limpo(titulo: str) -> str:
    """Google Notícias acrescenta " - Nome do veículo" ao título."""
    return re.sub(r"\s+-\s+[^-]{2,60}$", "", titulo).strip()
