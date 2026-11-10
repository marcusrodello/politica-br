"""Grava a descricao de cada objeto no proprio banco e regera o dicionario.

O banco e a fonte unica da descricao: os COMMENT abaixo sao a origem, e
DICIONARIO.md e gerado do catalogo (duckdb_tables / duckdb_columns), nunca
escrito a mao. Toda descricao foi conferida no dado ou no CSV de origem.

Sai com erro se alguma coluna do schema main ficar sem descricao.
"""
import os
import sys

import duckdb

# raiz do repositorio, derivada do proprio arquivo: transformacao/ -> uma acima
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")
DOC = os.path.join(BASE, "docs", "dicionario.md")

TABELAS = {
    "coleta": "Registro de procedencia: uma linha por arquivo que entrou na "
              "base, com a URL de origem, o instante do download, o tamanho, "
              "as linhas e o sha256. E o que sustenta a promessa de que cada "
              "numero do portal volta a fonte oficial e a data da coleta. "
              "Gravada por ingestao/comum.py; conferida contra os portais por "
              "ingestao/confere_coleta.py.",
    "bu": "Boletins de urna de 2026 (Presidente e Governador, 1o e 2o turno) "
          "como vieram do TSE. Uma linha por secao, cargo e votavel. Origem: "
          "CSV bweb do Portal de Dados Abertos, gravado pelo TSE; carregado "
          "por ingestao/tse/boletins_urna.py.",
    "secao": "Eleitorado de cada secao em cada cargo. Uma linha por turno, "
             "cargo e secao. Derivada de bu. A chave inclui o cargo porque "
             "aptos e comparecimento divergem entre Presidente e Governador "
             "em 19.776 secoes: o eleitor em transito vota so para Presidente.",
    "local": "Eleitorado agregado por local de votacao e cargo. Uma linha por "
             "turno, cargo e local. Derivada de secao. O local e a unidade de "
             "comparacao entre turnos porque os agrupamentos de secoes "
             "agregadas mudam de um turno para o outro.",
    "votos_local": "Votos somados por local de votacao, cargo e votavel. Uma "
                   "linha por turno, cargo, local e rotulo. Derivada de bu.",
    "fluxo_insumo": "Insumo do infografico de fluxo: cada rotulo disputado "
                    "mais a abstencao, com a fracao sobre os aptos. Uma linha "
                    "por turno, cargo, local e rotulo. A soma de votos por "
                    "turno e cargo fecha exatamente no total de aptos "
                    "(conferido: diferenca zero nos quatro cortes).",
    "fluxo_estimado": "Matriz de fluxo de votos do 1o para o 2o turno, "
                      "ESTIMADA por regressao ecologica no nivel do local de "
                      "votacao, por transformacao/tse/estima_fluxo.py. Uma "
                      "linha por cargo, escopo, origem e destino. NAO e "
                      "migracao medida: o voto e secreto e o dado e agregado, "
                      "entao movimentos opostos dentro do mesmo local se "
                      "cancelam (falacia ecologica) e o que sai aqui e o fluxo "
                      "LIQUIDO - a lealdade de um candidato e um teto e a "
                      "troca entre candidatos um piso. Cada celula vem com "
                      "faixa de 95% por bootstrap de municipios; faixa larga "
                      "significa que o dado nao decide aquela celula.",
}

