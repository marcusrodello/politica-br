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

E uma sobre votacao que inverte o que o nome sugere, descoberta ao conferir o
placar contra os votos:

- VOTACAO ABERTA NAO TRAZ O TOTAL; VOTACAO SECRETA NAO TRAZ O VOTO. Nas 1.772
  votacoes com votacaoSecreta = 'N', os campos de total vem VAZIOS e o placar
  tem de ser contado dos votos individuais, que sao nominais. Nas 1.838 com
  'S', o total vem preenchido e cada voto individual aparece como 'Votou' - o
  voto existe, mas nao e revelado. Quem somar os dois conjuntos sem separar
  produz placar errado nos dois sentidos.

- A CHAVE DA VOTACAO E codigoSessaoVotacao SOZINHO. O campo sequencialVotacao
  parece compor a chave mas e nulo em 2.719 das 3.626 votacoes e em 214 mil dos
  287 mil votos; usa-lo numa juncao descarta a maior parte das linhas em
  silencio, porque NULL nao casa com NULL.

Uso:  python transformacao/senado/monta_banco.py
"""
import glob
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
import banco                                                  # noqa: E402

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

    ("filiacao", "filiacoes", False, """
     SELECT TRY_CAST(codigoParlamentar AS BIGINT) AS codigo_parlamentar,
            TRY_CAST("Partido.CodigoPartido" AS INTEGER) AS codigo_partido,
            "Partido.SiglaPartido" AS sigla_partido,
            "Partido.NomePartido"  AS nome_partido,
            TRY_CAST(DataFiliacao AS DATE)   AS data_filiacao,
            TRY_CAST(DataDesfiliacao AS DATE) AS data_desfiliacao,
            TRY_CAST(AnoFiliacao AS INTEGER)    AS ano_filiacao,
            TRY_CAST(AnoDesfiliacao AS INTEGER) AS ano_desfiliacao
     FROM {f}"""),

    ("colegiado", "colegiados", False, """
     SELECT TRY_CAST(Codigo AS INTEGER) AS codigo, Sigla AS sigla,
            Nome AS nome, SiglaCasa AS casa,
            SiglaTipoColegiado AS sigla_tipo,
            DescricaoTipoColegiado AS tipo,
            TRY_CAST(CodigoTipoColegiado AS INTEGER) AS codigo_tipo,
            TRY_CAST(DataInicio AS DATE) AS data_inicio,
            Publica AS publica, Finalidade AS finalidade
     FROM {f}"""),

    ("votacao", "votacoes", False, """
     SELECT TRY_CAST(codigoSessaoVotacao AS BIGINT) AS codigo_votacao,
            TRY_CAST(sequencialVotacao AS INTEGER)  AS sequencial,
            TRY_CAST(codigoSessao AS BIGINT)        AS codigo_sessao,
            TRY_CAST(dataSessao AS DATE)            AS data_sessao,
            casaSessao AS casa, siglaTipoSessao AS tipo_sessao,
            TRY_CAST(numeroSessao AS INTEGER)       AS numero_sessao,
            identificacao AS materia, sigla AS sigla_materia,
            TRY_CAST(numero AS INTEGER)             AS numero_materia,
            TRY_CAST(ano AS INTEGER)                AS ano_materia,
            TRY_CAST(codigoMateria AS BIGINT)       AS codigo_materia,
            TRY_CAST(idProcesso AS BIGINT)          AS id_processo,
            descricaoVotacao AS descricao, ementa,
            resultadoVotacao AS resultado,
            votacaoSecreta AS secreta,
            TRY_CAST(totalVotosSim AS INTEGER)       AS votos_sim,
            TRY_CAST(totalVotosNao AS INTEGER)       AS votos_nao,
            TRY_CAST(totalVotosAbstencao AS INTEGER) AS votos_abstencao,
            "informeLegislativo.siglaColegiado" AS colegiado
     FROM {f}"""),

    ("voto", "votos", False, """
     SELECT TRY_CAST(codigoSessaoVotacao AS BIGINT) AS codigo_votacao,
            TRY_CAST(sequencialVotacao AS INTEGER)  AS sequencial,
            TRY_CAST(codigoParlamentar AS BIGINT)   AS codigo_parlamentar,
            nomeParlamentar AS nome, sexoParlamentar AS sexo,
            siglaPartidoParlamentar AS sigla_partido,
            siglaUFParlamentar AS uf,
            siglaVotoParlamentar AS voto,
            descricaoVotoParlamentar AS voto_descricao,
            TRY_CAST(dataSessao AS DATE) AS data_sessao,
            identificacao AS materia
     FROM {f}"""),

    ("processo", "processos", False, """
     SELECT TRY_CAST(id AS BIGINT) AS id_processo,
            TRY_CAST(codigoMateria AS BIGINT) AS codigo_materia,
            identificacao AS identificacao, apelido,
            tipoDocumento AS tipo_documento,
            tipoConteudo AS tipo_conteudo,
            casaIdentificadora AS casa, enteIdentificador AS ente,
            autoria, ementa, objetivo,
            situacaoAtual AS situacao,
            TRY_CAST(tramitando AS BOOLEAN) AS tramitando,
            normaGerada AS norma_gerada,
            TRY_CAST(dataApresentacao AS DATE)     AS apresentado_em,
            TRY_CAST(dataSituacaoAtual AS DATE)    AS situacao_em,
            TRY_CAST(dataDeliberacao AS DATE)      AS deliberado_em,
            siglaTipoDeliberacao AS tipo_deliberacao,
            TRY_CAST(dataUltimaAtualizacao AS TIMESTAMP) AS atualizado_em,
            urlDocumento AS url_documento
     FROM {f}"""),

    ("norma", "normas", False, """
     SELECT TRY_CAST(id AS BIGINT) AS id_norma,
            tipo, descricao AS tipo_descricao,
            norma, normaNome AS norma_nome, apelido,
            TRY_CAST(numero AS VARCHAR) AS numero,
            identificacaoLetra AS letra, complemento,
            TRY_CAST(reedicao AS INTEGER)   AS reedicao,
            TRY_CAST(sequencia AS INTEGER)  AS sequencia,
            ementa,
            TRY_CAST(dataassinatura AS DATE)  AS assinada_em,
            TRY_CAST(anoassinatura AS INTEGER) AS ano_assinatura
     FROM {f}"""),
]


def mostra(con, titulo, sql):
    print(f"\n--- {titulo} ---")
    print(con.sql(sql))


def main():
    con = banco.abre(schema="senado")

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
        # fetchall, nao fetchone: fetchone deixa o cursor aberto e a consulta
        # seguinte falha com "connection has an unfinished result"
        n = con.sql(f"SELECT COUNT(*) FROM {tabela}").fetchall()[0][0]
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

    # a juncao e por codigo_votacao SOZINHO: sequencial e nulo na maioria das
    # linhas, e NULL nao casa com NULL - incluir na chave descarta 3 de cada 4
    # votacoes sem avisar
    mostra(con, "placar e voto: aberta traz um, secreta traz o outro", """
    WITH c AS (
      SELECT codigo_votacao,
             COUNT(*) FILTER (voto = 'Sim')       AS sim,
             COUNT(*) FILTER (voto = 'Não')       AS nao,
             COUNT(*) FILTER (voto = 'Abstenção') AS abstencao,
             COUNT(*) FILTER (voto = 'Votou')     AS votou,
             COUNT(*)                             AS registros
      FROM voto GROUP BY 1)
    SELECT CASE v.secreta WHEN 'S' THEN 'secreta' ELSE 'aberta' END AS tipo,
           COUNT(*) AS votacoes,
           COUNT(*) FILTER (v.votos_sim IS NULL)  AS sem_placar_declarado,
           SUM(c.sim + c.nao + c.abstencao)       AS votos_nominais,
           SUM(c.votou)                           AS votos_ocultos,
           COUNT(*) FILTER (v.votos_sim IS NOT NULL
                            AND c.sim = v.votos_sim
                            AND c.nao = v.votos_nao)  AS placar_bate
    FROM c JOIN votacao v USING (codigo_votacao)
    GROUP BY 1
    """)

    mostra(con, "na secreta, o total declarado bate com quantos votaram?", """
    WITH c AS (SELECT codigo_votacao, COUNT(*) FILTER (voto = 'Votou') AS votou
               FROM voto GROUP BY 1)
    SELECT COUNT(*) AS votacoes_secretas,
           COUNT(*) FILTER (c.votou = coalesce(v.votos_sim, 0)
                                    + coalesce(v.votos_nao, 0)
                                    + coalesce(v.votos_abstencao, 0))
             AS total_bate,
           COUNT(*) FILTER (c.votou <> coalesce(v.votos_sim, 0)
                                     + coalesce(v.votos_nao, 0)
                                     + coalesce(v.votos_abstencao, 0))
             AS total_divergente
    FROM c JOIN votacao v USING (codigo_votacao) WHERE v.secreta = 'S'
    """)

    mostra(con, "cobertura por ano", """
    SELECT 'votacao' AS tabela, MIN(year(data_sessao)) AS de,
           MAX(year(data_sessao)) AS ate, COUNT(*) AS linhas
      FROM votacao WHERE data_sessao IS NOT NULL
    UNION ALL SELECT 'voto', MIN(year(data_sessao)), MAX(year(data_sessao)),
           COUNT(*) FROM voto WHERE data_sessao IS NOT NULL
    UNION ALL SELECT 'processo', MIN(year(apresentado_em)),
           MAX(year(apresentado_em)), COUNT(*) FROM processo
      WHERE apresentado_em IS NOT NULL
    UNION ALL SELECT 'norma', MIN(ano_assinatura), MAX(ano_assinatura),
           COUNT(*) FROM norma WHERE ano_assinatura IS NOT NULL
    UNION ALL SELECT 'filiacao', MIN(ano_filiacao), MAX(ano_filiacao),
           COUNT(*) FROM filiacao WHERE ano_filiacao IS NOT NULL
    ORDER BY 2
    """)

    mostra(con, "troca de partido: senadores com mais de uma filiacao", """
    SELECT COUNT(*) AS senadores_com_filiacao,
           COUNT(*) FILTER (filiacoes > 1) AS trocaram_de_partido,
           MAX(filiacoes) AS maior_numero_de_filiacoes
    FROM (SELECT codigo_parlamentar, COUNT(*) AS filiacoes
          FROM filiacao GROUP BY 1)
    """)

    con.close()
    print(f"\n{len(feitas)} tabelas no schema senado: "
          + ", ".join(t for t, _ in feitas))
    print(f"banco: {BANCO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
