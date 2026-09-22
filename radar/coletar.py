"""Coleta as fontes, monta e valida o status. Uso: python -m radar.coletar"""

import json
import logging
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from radar import iomat, noticias, status

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
CUIABA = timezone(timedelta(hours=-4))  # MT não tem horário de verão
TIMEOUT_SEGUNDOS = 30
USER_AGENT = "RadarCPA/1.0 (+https://github.com/xjfelli)"
DIAS_DE_DIARIO = 10
PAGINAS_POR_BUSCA = 3
RESULTADOS_POR_PAGINA = 10

BUSCA_IOMAT = "https://www.iomat.mt.gov.br/busca/busca/buscar/query/{pagina}/di:{inicio}/df:{fim}/?1=1&q={termo}"
TERMOS_IOMAT = ['"Fica declarado ponto facultativo"', '"Declara ponto facultativo"', '"ponto facultativo" inciso']

GOOGLE_NEWS = "https://news.google.com/rss/search?hl=pt-BR&gl=BR&ceid=BR:pt-419&q=" + urllib.parse.quote(
    '("ponto facultativo" OR expediente OR greve OR recesso OR mutirão) '
    "(Cuiabá OR \"Mato Grosso\" OR TJMT OR ALMT OR MPMT OR \"TCE-MT\" OR Detran OR Seduc OR Sefaz) when:10d"
)
FEEDS = {
    "Google Notícias": GOOGLE_NEWS,
    "g1 MT": "https://g1.globo.com/rss/g1/mt/",
    "Gazeta Digital": "https://www.gazetadigital.com.br/rss.php",
    "Só Notícias": "https://www.sonoticias.com.br/feed/",
    "TCE-MT": "https://www.tce.mt.gov.br/rss",
    "TRT-23": "https://portal.trt23.jus.br/portal/noticias/feed",
}

log = logging.getLogger("radar")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    agora = datetime.now(CUIABA)
    cadastro = _ler_json(DADOS / "orgaos.json")
    calendario = _ler_json(DADOS / "calendario.json")

    diario, fonte_diario = _coletar_iomat(agora)
    itens, fontes_feeds = _coletar_feeds()
    fontes = [fonte_diario, *fontes_feeds]
    extras = {
        "eventos": [*diario["eventos"], *noticias.extrair_eventos(itens, cadastro, agora)],
        "cancelamentos": diario["cancelamentos"],
    }
    resultado = status.montar(calendario, extras, cadastro, agora=agora, fontes=fontes)
    try:
        status.validar(resultado, cadastro)
    except ValueError as erro:
        log.error("Status recusado, mantendo o anterior: %s", erro)
        return 1
    _gravar_atomico(DADOS / "status.json", resultado)
    log.info("status.json: %d eventos, %d/%d fontes ok", len(resultado["eventos"]),
             sum(f["ok"] for f in fontes), len(fontes))
    return 0


def _coletar_iomat(agora: datetime) -> tuple[dict, dict]:
    nome = "Diário Oficial de MT"
    inicio = (agora.date() - timedelta(days=DIAS_DE_DIARIO)).isoformat()
    hits: dict[str, dict] = {}
    try:
        for termo in TERMOS_IOMAT:
            for pagina in range(PAGINAS_POR_BUSCA):
                url = BUSCA_IOMAT.format(pagina=pagina, inicio=inicio, fim=agora.date().isoformat(),
                                         termo=urllib.parse.quote(termo))
                resultado = json.loads(_baixar(url))["hits"]["hits"]
                hits.update({h["_id"]: h for h in resultado})
                if len(resultado) < RESULTADOS_POR_PAGINA:
                    break
    except Exception as erro:  # fonte fora do ar não pode derrubar as demais
        log.warning("%s falhou: %s", nome, erro)
        return {"eventos": [], "cancelamentos": []}, _situacao(nome, erro)
    return iomat.extrair_eventos(list(hits.values()), hoje=agora.date()), _situacao(nome)


def _coletar_feeds() -> tuple[list[dict], list[dict]]:
    itens: list[dict] = []
    situacoes: list[dict] = []
    for nome, url in FEEDS.items():
        try:
            lidos = noticias.ler_rss(_baixar(url), fonte=nome)
        except Exception as erro:  # idem: um feed fora do ar não derruba os outros
            log.warning("%s falhou: %s", nome, erro)
            situacoes.append(_situacao(nome, erro))
            continue
        situacoes.append(_situacao(nome))
        itens.extend(lidos)
    return itens, situacoes


def _situacao(nome: str, erro: Exception | None = None) -> dict:
    return {"nome": nome, "ok": erro is None, "erro": type(erro).__name__ if erro else None}


def _baixar(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(pedido, timeout=TIMEOUT_SEGUNDOS) as resposta:
        return resposta.read()


def _ler_json(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _gravar_atomico(caminho: Path, conteudo: dict) -> None:
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(conteudo, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temporario.replace(caminho)


if __name__ == "__main__":
    sys.exit(main())