# descricao valida em qualquer tabela que tenha a coluna
COMUNS = {
    "turno": "1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). "
             "Vem de NR_TURNO do bweb.",
    "cargo": "Cargo disputado: 'Presidente' ou 'Governador'. Vem de "
             "DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: "
             "AC, AM, DF, ES, RN e TO.",
    "uf": "Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. "
          "Vem de SG_UF.",
    "cd_municipio": "Codigo do municipio na Justica Eleitoral, que nao e o "
                    "codigo do IBGE. Vem de CD_MUNICIPIO.",
    "municipio": "Nome do municipio. Vem de NM_MUNICIPIO.",
    "zona": "Numero da zona eleitoral dentro da UF. Vem de NR_ZONA.",
    "secao": "Numero da secao eleitoral dentro da zona. Vem de NR_SECAO. "
             "Corresponde a uma urna.",
    "local_votacao": "Numero do local de votacao (o predio) dentro da zona. "
                     "Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao "
                     "entre turnos.",
    "nr_partido": "Numero do partido do candidato. Vem de NR_PARTIDO.",
    "sg_partido": "Sigla do partido. Vem de SG_PARTIDO; vale '#NULO#' nas "
                  "linhas de branco e nulo.",
    "tipo_votavel": "Natureza do voto: Nominal, Legenda, Branco ou Nulo. Vem "
                    "de DS_TIPO_VOTAVEL.",
    "nr_votavel": "Numero digitado na urna. Vem de NR_VOTAVEL; 95 identifica "
                  "branco e 96 identifica nulo.",
    "nm_votavel": "Nome do candidato como aparece na urna. Vem de NM_VOTAVEL; "
                  "vale 'Branco' ou 'Nulo' nas linhas correspondentes.",
    "votos": "Votos apurados. Vem de QT_VOTOS. Unidade: voto.",
    "aptos": "Eleitores aptos naquele cargo. Vem de QT_APTOS. Unidade: eleitor.",
    "comparecimento": "Eleitores que compareceram. Vem de QT_COMPARECIMENTO. "
                      "Unidade: eleitor.",
    "abstencoes": "Aptos que nao compareceram. Vem de QT_ABSTENCOES. "
                  "Unidade: eleitor.",
    "secoes_agregadas": "Secoes cujo eleitorado foi somado nesta. '#NULO#' "
                        "quando nao houve agregacao. Vem de "
                        "DS_SECOES_AGREGADAS. O conteudo muda entre turnos, "
                        "por isso a comparacao e feita por local.",
    "dt_abertura": "Instante em que a urna ficou pronta para receber votos, no "
                   "horario LOCAL da urna, nao no de Brasilia. Vem de "
                   "DT_ABERTURA.",
    "dt_encerramento": "Instante do encerramento, tambem no horario local da "
                       "urna. Vem de DT_ENCERRAMENTO.",
    "nr_urna": "Numero de serie da urna que gerou o boletim. Vem de "
               "NR_URNA_EFETIVADA.",
    "biom_sem_habilitacao": "Eleitores da secao sem habilitacao biometrica. "
                            "Vem de QT_ELEI_BIOM_SEM_HABILITACAO. Unidade: "
                            "eleitor.",
    "rotulo": "Identidade do destino do voto: nome do candidato quando "
              "nominal, 'LEGENDA <sigla>' no voto de legenda, ou BRANCO / "
              "NULO. Normalizado em maiusculas.",
    "qt_secoes": "Secoes somadas neste local naquele cargo. Unidade: secao.",
    "secoes_com_agregacao": "Quantas dessas secoes agregam eleitorado de "
                            "outra. Serve para medir o ruido da comparacao "
                            "entre turnos. Unidade: secao.",
    "fracao_aptos": "votos / aptos. Fracao entre 0 e 1, nao percentual.",
    "escopo": "Recorte em que a regressao rodou: 'UF' para a matriz estimada "
              "dentro de um estado, 'BRASIL' para a media das 27 matrizes "
              "estaduais ponderada pelos eleitores de cada origem - esse e o "
              "numero publicado - e 'BRASIL_DIRETO' para uma unica regressao "
              "no pais inteiro, que fica gravada so como contraste: ela supoe "
              "comportamento igual em todo o territorio e por isso crava 0% ou "
              "100% em 27 das 50 celulas, contra 2 na estimativa por UF.",
    "origem": "Rotulo escolhido no 1o turno: candidato, BRANCO, NULO, "
              "ABSTENCAO, ou OUTROS para o conjunto dos candidatos com menos "
              "de 0,2% dos aptos, cuja coluna de regressao e quase constante "
              "entre locais e nao identifica coeficiente proprio.",
    "destino": "Rotulo escolhido no 2o turno, nos mesmos termos de origem.",
    "eleitores_origem": "Eleitores que escolheram a origem no 1o turno, dentro "
                        "do escopo. E o denominador de fracao. Unidade: eleitor.",
    "fracao": "Parcela da origem estimada como tendo ido para o destino. "
              "Fracao entre 0 e 1, nao percentual. Por construcao, as fracoes "
              "de uma mesma origem somam 1.",
    "fracao_min": "Limite inferior da faixa de 95% de fracao, percentil 2,5 de "
                  "150 replicas de bootstrap que reamostram os MUNICIPIOS do "
                  "escopo - nao os locais, que dentro de um municipio se "
                  "parecem e estreitariam a faixa artificialmente.",
    "fracao_max": "Limite superior da faixa de 95% de fracao, percentil 97,5 "
                  "das mesmas replicas.",
    "eleitores": "fracao x eleitores_origem: eleitores estimados nesse fluxo. "
                 "Unidade: eleitor.",
    "eleitores_min": "fracao_min x eleitores_origem. Unidade: eleitor.",
    "eleitores_max": "fracao_max x eleitores_origem. Unidade: eleitor.",
    "locais": "Locais de votacao que sustentaram a regressao do escopo, ja "
              "descontado o local sem par entre os turnos. Unidade: local.",
    "municipios": "Municipios presentes no escopo. Unidade: municipio.",
    # --- registro de coleta (ingestao/comum.py) --------------------------
    "fonte": "Orgao de origem do arquivo: 'tse', 'camara', 'senado' e assim "
             "por diante. Define a pasta em dados/parquet e, no banco, o "
             "schema da fonte.",
    "conjunto": "Conjunto de dados dentro da fonte, no nome que o proprio "
                "portal usa: 'votacoesVotos', 'proposicoes', 'bu_2026'.",
    "arquivo": "Nome do Parquet gravado em dados/parquet/<fonte>/<conjunto>/.",
    "url": "URL exata de onde o arquivo foi baixado, para qualquer pessoa "
           "refazer o caminho ate a fonte oficial.",
    "baixado_em": "Instante do download, no horario local da maquina que "
                  "rodou a ingestao. E a 'data da coleta' que o portal cita "
                  "ao lado de cada numero.",
    "bytes": "Tamanho do arquivo baixado da origem, em bytes, conferido "
             "contra o Content-Length declarado pelo portal - download "
             "incompleto falha em vez de entrar na base.",
    "linhas": "Linhas gravadas no Parquet resultante.",
    "sha256": "Hash do conteudo baixado, para detectar que a origem mudou "
              "entre duas coletas.",
    "observacao": "Vazio quando a carga foi limpa. Quando o CSV de origem "
                  "nao obedece ao padrao, guarda quantas linhas e de que "
                  "tipo foi o defeito, e como o leitor foi relaxado - para o "
                  "caminho diferente nao ficar invisivel depois.",
}

