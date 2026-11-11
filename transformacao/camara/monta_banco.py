"""Monta as tabelas da Camara dos Deputados no schema camara.

Os Parquets da ingestao sao texto puro - all_varchar na carga, de proposito,
porque campo que muda de formato no meio da serie derruba a leitura inteira. A
tipagem acontece aqui, com TRY_CAST, e o que nao converte vira NULL em vez de
abortar. Isso esconderia estrago silencioso, entao o script CONTA o que se
perdeu em cada conversao de chave e data, e imprime no fim.

Duas coisas que a estrutura da Camara obriga a tratar:

- O ARQUIVO DE DEPUTADOS NAO TEM COLUNA DE ID. A identidade do deputado vive no
  fim da URI (.../deputados/204382), e e por ela que votos, autoria e frentes
  se amarram. O id sai da URI por expressao regular, aqui e em toda tabela que
  referencia deputado.

- O VOTO NOMINAL COMECA EM 2001, as votacoes em 1988. Juntar as duas sem olhar
  a cobertura produz a conclusao falsa de que o Congresso nao votava nominal
  antes de 2001 - votava, e o registro aberto e que nao existe. A conferencia
  no fim mostra a cobertura de cada tabela por ano.

E duas descobertas das conferencias, que mudam o que se pode fazer com o dado:

- O CPF DO DEPUTADO VEM VAZIO. A coluna existe no arquivo da Camara e esta
  preenchida em ZERO das 7.890 linhas. Isso tira do caminho a chave obvia para
  amarrar a mesma pessoa entre Camara, Senado e TSE: a identidade vai ter de
  sair de nome, data de nascimento e UF, que e justamente o problema difícil
  do projeto. Melhor saber agora do que depois de construir em cima.

- ano = 0 EM 390.899 PROPOSICOES, 39% do total. Nao e erro de conversao: sao
  pareceres (PAR), substitutivos (SBT) e afins, que nao tem ano proprio, e a
  Camara grava zero. Zero como ano envenena qualquer agregacao por tempo - um
  MIN(ano) ingenuo devolve o ano zero -, entao a carga converte para NULL, que
  e o que "nao tem ano" quer dizer. O valor cru segue no Parquet.

Uso:  python transformacao/camara/monta_banco.py
"""
import glob
import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
import banco                                                  # noqa: E402

# raiz do repositorio: transformacao/camara/ -> duas acima
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PQ = os.path.join(BASE, "dados", "parquet", "camara")
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")

ID_URI = r"regexp_extract({c}, '(\d+)/?$', 1)"


def fonte(conjunto):
    """Glob dos Parquets de um conjunto, no formato que o DuckDB aceita."""
    p = os.path.join(PQ, conjunto, "*.parquet").replace("\\", "/")
    if not glob.glob(p):
        return None
    # union_by_name porque a Camara acrescenta coluna nova em ano novo e os
    # arquivos antigos seguem sem ela
    return f"read_parquet('{p}', union_by_name=true)"


