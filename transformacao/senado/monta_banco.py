"""Monta as tabelas do Senado Federal no schema senado.

Os Parquets vem do JSON achatado da API, com nome de coluna em CamelCase e
pontos no caminho aninhado ("IdentificacaoParlamentar.NomeParlamentar"). A
tipagem e a renomeacao acontecem aqui.

Tres coisas que a forma do dado do Senado obriga a tratar:

- A LEGISLATURA DO ARQUIVO DE SENADORES NAO ESTA DENTRO DO ARQUIVO. A ingestao
  grava um Parquet por legislatura (L57.parquet) e o numero vive no nome. Sem
  recuperar isso do caminho, as 59 legislaturas viram um amontoado em que o
  mesmo senador aparece varias vezes sem dizer de quando.

- SUBLISTAS VIRAM TEXTO JSON. Mandato tem suplentes e exercicios, legislatura
  tem sessoes legislativas; a ingestao serializa esses campos em vez de perder.
  Aqui eles ficam como vieram, com o nome terminando em _json, para quem
  precisar extrair depois saber que ali dentro ha estrutura.

- O MESMO SENADOR TEM VARIOS MANDATOS, e cada mandato tem filiacao propria. A
  tabela mandato e por mandato, nao por pessoa: contar linhas dela nao conta
  senadores.

Uso:  python transformacao/senado/monta_banco.py
"""
import glob
import os
import sys

import duckdb

# raiz do repositorio: transformacao/senado/ -> duas acima
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PQ = os.path.join(BASE, "dados", "parquet", "senado")
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")


def fonte(conjunto, com_nome_arquivo=False):
    p = os.path.join(PQ, conjunto, "*.parquet").replace("\\", "/")
    if not glob.glob(p):
        return None
    extra = ", filename=true" if com_nome_arquivo else ""
    return f"read_parquet('{p}', union_by_name=true{extra})"


# (tabela, conjunto, precisa do nome do arquivo, SQL com {f})
TABELAS = [
    ("legislatura", "legislaturas", False, """
     SELECT TRY_CAST(NumeroLegislatura AS INTEGER) AS numero,
            TRY_CAST(DataInicio AS DATE)   AS data_inicio,
            TRY_CAST(DataFim AS DATE)      AS data_fim,
            TRY_CAST(DataEleicao AS DATE)  AS data_eleicao,
            "SessoesLegislativas.SessaoLegislativa" AS sessoes_json
     FROM {f}"""),

    ("partido", "partidos", False, """
     SELECT TRY_CAST(Codigo AS INTEGER) AS codigo, Sigla AS sigla,
            Nome AS nome,
            TRY_CAST(DataCriacao AS DATE)  AS data_criacao,
            TRY_CAST(DataExtincao AS DATE) AS data_extincao
     FROM {f}"""),

    # uma linha por senador E legislatura: a legislatura vem do nome do arquivo
    ("senador_legislatura", "senadores", True, r"""
     SELECT TRY_CAST(regexp_extract(filename, 'L(\d+)\.parquet$', 1) AS INTEGER)
              AS numero_legislatura,
            TRY_CAST("IdentificacaoParlamentar.CodigoParlamentar" AS BIGINT)
              AS codigo_parlamentar,
            "IdentificacaoParlamentar.NomeParlamentar"         AS nome,
            "IdentificacaoParlamentar.NomeCompletoParlamentar" AS nome_completo,
            "IdentificacaoParlamentar.SexoParlamentar"         AS sexo,
            "IdentificacaoParlamentar.FormaTratamento"         AS tratamento,
            "IdentificacaoParlamentar.SiglaPartidoParlamentar" AS sigla_partido,
            "IdentificacaoParlamentar.UfParlamentar"           AS uf,
            "IdentificacaoParlamentar.EmailParlamentar"        AS email,
            "IdentificacaoParlamentar.UrlPaginaParlamentar"    AS url_pagina,
            "IdentificacaoParlamentar.UrlFotoParlamentar"      AS url_foto,
            "Mandatos.Mandato"                                 AS mandatos_json
     FROM {f}"""),

    # a pessoa, consolidada: o registro mais recente de cada codigo
    ("senador", None, False, """
     SELECT codigo_parlamentar, nome, nome_completo, sexo, tratamento,
            max(numero_legislatura) AS ultima_legislatura,
            min(numero_legislatura) AS primeira_legislatura,
            count(*)                AS legislaturas,
            any_value(url_pagina)   AS url_pagina,
            any_value(url_foto)     AS url_foto
     FROM senador_legislatura
     WHERE codigo_parlamentar IS NOT NULL
     GROUP BY ALL"""),

    ("mandato", "mandatos", False, """
     SELECT TRY_CAST(CodigoMandato AS BIGINT)     AS codigo_mandato,
            TRY_CAST(codigoParlamentar AS BIGINT) AS codigo_parlamentar,
            UfParlamentar AS uf,
            DescricaoParticipacao AS participacao,
            TRY_CAST("PrimeiraLegislaturaDoMandato.NumeroLegislatura" AS INTEGER)
              AS primeira_legislatura,
            TRY_CAST("SegundaLegislaturaDoMandato.NumeroLegislatura" AS INTEGER)
              AS segunda_legislatura,
            TRY_CAST("PrimeiraLegislaturaDoMandato.DataInicio" AS DATE)
              AS data_inicio,
            TRY_CAST("SegundaLegislaturaDoMandato.DataFim" AS DATE)
              AS data_fim,
            TRY_CAST("Partidos.Partido.CodigoPartido" AS INTEGER)
              AS codigo_partido,
            "Partidos.Partido.Sigla" AS sigla_partido,
            "Partidos.Partido.Nome"  AS nome_partido,
            TRY_CAST("Titular.CodigoParlamentar" AS BIGINT) AS codigo_titular,
            "Titular.NomeParlamentar" AS nome_titular,
            "Suplentes.Suplente"      AS suplentes_json,
            "Exercicios.Exercicio"    AS exercicios_json
     FROM {f}"""),
]


