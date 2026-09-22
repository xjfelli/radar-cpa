# Radar CPA · Restaurantes

Previsão dos dias de almoço fraco no Centro Político Administrativo de Cuiabá: um mapa com os ~33 órgãos
ao redor, cada um com um pin que pulsa quando há ponto facultativo, recesso ou dispensa no dia.

- ⚪ sem alertas · 🟢 movimento extra · 🟠 possível ou parcial · 🔴 dispensa confirmada no horário do almoço
- **Vermelho só com fonte oficial** (Diário Oficial de MT, portarias, leis). Notícia de imprensa nunca passa de âmbar.
- Índice do dia: órgãos em vermelho + metade dos em âmbar, ponderados por porte (G=3, M=2, P=1).
  Abaixo de 15% é normal, de 15% a 40% é atenção, acima de 40% é movimento fraco.

## Como funciona

```
GitHub Actions (7× por dia) ──► radar/coletar.py
   ├─ dados/calendario.json   calendário anual oficial de 2026
   ├─ radar/iomat.py          decretos no Diário Oficial de MT (busca JSON)
   └─ radar/noticias.py       RSS: Google Notícias, g1 MT, Gazeta Digital, Só Notícias, TCE-MT, TRT-23
        ▼
   radar/status.py  monta + valida ──► dados/status.json ──► GitHub Pages (index.html)
```

Se a validação falhar, o `status.json` anterior é mantido. A página avisa quando os dados têm mais de 14h.

## Desenvolvimento

Sem dependências: Python 3.12+ e Node 22+.

```bash
python3 -m unittest discover -s tests -t .   # leitores e montagem do status
node --test tests/*.test.mjs                 # regras da página
python3 -m radar.coletar                     # coleta real → dados/status.json
python3 -m http.server                       # abrir http://localhost:8000
```

No macOS com o Python do python.org, use `SSL_CERT_FILE=/etc/ssl/cert.pem` para a coleta.

## Manutenção anual

Em dezembro, quando saírem os decretos e portarias de 2027, acrescente as datas em `dados/calendario.json`.
Órgãos, coordenadas, porte e apelidos usados para casar notícias ficam em `dados/orgaos.json`.

Mapa: © [OpenStreetMap](https://www.openstreetmap.org/copyright), tiles [OpenFreeMap](https://openfreemap.org).