# (tabela, conjunto de origem, SQL) - o SQL recebe {f} = a leitura do Parquet
TABELAS = [
    ("legislatura", "legislaturas", """
     SELECT TRY_CAST(idLegislatura AS INTEGER) AS id_legislatura,
            TRY_CAST(dataInicio AS DATE)       AS data_inicio,
            TRY_CAST(dataFim AS DATE)          AS data_fim,
            TRY_CAST(anoEleicao AS INTEGER)    AS ano_eleicao
     FROM {f}"""),

    ("partido", "partidos", """
     SELECT TRY_CAST(id AS INTEGER) AS id_partido, sigla, nome
     FROM {f}"""),

    ("deputado", "deputados", f"""
     SELECT TRY_CAST({ID_URI.format(c='uri')} AS BIGINT) AS id_deputado,
            nome, nomeCivil AS nome_civil, cpf, siglaSexo AS sexo,
            TRY_CAST(dataNascimento AS DATE)   AS data_nascimento,
            TRY_CAST(dataFalecimento AS DATE)  AS data_falecimento,
            ufNascimento AS uf_nascimento,
            municipioNascimento AS municipio_nascimento,
            TRY_CAST(idLegislaturaInicial AS INTEGER) AS legislatura_inicial,
            TRY_CAST(idLegislaturaFinal AS INTEGER)   AS legislatura_final,
            urlWebsite AS url_site, urlRedeSocial AS url_rede_social
     FROM {{f}}"""),

    ("ocupacao", "deputadosOcupacoes", """
     SELECT TRY_CAST(id AS BIGINT) AS id_deputado,
            titulo, entidade, entidadeUF AS entidade_uf,
            entidadePais AS entidade_pais,
            TRY_CAST(anoInicio AS INTEGER) AS ano_inicio,
            TRY_CAST(anoFim AS INTEGER)    AS ano_fim
     FROM {f}"""),

    ("profissao", "deputadosProfissoes", """
     SELECT TRY_CAST(id AS BIGINT) AS id_deputado, titulo,
            TRY_CAST(codTipoProfissao AS INTEGER) AS cod_tipo,
            TRY_CAST(dataHora AS TIMESTAMP) AS registrado_em
     FROM {f}"""),

    ("orgao", "orgaos", f"""
     SELECT TRY_CAST({ID_URI.format(c='uri')} AS BIGINT) AS id_orgao,
            sigla, nome, apelido, tipoOrgao AS tipo,
            TRY_CAST(codTipoOrgao AS INTEGER) AS cod_tipo,
            descricaoSituacao AS situacao, casa,
            TRY_CAST(dataInicio AS DATE)      AS data_inicio,
            TRY_CAST(dataInstalacao AS DATE)  AS data_instalacao,
            TRY_CAST(dataFim AS DATE)         AS data_fim
     FROM {{f}}"""),

    ("orgao_deputado", "orgaosDeputados", f"""
     SELECT TRY_CAST({ID_URI.format(c='uriOrgao')} AS BIGINT)    AS id_orgao,
            siglaOrgao AS sigla_orgao, nomeOrgao AS nome_orgao,
            TRY_CAST({ID_URI.format(c='uriDeputado')} AS BIGINT) AS id_deputado,
            nomeDeputado AS nome_deputado,
            siglaPartido AS sigla_partido, siglaUF AS uf, cargo,
            TRY_CAST(dataInicio AS DATE) AS data_inicio,
            TRY_CAST(dataFim AS DATE)    AS data_fim
     FROM {{f}}"""),

    ("frente", "frentes", """
     SELECT TRY_CAST(id AS BIGINT) AS id_frente, titulo,
            TRY_CAST(dataCriacao AS DATE) AS data_criacao,
            TRY_CAST(idLegislatura AS INTEGER) AS id_legislatura,
            situacao, keywords AS palavras_chave,
            TRY_CAST(coordenador_id AS BIGINT) AS id_coordenador,
            coordenador_nome AS nome_coordenador,
            coordenador_siglaPartido AS partido_coordenador,
            coordenador_siglaUf AS uf_coordenador
     FROM {f}"""),

    ("frente_deputado", "frentesDeputados", """
     SELECT TRY_CAST(id AS BIGINT) AS id_frente, titulo,
            TRY_CAST("deputado_.id" AS BIGINT) AS id_deputado,
            "deputado_.nome" AS nome_deputado,
            "deputado_.siglaUf" AS uf,
            TRY_CAST("deputado_.idLegislatura" AS INTEGER) AS id_legislatura,
            "deputado_.titulo" AS titulo_participacao,
            TRY_CAST(dataInicio AS DATE) AS data_inicio,
            TRY_CAST(dataFim AS DATE)    AS data_fim
     FROM {f}"""),

    ("proposicao", "proposicoes", """
     SELECT TRY_CAST(id AS BIGINT) AS id_proposicao,
            siglaTipo AS sigla_tipo, descricaoTipo AS tipo,
            TRY_CAST(numero AS INTEGER) AS numero,
            -- zero aqui quer dizer "sem ano proprio" (parecer, substitutivo),
            -- e zero como ano envenena agregacao por tempo
            nullif(TRY_CAST(ano AS INTEGER), 0)     AS ano,
            TRY_CAST(dataApresentacao AS TIMESTAMP) AS apresentada_em,
            ementa, ementaDetalhada AS ementa_detalhada,
            keywords AS palavras_chave,
            ultimoStatus_descricaoSituacao AS situacao,
            ultimoStatus_descricaoTramitacao AS tramitacao,
            ultimoStatus_siglaOrgao AS orgao_atual,
            ultimoStatus_apreciacao AS apreciacao,
            TRY_CAST(ultimoStatus_dataHora AS TIMESTAMP) AS status_em,
            urlInteiroTeor AS url_inteiro_teor
     FROM {f}"""),

    ("proposicao_autor", "proposicoesAutores", """
     SELECT TRY_CAST(idProposicao AS BIGINT)    AS id_proposicao,
            TRY_CAST(idDeputadoAutor AS BIGINT) AS id_deputado,
            nomeAutor AS nome_autor, tipoAutor AS tipo_autor,
            siglaPartidoAutor AS sigla_partido, siglaUFAutor AS uf,
            TRY_CAST(ordemAssinatura AS INTEGER) AS ordem_assinatura,
            TRY_CAST(proponente AS INTEGER)      AS proponente
     FROM {f}"""),

    ("proposicao_tema", "proposicoesTemas", f"""
     SELECT TRY_CAST({ID_URI.format(c='uriProposicao')} AS BIGINT)
              AS id_proposicao,
            siglaTipo AS sigla_tipo,
            TRY_CAST(numero AS INTEGER) AS numero,
            nullif(TRY_CAST(ano AS INTEGER), 0) AS ano,
            TRY_CAST(codTema AS INTEGER) AS cod_tema, tema,
            TRY_CAST(relevancia AS INTEGER) AS relevancia
     FROM {{f}}"""),

    ("votacao", "votacoes", """
     SELECT id AS id_votacao,
            TRY_CAST(data AS DATE) AS data,
            TRY_CAST(dataHoraRegistro AS TIMESTAMP) AS registrada_em,
            TRY_CAST(idOrgao AS BIGINT) AS id_orgao,
            siglaOrgao AS sigla_orgao,
            TRY_CAST(idEvento AS BIGINT) AS id_evento,
            aprovacao, descricao,
            TRY_CAST(votosSim AS INTEGER)    AS votos_sim,
            TRY_CAST(votosNao AS INTEGER)    AS votos_nao,
            TRY_CAST(votosOutros AS INTEGER) AS votos_outros,
            ultimaApresentacaoProposicao_idProposicao::BIGINT AS id_proposicao,
            ultimaApresentacaoProposicao_descricao AS proposicao_descricao
     FROM {f}"""),

    ("voto", "votacoesVotos", """
     SELECT idVotacao AS id_votacao,
            TRY_CAST(dataHoraVoto AS TIMESTAMP) AS votado_em,
            voto,
            TRY_CAST(deputado_id AS BIGINT) AS id_deputado,
            deputado_nome AS nome_deputado,
            deputado_siglaPartido AS sigla_partido,
            deputado_siglaUf AS uf,
            TRY_CAST(deputado_idLegislatura AS INTEGER) AS id_legislatura
     FROM {f}"""),

    ("votacao_objeto", "votacoesObjetos", """
     SELECT idVotacao AS id_votacao,
            TRY_CAST(data AS DATE) AS data, descricao,
            TRY_CAST(proposicao_id AS BIGINT) AS id_proposicao,
            proposicao_siglaTipo AS sigla_tipo,
            TRY_CAST(proposicao_numero AS INTEGER) AS numero,
            nullif(TRY_CAST(proposicao_ano AS INTEGER), 0) AS ano,
            proposicao_ementa AS ementa, proposicao_titulo AS titulo
     FROM {f}"""),

    ("evento", "eventos", """
     SELECT TRY_CAST(id AS BIGINT) AS id_evento,
            TRY_CAST(dataHoraInicio AS TIMESTAMP) AS inicio,
            TRY_CAST(dataHoraFim AS TIMESTAMP)    AS fim,
            situacao, descricao, descricaoTipo AS tipo,
            localExterno AS local_externo,
            "localCamara.nome" AS local_camara,
            urlDocumentoPauta AS url_pauta
     FROM {f}"""),

    ("despesa", "despesas", """
     SELECT TRY_CAST(nuDeputadoId AS BIGINT) AS id_deputado_cota,
            txNomeParlamentar AS nome_parlamentar, cpf,
            TRY_CAST(ideCadastro AS BIGINT) AS id_cadastro,
            sgUF AS uf, sgPartido AS sigla_partido,
            TRY_CAST(nuLegislatura AS INTEGER) AS legislatura,
            TRY_CAST(numAno AS INTEGER) AS ano,
            TRY_CAST(numMes AS INTEGER) AS mes,
            txtDescricao AS categoria,
            txtDescricaoEspecificacao AS subcategoria,
            txtFornecedor AS fornecedor, txtCNPJCPF AS fornecedor_doc,
            TRY_CAST(datEmissao AS TIMESTAMP) AS emitido_em,
            TRY_CAST(vlrDocumento AS DOUBLE) AS valor_documento,
            TRY_CAST(vlrGlosa AS DOUBLE)     AS valor_glosa,
            TRY_CAST(vlrLiquido AS DOUBLE)   AS valor_liquido,
            txtPassageiro AS passageiro, txtTrecho AS trecho,
            urlDocumento AS url_documento
     FROM {f}"""),
]


