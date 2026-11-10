"""Grava a descricao de cada objeto no proprio banco e regera o dicionario.

O banco e a fonte unica da descricao: os COMMENT abaixo sao a origem, e
DICIONARIO.md e gerado do catalogo (duckdb_tables / duckdb_columns), nunca
escrito a mao. Toda descricao foi conferida no dado ou no CSV de origem.

Sai com erro se alguma coluna do schema main ficar sem descricao.
"""
import os
import sys

import duckdb

# raiz do repositorio, derivada do proprio arquivo: transformacao/tse/ -> duas acima
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")
DOC = os.path.join(BASE, "docs", "dicionario-tse-2026.md")

TABELAS = {
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
}


def lit(texto):
    """COMMENT ON nao aceita parametro vinculado; a string vai literal."""
    return "'" + texto.replace("'", "''") + "'"


con = duckdb.connect(BANCO)

for tabela, desc in TABELAS.items():
    alvo = "VIEW" if tabela == "bu" else "TABLE"
    con.execute(f"COMMENT ON {alvo} {tabela} IS {lit(desc)}")

colunas = con.execute("""
    SELECT table_name, column_name FROM duckdb_columns()
    WHERE schema_name = 'main' AND NOT internal
    ORDER BY table_name, column_index
""").fetchall()

sem_descricao = []
for tabela, coluna in colunas:
    desc = ESPECIFICAS.get((tabela, coluna)) or COMUNS.get(coluna)
    if desc is None:
        sem_descricao.append(f"{tabela}.{coluna}")
        continue
    con.execute(f"COMMENT ON COLUMN {tabela}.{coluna} IS {lit(desc)}")

# --- regera o dicionario a partir do catalogo -------------------------------
objetos = con.execute("""
SELECT table_name, comment, 'tabela' AS tipo FROM duckdb_tables()
UNION ALL
SELECT view_name, comment, 'view' FROM duckdb_views() WHERE NOT internal
ORDER BY 3 DESC, 1
""").fetchall()

linhas = ["# Dicionário de dados — TSE, eleição de 2026", "",
          "Gerado por `transformacao/tse/documenta_banco.py` a partir do "
          "catálogo do banco.",
          "Não editar à mão: a descrição vive no banco.", ""]

for nome, comentario, tipo in objetos:
    cols = con.execute("""
        SELECT column_name, data_type, comment FROM duckdb_columns()
        WHERE table_name = ? AND schema_name = 'main'
        ORDER BY column_index
    """, [nome]).fetchall()
    n = con.execute(f'SELECT COUNT(*) FROM "{nome}"').fetchone()[0]
    linhas += [f"## `{nome}` ({tipo})", "",
               comentario or "_sem descrição_", "",
               f"Linhas: {n:,}".replace(",", "."), "",
               "| Coluna | Tipo | Descrição |", "| --- | --- | --- |"]
    for c, t, cd in cols:
        linhas.append(f"| `{c}` | {t} | {cd or ''} |")
    linhas.append("")

with open(DOC, "w", encoding="utf-8") as fh:
    fh.write("\n".join(linhas))

con.close()

print(f"{len(colunas)} colunas no schema main; "
      f"{len(colunas) - len(sem_descricao)} documentadas")
print(f"{DOC} regerado")
if sem_descricao:
    print("FALTAM descricoes: " + ", ".join(sem_descricao))
    sys.exit(1)
