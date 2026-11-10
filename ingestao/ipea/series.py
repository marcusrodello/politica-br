"""Baixa o catalogo e as series do Ipeadata e grava em Parquet.

O Ipeadata e a fonte de contexto do portal: PIB, inflacao, emprego, pobreza,
desigualdade, indicadores sociais e regionais, muitos com serie longa. Sao 4.135
series, cada uma com uma requisicao propria - nao ha download em lote.

DUAS COISAS QUE MUDAM O USO DOS NUMEROS:

1. O Ipea e um AGREGADOR, nao a fonte primaria. Cada serie traz FNTSIGLA e
   FNTURL apontando para quem produziu o dado (IBGE, Bacen, Ministerio da
   Fazenda...). O catalogo entra na base junto com as series exatamente para que
   o portal possa citar a fonte original, e nao "Ipeadata".

2. Serie regional vem com NIVNOME e TERCODIGO - o nivel territorial e o codigo
   do territorio. O codigo e o do IBGE, nao o do TSE: cruzar com eleicao exige
   a tabela municipio_tse_ibge, que a ingestao do TSE baixa.

As series sao gravadas agrupadas por tema, nao uma por arquivo: 4.135 Parquets
de poucos kilobytes custam mais para abrir do que valem, e o tema e a unidade
natural de retomada.

Uso:  python ingestao/ipea/series.py [--so TEMA] [--catalogo]
Retomavel: reexecutar pula o tema que ja tem Parquet valido.
"""
import os
import sys
import time

# ingestao/ipea/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "ipea"
API = "http://www.ipeadata.gov.br/api/odata4"
PAUSA = 0.12


def catalogo(con):
    """Metadados de todas as series: nome, fonte primaria, unidade, tema."""
    url = f"{API}/Metadados"
    destino = comum.caminho(FONTE, "catalogo", "completo.parquet")
    series = comum.pega_json(url, tempo=300)["value"]
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        comum.log(f"catalogo: ja existe ({len(series):,} series no portal)")
        return series
    import pandas as pd
    df = pd.DataFrame(series).astype("string")
    con.register("_cat", df)
    con.execute(f"COPY _cat TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_cat")
    comum.registra(con, FONTE, "catalogo", "completo.parquet", url,
                   os.path.getsize(destino), len(df), None)
    comum.log(f"catalogo: {len(df):,} series, {len(df.columns)} campos")
    return series


def valores(codigo):
    url = f"{API}/ValoresSerie(SERCODIGO='{codigo}')"
    d = comum.pega_json(url, tempo=240, aceita_404=True)
    return (d or {}).get("value") or []


def faz_tema(con, tema, series):
    nome = f"tema_{tema}"
    destino = comum.caminho(FONTE, "series", f"{nome}.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        comum.log(f"  {nome}: ja existe, pulando")
        return 0

    tudo, vazias, erros = [], 0, 0
    for i, s in enumerate(series, 1):
        cod = s["SERCODIGO"]
        try:
            pontos = valores(cod)
        except Exception as e:
            comum.log(f"    {cod}: {type(e).__name__}, seguindo")
            erros += 1
            pontos = []
        if pontos:
            tudo += pontos
        else:
            vazias += 1
        if i % 100 == 0:
            comum.log(f"    {nome}: {i}/{len(series)} series, "
                      f"{len(tudo):,} pontos")
        time.sleep(PAUSA)

    if not tudo:
        comum.log(f"  {nome}: nenhum ponto, nada a gravar")
        return 0
    import pandas as pd
    df = pd.DataFrame(tudo).astype("string")
    con.register("_lote", df)
    con.execute(f"COPY _lote TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_lote")
    obs = (f"{len(series)} series do tema; {vazias} sem ponto"
           + (f"; {erros} com erro de rede" if erros else ""))
    comum.registra(con, FONTE, "series", f"{nome}.parquet",
                   f"{API}/ValoresSerie", os.path.getsize(destino), len(df),
                   None, obs)
    comum.log(f"  {nome}: {len(series)} series -> {len(df):,} pontos "
              f"({vazias} vazias)")
    return len(df)


def main():
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]

    con = comum.abre_banco()
    series = catalogo(con)
    if "--catalogo" in sys.argv:
        con.close()
        return 0

    # agrupa por tema, do maior para o menor, para o progresso aparecer cedo
    por_tema = {}
    for s in series:
        por_tema.setdefault(str(s.get("TEMCODIGO")), []).append(s)
    temas = sorted(por_tema, key=lambda t: -len(por_tema[t]))
    comum.log(f"{len(temas)} temas, {len(series):,} series")

    falhas = 0
    for tema in temas:
        if so and so != tema:
            continue
        comum.log(f"===== tema {tema} ({len(por_tema[tema])} series) =====")
        try:
            faz_tema(con, tema, por_tema[tema])
        except Exception as e:
            comum.log(f"!! tema {tema} FALHOU: {type(e).__name__}: {e}")
            falhas += 1

    print("\n--- coletado do Ipeadata ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas
        FROM coleta WHERE fonte = 'ipea' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()
    comum.log(f"concluido. temas com falha: {falhas}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