# tabelas grandes demais para um CREATE TABLE AS de uma vez: a cota parlamentar
# tem 5,2 milhoes de linhas e 32 colunas de texto, e o pico de memoria da carga
# unica derruba a maquina quando ela esta com pouca RAM livre. Carregadas arquivo
# por arquivo - um por ano -, o pico cai para o tamanho de um ano.
POR_ARQUIVO = {"despesa"}


def carrega_em_partes(con, tabela, conjunto, sql):
    """Cria a tabela com o primeiro arquivo e insere os demais um a um."""
    arquivos = sorted(glob.glob(
        os.path.join(PQ, conjunto, "*.parquet").replace("\\", "/")))
    for i, arq in enumerate(arquivos):
        leitura = f"read_parquet('{arq}', union_by_name=true)"
        corpo = sql.format(f=leitura)
        if i == 0:
            con.execute(f"CREATE OR REPLACE TABLE {tabela} AS {corpo}")
        else:
            # BY NAME porque um ano pode ter coluna que outro nao tem
            con.execute(f"INSERT INTO {tabela} BY NAME {corpo}")
    print(f"  ({tabela}: {len(arquivos)} arquivos carregados um a um)")


def mostra(con, titulo, sql):
    print(f"\n--- {titulo} ---")
    print(con.sql(sql))


