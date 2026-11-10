"""Baixa localidades e agregados do SIDRA/IBGE e grava em Parquet.

Tres coisas entram daqui:

  localidades   UFs, mesorregioes, microrregioes e os 5.570 municipios com o
                codigo oficial do IBGE. E a tabela de referencia geografica do
                portal: o codigo do IBGE e o que o Ipea, o Tesouro e o Banco
                Central usam. O TSE usa outro, e a ponte entre os dois vem de
                municipio_tse_ibge, na ingestao do TSE.

  catalogo      todos os agregados do SIDRA, com suas variaveis e niveis
                territoriais. Serve para descobrir que tabela responde a uma
                pergunta sem adivinhar numero de agregado.

  series        os agregados listados em ESCOLHIDOS, com toda a serie historica
                disponivel, no nivel territorial declarado.

POR QUE UMA LISTA EXPLICITA DE AGREGADOS, e nao tudo: o SIDRA tem mais de mil
agregados, e muitos sao recortes de pesquisa que nao dizem nada sobre governo
ou politica. A lista abaixo e a parte que o portal usa para dar contexto a
comparacao de governos - producto, populacao, trabalho, preco - e cada entrada
diz por que esta ali. Ampliar e so acrescentar uma linha.

Uso:  python ingestao/ibge/agregados.py [--so CONJUNTO] [--catalogo]
Retomavel: reexecutar pula o que ja tem Parquet valido.
"""
import os
import sys
import time

# ingestao/ibge/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "ibge"
API = "https://servicodados.ibge.gov.br/api"
PAUSA = 0.2

# nivel territorial na API: N1 Brasil, N3 UF, N6 municipio
# (agregado, nome local, nivel, por que entra)
ESCOLHIDOS = [
    (5938, "pib_municipios", "N6",
     "PIB municipal a preco corrente - a medida de produto mais fina que o "
     "IBGE publica por municipio"),
    (6579, "populacao_estimada", "N6",
     "populacao residente estimada por municipio, usada como denominador de "
     "quase todo indicador per capita"),
    (4709, "populacao_censo", "N6",
     "populacao do Censo, a contagem de verdade - a estimada e projecao"),
    (1737, "ipca_serie", "N1",
     "IPCA mensal, o indice que corrige valor de uma eleicao para outra"),
    (6784, "pnad_desocupacao", "N3",
     "taxa de desocupacao por UF, da PNAD Continua trimestral"),
    (7060, "ipca_grupo", "N1",
     "IPCA por grupo de produto, para separar inflacao de alimento da geral"),
]


def localidades(con):
    for nivel, nome in (("municipios", "municipios"), ("estados", "estados"),
                        ("mesorregioes", "mesorregioes"),
                        ("microrregioes", "microrregioes")):
        destino = comum.caminho(FONTE, "localidades", f"{nome}.parquet")
        if os.path.exists(destino) and comum.parquet_valido(con, destino):
            comum.log(f"  localidades/{nome}: ja existe, pulando")
            continue
        url = f"{API}/v1/localidades/{nivel}"
        dados = comum.pega_json(url, tempo=240)
        import pandas as pd
        df = pd.json_normalize(dados, sep=".").astype("string")
        con.register("_loc", df)
        con.execute(f"COPY _loc TO '{comum.sql(destino)}' "
                    f"(FORMAT PARQUET, COMPRESSION ZSTD)")
        con.unregister("_loc")
        comum.registra(con, FONTE, "localidades", f"{nome}.parquet", url,
                       os.path.getsize(destino), len(df), None)
        comum.log(f"  localidades/{nome}: {len(df):,} registros")


