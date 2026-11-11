"""Monta as tabelas do TSE no schema tse e o insumo do infografico de fluxo.

Cada fonte vive no seu schema (tse, camara, senado...), e nao em main, porque
os nomes naturais dessas tabelas sao genericos: `local`, `secao` e `votos_local`
colidiriam com a segunda fonte que precisasse dos mesmos nomes. Em main fica
so o que atravessa fontes - hoje, a tabela coleta.

Decisoes que vem da analise dos dados:

- a unidade de comparacao e o LOCAL DE VOTACAO, nao a secao: os agrupamentos de
  secoes agregadas mudam entre turnos e quebram a chave.

- aptos/comparecimento sao por SECAO E CARGO, nao por secao. Em 19.776 secoes os
  dois valores divergem entre Presidente e Governador, porque o eleitor em
  transito vota so para Presidente: a mesma secao tem eleitorado maior na
  eleicao presidencial. Tratar como numero unico por secao inflava o total
  nacional de aptos em ~4,6 milhoes.

- Governador tem 2o turno em apenas 6 UFs (AC, AM, DF, ES, RN, TO). A abstencao
  precisa ser derivada por cargo, senao ela vaza para locais onde aquele cargo
  nao foi disputado.

- abstencao e branco/nulo entram como rotulos, para o fluxo fechar em 100% dos
  aptos nos dois lados.
"""
import os
import sys

import duckdb

# raiz do repositorio, derivada do proprio arquivo: transformacao/tse/ -> duas acima
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PQ = os.path.join(BASE, "dados", "parquet", "tse", "bu_2026",
                  "*.parquet").replace("\\", "/")
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")

sys.path.insert(0, BASE)
import banco                                                  # noqa: E402

con = banco.abre(schema="tse")

# residuo da epoca em que tudo vivia em main, antes de haver uma segunda fonte.
# Em base nova nao existe nada disso e o laco nao faz nada; em base antiga,
# evita conviver com duas copias das mesmas tabelas, uma delas desatualizando.
# O tipo vem do catalogo porque DROP VIEW IF EXISTS nao e inofensivo quando o
# objeto existe como tabela: o DuckDB erra em vez de ignorar.
VELHAS = ("bu", "secao", "local", "votos_local", "fluxo_insumo",
          "fluxo_estimado")
for nome, tipo in con.execute("""
        SELECT table_name, 'TABLE' FROM duckdb_tables()
         WHERE schema_name = 'main' AND table_name IN ?
        UNION ALL
        SELECT view_name, 'VIEW' FROM duckdb_views()
         WHERE schema_name = 'main' AND view_name IN ?
    """, [list(VELHAS), list(VELHAS)]).fetchall():
    con.execute(f"DROP {tipo} IF EXISTS main.{nome}")
    print(f"removido residuo main.{nome} ({tipo.lower()})")

con.execute(f"CREATE OR REPLACE VIEW bu AS SELECT * FROM read_parquet('{PQ}')")

# --- eleitorado por secao E cargo (uma linha por combinacao) ----------------
con.execute("""
CREATE OR REPLACE TABLE secao AS
SELECT
  turno, cargo, uf, cd_municipio, municipio, zona, secao, local_votacao,
  max(aptos)            AS aptos,
  max(comparecimento)   AS comparecimento,
  max(abstencoes)       AS abstencoes,
  any_value(secoes_agregadas) AS secoes_agregadas,
  min(dt_abertura)      AS dt_abertura,
  max(dt_encerramento)  AS dt_encerramento
FROM bu
GROUP BY turno, cargo, uf, cd_municipio, municipio, zona, secao, local_votacao
""")

# --- eleitorado por local de votacao e cargo -------------------------------
con.execute("""
CREATE OR REPLACE TABLE local AS
SELECT
  turno, cargo, uf, cd_municipio, municipio, zona, local_votacao,
  COUNT(*)              AS qt_secoes,
  SUM(aptos)            AS aptos,
  SUM(comparecimento)   AS comparecimento,
  SUM(abstencoes)       AS abstencoes,
  COUNT(*) FILTER (secoes_agregadas <> '#NULO#') AS secoes_com_agregacao
FROM secao
GROUP BY ALL
""")