# sobrescreve quando o sentido muda na tabela
ESPECIFICAS = {
    ("fluxo_insumo", "rotulo"):
        "Mesmos rotulos de votos_local, mais ABSTENCAO, que entra como destino "
        "para o fluxo fechar em 100% dos aptos.",
    ("fluxo_insumo", "votos"):
        "Votos do rotulo, ou eleitores que se abstiveram quando o rotulo e "
        "ABSTENCAO. Unidade: voto, exceto nessa linha, em que e eleitor.",
    ("fluxo_insumo", "aptos"):
        "Aptos do local naquele cargo e turno, usado como denominador de "
        "fracao_aptos. Unidade: eleitor.",
    ("fluxo_estimado", "uf"):
        "Sigla da UF quando escopo = 'UF'; NULL nos escopos nacionais. O "
        "exterior ('ZZ') nao entra: sao poucos locais para a regressao.",
    ("fluxo_estimado", "cargo"):
        "'Presidente' tem matriz por UF e matriz nacional. 'Governador' so tem "
        "matriz por UF, e apenas nas 6 que tiveram 2o turno (AC, AM, DF, ES, "
        "RN, TO): cada estado disputou entre candidatos proprios, e uma matriz "
        "nacional misturaria nomes que nunca estiveram na mesma urna.",
    ("fluxo_estimado", "fracao_min"):
        "Limite inferior da faixa de 95% de fracao, percentil 2,5 de 150 "
        "replicas de bootstrap que reamostram os MUNICIPIOS do escopo - nao os "
        "locais, que dentro de um municipio se parecem e estreitariam a faixa "
        "artificialmente. No DF, onde o municipio e unico, a reamostragem "
        "desce para a zona eleitoral.",
}


