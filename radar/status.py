"""Junta calendário anual + eventos coletados no `status.json` que a página lê."""

import hashlib
import json
from datetime import date, datetime, timedelta

VERSAO = 1
NIVEIS = {"vermelho", "ambar", "verde"}
TITULO_MAXIMO = 300
DIAS_EXIBIDOS = 5
HORIZONTE = timedelta(days=60)
SABADO = 5


def montar(calendario: list[dict], extras: dict, cadastro: dict, agora: datetime, fontes: list[dict]) -> dict:
    hoje = agora.date()
    cancelados = {(c["data"], _chave_alvo(c["alvo"])) for c in extras["cancelamentos"]}
    vigentes = [e for e in calendario if (e["data"], _chave_alvo(e["alvo"])) not in cancelados]
    unicos: dict[str, dict] = {}
    for bruto in [*vigentes, *extras["eventos"]]:
        if hoje <= date.fromisoformat(bruto["data"]) <= hoje + HORIZONTE:
            expandido = _expandir(bruto, cadastro)
            unicos.setdefault(expandido["id"], expandido)
    return {
        "versao": VERSAO,
        "gerado_em": agora.isoformat(timespec="minutes"),
        "hoje": hoje.isoformat(),
        "dias": [d.isoformat() for d in _dias_uteis(hoje, DIAS_EXIBIDOS)],
        "eventos": sorted(unicos.values(), key=lambda e: (e["data"], e["id"])),
        "fontes": fontes,
    }


def validar(status: dict, cadastro: dict) -> None:
    """Barra qualquer status que quebraria a página ou violaria a regra de confiança (Q12)."""
    erros = []
    if status.get("versao") != VERSAO:
        erros.append("versao desconhecida")
    if len(status.get("dias", [])) != DIAS_EXIBIDOS or not all(_e_data(d) for d in status["dias"]):
        erros.append("dias invalidos")
    ids_validos = {o["id"] for o in cadastro["orgaos"]}
    for evento in status.get("eventos", []):
        erros.extend(f"{evento.get('id', '?')}: {erro}" for erro in _erros_do_evento(evento, ids_validos))
    if erros:
        raise ValueError("status.json invalido: " + "; ".join(erros))


def _erros_do_evento(evento: dict, ids_validos: set[str]):
    if not _e_data(evento.get("data")):
        yield "data invalida"
    if evento.get("nivel") not in NIVEIS:
        yield "nivel invalido"
    desconhecidos = set(evento.get("orgaos") or ["(vazio)"]) - ids_validos
    if desconhecidos:
        yield f"orgaos desconhecidos {sorted(desconhecidos)}"
    fonte = evento.get("fonte") or {}
    if not str(fonte.get("url", "")).startswith("https://"):
        yield "fonte.url precisa ser https"
    if evento.get("nivel") == "vermelho" and fonte.get("oficial") is not True:
        yield "vermelho exige fonte oficial"
    if not isinstance(evento.get("titulo"), str) or not 0 < len(evento["titulo"]) <= TITULO_MAXIMO:
        yield "titulo invalido"


def _e_data(valor) -> bool:
    try:
        date.fromisoformat(valor)
    except (TypeError, ValueError):
        return False
    return True


def _chave_alvo(alvo: dict) -> str:
    return json.dumps(alvo, sort_keys=True)


def _dias_uteis(inicio: date, quantidade: int) -> list[date]:
    dias, dia = [], inicio
    while len(dias) < quantidade:
        if dia.weekday() < SABADO:
            dias.append(dia)
        dia += timedelta(days=1)
    return dias


def _expandir(evento: dict, cadastro: dict) -> dict:
    orgaos = _orgaos_do_alvo(evento["alvo"], cadastro)
    assinatura = json.dumps([evento["data"], sorted(orgaos), evento["nivel"], evento["fonte"]["url"], evento["titulo"]])
    return {
        "id": hashlib.sha1(assinatura.encode()).hexdigest()[:12],
        **{k: v for k, v in evento.items() if k != "alvo"},
        "orgaos": orgaos,
    }


def _orgaos_do_alvo(alvo: dict, cadastro: dict) -> list[str]:
    if alvo.get("todos"):
        return [o["id"] for o in cadastro["orgaos"]]
    if "orgaos" in alvo:
        return list(alvo["orgaos"])
    return [o["id"] for o in cadastro["orgaos"] if o["calendario"] == alvo.get("calendario")]
