"""Baixa series do Sistema Gerenciador de Series Temporais (SGS) do Banco Central.

O que o portal usa daqui: o contexto economico contra o qual um governo e
julgado - inflacao, juro, cambio, atividade, credito, divida publica, confianca.

POR QUE UMA LISTA EXPLICITA DE SERIES: o SGS tem mais de vinte mil series e nao
publica catalogo consultavel por API - o que existe e uma interface de busca
web. Varrer o espaco de codigos seria chute. Cada entrada abaixo diz o que e e
por que entra; ampliar e acrescentar uma linha.

O SGS recusa janelas muito longas em serie diaria: a carga pede em blocos de 10
anos e junta. Serie que nunca existiu devolve 404 e e anotada como ausente, em
vez de derrubar a ingestao.

Uso:  python ingestao/bcb/series.py [--so NOME]
Retomavel: reexecutar pula o que ja tem Parquet valido.
"""
import datetime
import os
import sys
import time

# ingestao/bcb/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "bcb"
API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"
PAUSA = 0.2
INICIO = 1980          # antes disso quase nada existe no SGS
BLOCO = 10             # anos por requisicao

# (codigo SGS, nome local, o que e)
SERIES = [
    (433, "ipca_mensal", "IPCA, variacao mensal - o indice oficial de inflacao"),
    (13522, "ipca_12m", "IPCA acumulado em 12 meses"),
    (432, "selic_meta", "meta da taxa Selic definida pelo Copom"),
    (11, "selic_diaria", "Selic efetiva, ao dia"),
    (1, "cambio_dolar", "dolar comercial, venda, ao dia"),
    (24363, "ibc_br", "IBC-Br, o indicador mensal de atividade economica"),
    (24369, "pib_mensal_acum", "PIB acumulado em 12 meses, em valor corrente"),
    (4189, "selic_anual", "Selic acumulada no ano"),
    (13621, "divida_liquida_pib", "divida liquida do setor publico, em % do PIB"),
    (4513, "divida_bruta_pib", "divida bruta do governo geral, em % do PIB"),
    (20539, "credito_pib", "saldo de credito do sistema financeiro, em % do PIB"),
    (24364, "expectativa_ipca", "expectativa de IPCA do boletim Focus"),
    (28763, "desemprego_pnad", "taxa de desocupacao da PNAD Continua"),
    (1207, "salario_minimo", "salario minimo nominal"),
    (7832, "pib_anual_corrente", "PIB anual a preco corrente"),
]


def pega_bloco(cod, ini, fim):
    url = (API.format(cod=cod) +
           f"?formato=json&dataInicial=01/01/{ini}&dataFinal=31/12/{fim}")
    try:
        return comum.pega_json(url, tempo=180, aceita_404=True) or [], url
    except Exception as e:
        comum.log(f"    {cod} {ini}-{fim}: {type(e).__name__}, seguindo")
        return [], url


def faz_serie(con, cod, nome, descricao):
    destino = comum.caminho(FONTE, "series", f"{nome}.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        comum.log(f"  {nome}: ja existe, pulando")
        return

    hoje = datetime.date.today().year
    tudo, url_ref = [], None
    for ini in range(INICIO, hoje + 1, BLOCO):
        fim = min(ini + BLOCO - 1, hoje)
        pontos, url_ref = pega_bloco(cod, ini, fim)
        for p in pontos:
            tudo.append({"codigo_sgs": str(cod), "serie": nome,
                         "data": p.get("data"), "valor": p.get("valor")})
        time.sleep(PAUSA)

    if not tudo:
        comum.log(f"  {nome}: serie {cod} sem dado no periodo, nada a gravar")
        return
    import pandas as pd
    df = pd.DataFrame(tudo).drop_duplicates().astype("string")
    con.register("_lote", df)
    con.execute(f"COPY _lote TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_lote")
    comum.registra(con, FONTE, "series", f"{nome}.parquet", url_ref,
                   os.path.getsize(destino), len(df), None, descricao)
    comum.log(f"  {nome}: {len(df):,} pontos, de {df['data'].min()} "
              f"a {df['data'].max()}")


def main():
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]

    con = comum.abre_banco()
    falhas = []
    for cod, nome, descricao in SERIES:
        if so and so != nome:
            continue
        comum.log(f"===== {nome} (SGS {cod}) =====")
        try:
            faz_serie(con, cod, nome, descricao)
        except Exception as e:
            comum.log(f"!! {nome} FALHOU: {type(e).__name__}: {e}")
            falhas.append(nome)

    print("\n--- coletado do Banco Central ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas
        FROM main.coleta WHERE fonte = 'bcb' GROUP BY 1
    """))
    con.close()
    comum.log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