def lit(texto):
    """COMMENT ON nao aceita parametro vinculado; a string vai literal."""
    return "'" + texto.replace("'", "''") + "'"


con = duckdb.connect(BANCO)

# o catalogo cobre todos os schemas de fonte, nao so main: cada fonte vive no
# seu (tse, camara, senado...) e main guarda o que atravessa fontes
SCHEMAS = [s[0] for s in con.execute("""
    SELECT schema_name FROM duckdb_schemas()
    WHERE NOT internal AND database_name = 'politica_br' ORDER BY 1
""").fetchall()]

onde = {t: s for s, t in con.execute("""
    SELECT schema_name, table_name FROM duckdb_tables()
    UNION ALL SELECT schema_name, view_name FROM duckdb_views()
    WHERE NOT internal
""").fetchall()}

for tabela, desc in TABELAS.items():
    if tabela not in onde:
        continue            # tabela ainda nao construida nesta base
    alvo = "VIEW" if tabela == "bu" else "TABLE"
    con.execute(f"COMMENT ON {alvo} {onde[tabela]}.{tabela} IS {lit(desc)}")

colunas = con.execute(f"""
    SELECT schema_name, table_name, column_name FROM duckdb_columns()
    WHERE schema_name IN ({','.join("'" + s + "'" for s in SCHEMAS)})
      AND NOT internal
    ORDER BY schema_name, table_name, column_index
""").fetchall()

sem_descricao = []
for schema, tabela, coluna in colunas:
    desc = ESPECIFICAS.get((tabela, coluna)) or COMUNS.get(coluna)
    if desc is None:
        sem_descricao.append(f"{schema}.{tabela}.{coluna}")
        continue
    con.execute(f'COMMENT ON COLUMN {schema}.{tabela}."{coluna}" IS {lit(desc)}')

# --- regera o dicionario a partir do catalogo -------------------------------
objetos = con.execute("""
SELECT schema_name, table_name, comment, 'tabela' AS tipo FROM duckdb_tables()
UNION ALL
SELECT schema_name, view_name, comment, 'view' FROM duckdb_views()
WHERE NOT internal
ORDER BY 1, 4 DESC, 2
""").fetchall()

linhas = ["# Dicionário de dados", "",
          "Gerado por `transformacao/documenta_banco.py` a partir do "
          "catálogo do banco.",
          "Não editar à mão: a descrição vive no banco.", "",
          "Uma fonte por schema; `main` guarda o que atravessa fontes.", ""]

schema_atual = None
for schema, nome, comentario, tipo in objetos:
    if schema != schema_atual:
        linhas += [f"# Schema `{schema}`", ""]
        schema_atual = schema
    cols = con.execute("""
        SELECT column_name, data_type, comment FROM duckdb_columns()
        WHERE table_name = ? AND schema_name = ?
        ORDER BY column_index
    """, [nome, schema]).fetchall()
    n = con.execute(f'SELECT COUNT(*) FROM {schema}."{nome}"').fetchone()[0]
    linhas += [f"## `{schema}.{nome}` ({tipo})", "",
               comentario or "_sem descrição_", "",
               f"Linhas: {n:,}".replace(",", "."), "",
               "| Coluna | Tipo | Descrição |", "| --- | --- | --- |"]
    for c, t, cd in cols:
        linhas.append(f"| `{c}` | {t} | {cd or ''} |")
    linhas.append("")

with open(DOC, "w", encoding="utf-8") as fh:
    fh.write("\n".join(linhas))

con.close()

print(f"{len(colunas)} colunas em {len(SCHEMAS)} schemas "
      f"({', '.join(SCHEMAS)}); "
      f"{len(colunas) - len(sem_descricao)} documentadas")
print(f"{DOC} regerado")
if sem_descricao:
    print(f"FALTAM {len(sem_descricao)} descricoes: "
          + ", ".join(sem_descricao[:25])
          + (" ..." if len(sem_descricao) > 25 else ""))
    sys.exit(1)