def main():
    con = banco.abre(schema="camara")

    feitas, ausentes = [], []
    for tabela, conjunto, sql in TABELAS:
        f = fonte(conjunto)
        if not f:
            ausentes.append(f"{tabela} (falta {conjunto})")
            continue
        if tabela in POR_ARQUIVO:
            carrega_em_partes(con, tabela, conjunto, sql)
        else:
            con.execute(f"CREATE OR REPLACE TABLE {tabela} AS "
                        + sql.format(f=f))
        # fetchall, nao fetchone: fetchone deixa o cursor aberto e a consulta
        # seguinte falha com "connection has an unfinished result"
        n = con.sql(f"SELECT COUNT(*) FROM {tabela}").fetchall()[0][0]
        feitas.append((tabela, n))
        print(f"  {tabela:<18} {n:>12,} linhas".replace(",", "."))

    if ausentes:
        print("\nnao construidas (ingestao faltando): " + ", ".join(ausentes))

    # =================== conferencias ===================================
    mostra(con, "chave duplicada? (linhas deve igualar distintos)", """
    SELECT 'deputado' AS tabela, COUNT(*) AS linhas,
           COUNT(DISTINCT id_deputado) AS distintos FROM deputado
    UNION ALL SELECT 'proposicao', COUNT(*), COUNT(DISTINCT id_proposicao)
      FROM proposicao
    UNION ALL SELECT 'votacao', COUNT(*), COUNT(DISTINCT id_votacao)
      FROM votacao
    UNION ALL SELECT 'orgao', COUNT(*), COUNT(DISTINCT id_orgao) FROM orgao
    UNION ALL SELECT 'partido', COUNT(*), COUNT(DISTINCT id_partido)
      FROM partido
    """)

    mostra(con, "o que a tipagem perdeu (NULL onde o texto nao convertia)", """
    SELECT 'deputado.id_deputado' AS campo,
           COUNT(*) FILTER (id_deputado IS NULL) AS nulos, COUNT(*) AS total
      FROM deputado
    UNION ALL SELECT 'deputado.data_nascimento',
           COUNT(*) FILTER (data_nascimento IS NULL), COUNT(*) FROM deputado
    UNION ALL SELECT 'proposicao.apresentada_em',
           COUNT(*) FILTER (apresentada_em IS NULL), COUNT(*) FROM proposicao
    UNION ALL SELECT 'voto.id_deputado',
           COUNT(*) FILTER (id_deputado IS NULL), COUNT(*) FROM voto
    UNION ALL SELECT 'despesa.valor_liquido',
           COUNT(*) FILTER (valor_liquido IS NULL), COUNT(*) FROM despesa
    ORDER BY 2 DESC
    """)

    mostra(con, "voto orfao? (voto sem a votacao correspondente)", """
    SELECT COUNT(*) AS votos_sem_votacao
    FROM voto v ANTI JOIN votacao x USING (id_votacao)
    """)

    mostra(con, "o placar declarado fecha com os votos individuais?", """
    WITH c AS (
      SELECT id_votacao,
             COUNT(*) FILTER (voto = 'Sim') AS sim,
             COUNT(*) FILTER (voto = 'Não') AS nao
      FROM voto GROUP BY 1)
    SELECT COUNT(*) AS votacoes_com_voto_nominal,
           COUNT(*) FILTER (c.sim = v.votos_sim AND c.nao = v.votos_nao)
             AS placar_bate,
           COUNT(*) FILTER (c.sim <> v.votos_sim OR c.nao <> v.votos_nao)
             AS placar_divergente
    FROM c JOIN votacao v USING (id_votacao)
    """)

    mostra(con, "cobertura por ano: de quando a quando cada tabela alcanca", """
    SELECT 'proposicao' AS tabela, MIN(ano) AS de, MAX(ano) AS ate,
           COUNT(*) AS linhas FROM proposicao WHERE ano IS NOT NULL
    UNION ALL SELECT 'votacao', MIN(year(data)), MAX(year(data)), COUNT(*)
      FROM votacao WHERE data IS NOT NULL
    UNION ALL SELECT 'voto', MIN(year(votado_em)), MAX(year(votado_em)),
           COUNT(*) FROM voto WHERE votado_em IS NOT NULL
    UNION ALL SELECT 'despesa', MIN(ano), MAX(ano), COUNT(*) FROM despesa
      WHERE ano IS NOT NULL
    UNION ALL SELECT 'evento', MIN(year(inicio)), MAX(year(inicio)), COUNT(*)
      FROM evento WHERE inicio IS NOT NULL
    ORDER BY 2
    """)

    # a coluna existe no arquivo da Camara e vem vazia em todas as linhas;
    # a conferencia fica para o dia em que isso mudar
    mostra(con, "o CPF do deputado continua vazio na origem?", """
    SELECT COUNT(*) AS deputados,
           COUNT(*) FILTER (cpf IS NOT NULL AND length(trim(cpf)) > 0)
             AS com_cpf,
           COUNT(*) FILTER (nome_civil IS NOT NULL
                            AND length(trim(nome_civil)) > 0) AS com_nome_civil,
           COUNT(*) FILTER (data_nascimento IS NOT NULL) AS com_nascimento
    FROM deputado
    """)

    mostra(con, "proposicao sem ano proprio (parecer, substitutivo)", """
    SELECT COUNT(*) AS proposicoes,
           COUNT(*) FILTER (ano IS NULL) AS sem_ano,
           round(100.0 * COUNT(*) FILTER (ano IS NULL) / COUNT(*), 1) AS pct
    FROM proposicao
    """)

    con.close()
    print(f"\n{len(feitas)} tabelas no schema camara: "
          + ", ".join(t for t, _ in feitas))
    print(f"banco: {BANCO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