def catalogo(con):
    destino = comum.caminho(FONTE, "catalogo", "agregados.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        comum.log("  catalogo: ja existe, pulando")
        return
    url = f"{API}/v3/agregados"
    pesquisas = comum.pega_json(url, tempo=240)
    linhas = []
    for p in pesquisas:
        for a in p.get("agregados", []):
            linhas.append({"pesquisa_id": p.get("id"),
                           "pesquisa": p.get("nome"),
                           "agregado_id": a.get("id"),
                           "agregado": a.get("nome")})
    import pandas as pd
    df = pd.DataFrame(linhas).astype("string")
    con.register("_cat", df)
    con.execute(f"COPY _cat TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_cat")
    comum.registra(con, FONTE, "catalogo", "agregados.parquet", url,
                   os.path.getsize(destino), len(df), None)
    comum.log(f"  catalogo: {len(df):,} agregados em {len(pesquisas)} pesquisas")


def metadados(agregado):
    return comum.pega_json(f"{API}/v3/agregados/{agregado}/metadados",
                           tempo=180, aceita_404=True)


def serie(con, agregado, nome, nivel, motivo):
    """Baixa a serie de um agregado, por periodo, no nivel territorial dado.

    A API recusa pedir todos os periodos de todos os municipios de uma vez nos
    agregados grandes, entao a carga vai periodo a periodo e junta no fim.
    """
    destino = comum.caminho(FONTE, "series", f"{nome}.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        comum.log(f"  {nome}: ja existe, pulando")
        return

    meta = metadados(agregado)
    if not meta:
        comum.log(f"  {nome}: agregado {agregado} nao existe mais, pulando")
        return
    variaveis = [str(v["id"]) for v in meta.get("variaveis", [])]
    # os periodos disponiveis vem num endpoint proprio, nao nos metadados
    lista = comum.pega_json(f"{API}/v3/agregados/{agregado}/periodos",
                            tempo=180, aceita_404=True) or []
    anos = [str(p["id"]) for p in lista] if lista else []
    if not anos:
        comum.log(f"  {nome}: sem periodos listados, pulando")
        return

    var = ",".join(variaveis[:4]) or "all"
    tudo = []
    for p in anos:
        url = (f"{API}/v3/agregados/{agregado}/periodos/{p}/variaveis/{var}"
               f"?localidades={nivel}[all]")
        try:
            d = comum.pega_json(url, tempo=300, aceita_404=True) or []
        except Exception as e:
            comum.log(f"    {nome} {p}: {type(e).__name__}, seguindo")
            continue
        for v in d:
            for r in v.get("resultados", []):
                classif = " | ".join(
                    f"{c['nome']}={list(c['categoria'].values())[0]}"
                    for c in r.get("classificacoes", []))
                for s in r.get("series", []):
                    loc = s.get("localidade", {})
                    for periodo, valor in (s.get("serie") or {}).items():
                        tudo.append({
                            "agregado": str(agregado),
                            "variavel_id": str(v.get("id")),
                            "variavel": v.get("variavel"),
                            "unidade": v.get("unidade"),
                            "classificacao": classif,
                            "nivel": loc.get("nivel", {}).get("id"),
                            "localidade_id": loc.get("id"),
                            "localidade": loc.get("nome"),
                            "periodo": periodo,
                            "valor": valor})
        time.sleep(PAUSA)

    if not tudo:
        comum.log(f"  {nome}: nenhum valor retornado")
        return
    import pandas as pd
    df = pd.DataFrame(tudo).astype("string")
    con.register("_lote", df)
    con.execute(f"COPY _lote TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_lote")
    comum.registra(con, FONTE, "series", f"{nome}.parquet",
                   f"{API}/v3/agregados/{agregado}", os.path.getsize(destino),
                   len(df), None, f"{motivo}; {len(anos)} periodos, "
                   f"nivel {nivel}")
    comum.log(f"  {nome}: {len(anos)} periodos -> {len(df):,} valores")


def main():
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]

    con = comum.abre_banco()
    if not so or so == "localidades":
        comum.log("===== localidades =====")
        localidades(con)
    if not so or so == "catalogo":
        comum.log("===== catalogo de agregados =====")
        catalogo(con)
    if "--catalogo" in sys.argv:
        con.close()
        return 0

    falhas = []
    for agregado, nome, nivel, motivo in ESCOLHIDOS:
        if so and so != nome:
            continue
        comum.log(f"===== {nome} (agregado {agregado}) =====")
        try:
            serie(con, agregado, nome, nivel, motivo)
        except Exception as e:
            comum.log(f"!! {nome} FALHOU: {type(e).__name__}: {e}")
            falhas.append(nome)

    print("\n--- coletado do IBGE ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas
        FROM main.coleta WHERE fonte = 'ibge' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()
    comum.log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