def mostra(con, titulo, sql):
    print(f"\n--- {titulo} ---")
    print(con.sql(sql))


def main():
    con = duckdb.connect(BANCO)
    con.execute("SET preserve_insertion_order=false")
    con.execute(f"SET temp_directory='{os.path.join(BASE, '_tmp').replace(chr(92), '/')}'")
    con.execute("CREATE SCHEMA IF NOT EXISTS senado")
    con.execute("USE senado")

    feitas, ausentes = [], []
    for tabela, conjunto, com_nome, sql in TABELAS:
        if conjunto is None:                 # derivada de outra tabela
            con.execute(f"CREATE OR REPLACE TABLE {tabela} AS {sql}")
        else:
            f = fonte(conjunto, com_nome)
            if not f:
                ausentes.append(f"{tabela} (falta {conjunto})")
                continue
            con.execute(f"CREATE OR REPLACE TABLE {tabela} AS "
                        + sql.format(f=f))
        n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        feitas.append((tabela, n))
        print(f"  {tabela:<22} {n:>10,} linhas".replace(",", "."))

    if ausentes:
        print("\nnao construidas (ingestao faltando): " + ", ".join(ausentes))

    # =================== conferencias ===================================
    mostra(con, "chave duplicada? (linhas deve igualar distintos)", """
    SELECT 'senador' AS tabela, COUNT(*) AS linhas,
           COUNT(DISTINCT codigo_parlamentar) AS distintos FROM senador
    UNION ALL SELECT 'mandato', COUNT(*), COUNT(DISTINCT codigo_mandato)
      FROM mandato
    UNION ALL SELECT 'partido', COUNT(*), COUNT(DISTINCT codigo) FROM partido
    UNION ALL SELECT 'legislatura', COUNT(*), COUNT(DISTINCT numero)
      FROM legislatura
    """)

    mostra(con, "o que a tipagem perdeu", """
    SELECT 'senador_legislatura.numero_legislatura' AS campo,
           COUNT(*) FILTER (numero_legislatura IS NULL) AS nulos,
           COUNT(*) AS total FROM senador_legislatura
    UNION ALL SELECT 'senador_legislatura.codigo_parlamentar',
           COUNT(*) FILTER (codigo_parlamentar IS NULL), COUNT(*)
      FROM senador_legislatura
    UNION ALL SELECT 'mandato.codigo_parlamentar',
           COUNT(*) FILTER (codigo_parlamentar IS NULL), COUNT(*) FROM mandato
    ORDER BY 2 DESC
    """)

    mostra(con, "mandato orfao? (mandato de senador que nao esta na base)", """
    SELECT COUNT(*) AS mandatos_sem_senador
    FROM mandato m ANTI JOIN senador s USING (codigo_parlamentar)
    """)

    mostra(con, "cobertura: senadores por legislatura, das 8 mais recentes", """
    SELECT l.numero, l.data_inicio, l.data_fim,
           COUNT(DISTINCT sl.codigo_parlamentar) AS senadores
    FROM legislatura l
    LEFT JOIN senador_legislatura sl ON sl.numero_legislatura = l.numero
    GROUP BY ALL ORDER BY 1 DESC LIMIT 8
    """)

    con.close()
    print(f"\n{len(feitas)} tabelas no schema senado: "
          + ", ".join(t for t, _ in feitas))
    print(f"banco: {BANCO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