# --- votos por local, cargo e votavel --------------------------------------
con.execute("""
CREATE OR REPLACE TABLE votos_local AS
SELECT
  turno, cargo, uf, cd_municipio, municipio, zona, local_votacao,
  CASE tipo_votavel
    WHEN 'Nominal' THEN upper(nm_votavel)
    WHEN 'Legenda' THEN 'LEGENDA ' || sg_partido
    ELSE upper(tipo_votavel)
  END                   AS rotulo,
  tipo_votavel,
  any_value(nr_votavel) AS nr_votavel,
  SUM(votos)            AS votos
FROM bu
GROUP BY ALL
""")

# --- insumo do fluxo: rotulos + abstencao, sobre os aptos do mesmo cargo ----
con.execute("""
CREATE OR REPLACE TABLE fluxo_insumo AS
WITH tudo AS (
  SELECT turno, cargo, uf, cd_municipio, municipio, zona, local_votacao,
         rotulo, votos
  FROM votos_local
  UNION ALL
  SELECT turno, cargo, uf, cd_municipio, municipio, zona, local_votacao,
         'ABSTENCAO' AS rotulo, abstencoes AS votos
  FROM local
)
SELECT t.*, l.aptos, t.votos / NULLIF(l.aptos, 0) AS fracao_aptos
FROM tudo t
JOIN local l USING (turno, cargo, uf, cd_municipio, zona, local_votacao)
""")

# =================== conferencias de fechamento ============================
def mostra(titulo, sql):
    print(f"\n--- {titulo} ---")
    print(con.sql(sql))


mostra("o fluxo fecha nos aptos? (reconstruido - aptos deve ser 0)", """
WITH r AS (SELECT turno, cargo, SUM(votos) AS reconstruido
           FROM fluxo_insumo GROUP BY 1,2),
     a AS (SELECT turno, cargo, SUM(aptos) AS aptos FROM local GROUP BY 1,2)
SELECT r.turno, r.cargo, a.aptos, r.reconstruido,
       r.reconstruido - a.aptos AS diferenca
FROM r JOIN a USING (turno, cargo) ORDER BY 2,1
""")

mostra("eleitorado por cargo e turno", """
SELECT turno, cargo, SUM(aptos) AS aptos, SUM(comparecimento) AS comparecimento,
       SUM(abstencoes) AS abstencoes,
       round(SUM(abstencoes)*100.0/SUM(aptos), 2) AS pct_abstencao,
       SUM(qt_secoes) AS secoes, COUNT(*) AS locais
FROM local GROUP BY 1,2 ORDER BY 2,1
""")

mostra("secao duplicada? (linhas deve igualar secoes_unicas)", """
SELECT turno, cargo, COUNT(*) AS linhas,
       COUNT(DISTINCT (uf, cd_municipio, zona, secao)) AS secoes_unicas
FROM secao GROUP BY 1,2 ORDER BY 2,1
""")

mostra("Presidente — 2o turno nacional", """
SELECT rotulo, SUM(votos) AS votos,
       round(SUM(votos)*100.0/(SELECT SUM(votos) FROM fluxo_insumo
             WHERE cargo='Presidente' AND turno=2), 2) AS pct_aptos
FROM fluxo_insumo WHERE cargo='Presidente' AND turno=2
GROUP BY 1 ORDER BY 2 DESC
""")

mostra("Presidente — 1o turno nacional", """
SELECT rotulo, SUM(votos) AS votos
FROM fluxo_insumo WHERE cargo='Presidente' AND turno=1
GROUP BY 1 ORDER BY 2 DESC LIMIT 12
""")

con.close()
print(f"\nbanco: {BANCO}")
