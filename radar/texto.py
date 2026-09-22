"""Utilitários de texto em pt-BR: normalização e datas por extenso."""

import re
import unicodedata
from datetime import date

MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços colapsados — base de toda comparação."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def montar_data(dia: int, mes_extenso: str, ano: int | None, referencia: date) -> date | None:
    """Constrói a data; sem ano explícito, assume o ano da referência (ou o seguinte, se já passou há mais de 7 dias)."""
    mes = MESES.get(normalizar(mes_extenso))
    if mes is None:
        return None
    ano_final = ano if ano is not None else referencia.year
    try:
        resultado = date(ano_final, mes, dia)
    except ValueError:
        return None
    if ano is None and (referencia - resultado).days > 7:
        resultado = resultado.replace(year=ano_final + 1)
    return resultado
