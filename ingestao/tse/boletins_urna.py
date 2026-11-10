"""Monta a base de boletins de urna de 2026 para analise de migracao de votos.

Para cada UF e turno: baixa o pacote bweb do TSE, filtra Presidente e Governador,
grava em Parquet e descarta o material bruto. Pico de disco = o maior CSV.

Passa por ingestao/comum.py como as demais fontes, para a procedencia de cada
pacote ficar registrada na tabela coleta. Arquivo que ja existe de uma coleta
anterior a esse registro e anotado com o instante inferido da gravacao do
Parquet - inferido, e dito como tal na observacao, em vez de rebaixar 56
pacotes de gigabytes so para ter a data exata.

Uso:  python ingestao/tse/boletins_urna.py
Retomavel: pula o que ja tem Parquet gravado.
"""
import datetime
import os
import sys
import time
import zipfile

# ingestao/tse/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "tse"
CONJUNTO = "bu_2026"
BASE = comum.BASE
PQ = os.path.join(BASE, "dados", "parquet", "tse", "bu_2026")
TMP = comum.TMP
CKAN = ("https://dadosabertos.tse.jus.br/api/3/action/"
        "package_show?id=resultados-2026-boletim-de-urna")
CARGOS = ("Presidente", "Governador")

COLUNAS = """
  NR_TURNO::SMALLINT               AS turno,
  SG_UF                            AS uf,
  CD_MUNICIPIO::INTEGER            AS cd_municipio,
  NM_MUNICIPIO                     AS municipio,
  NR_ZONA::INTEGER                 AS zona,
  NR_SECAO::INTEGER                AS secao,
  NR_LOCAL_VOTACAO::INTEGER        AS local_votacao,
  DS_CARGO_PERGUNTA                AS cargo,
  NR_PARTIDO::INTEGER              AS nr_partido,
  SG_PARTIDO                       AS sg_partido,
  DS_TIPO_VOTAVEL                  AS tipo_votavel,
  NR_VOTAVEL                       AS nr_votavel,
  NM_VOTAVEL                       AS nm_votavel,
  QT_VOTOS::INTEGER                AS votos,
  QT_APTOS::INTEGER                AS aptos,
  QT_COMPARECIMENTO::INTEGER       AS comparecimento,
  QT_ABSTENCOES::INTEGER           AS abstencoes,
  DS_SECOES_AGREGADAS              AS secoes_agregadas,
  DT_ABERTURA                      AS dt_abertura,
  DT_ENCERRAMENTO                  AS dt_encerramento,
  NR_URNA_EFETIVADA                AS nr_urna,
  QT_ELEI_BIOM_SEM_HABILITACAO     AS biom_sem_habilitacao
"""


log = comum.log


def recursos():
    """URLs dos 56 pacotes bweb, com UF e turno deduzidos do nome do arquivo."""
    dados = comum.pega_json(CKAN, tempo=90)
    saida = []
    for rec in dados["result"]["resources"]:
        url = rec["url"]
        if not url.endswith(".zip"):
            continue
        nome = url.rsplit("/", 1)[-1]          # bweb_1t_AC_051020261403.zip
        partes = nome.split("_")
        turno, uf = partes[1], partes[2]
        saida.append((uf, turno, url))
    return sorted(saida)


def ja_registrado(con, arquivo):
    return con.execute("""SELECT COUNT(*) FROM coleta
                          WHERE fonte = ? AND conjunto = ? AND arquivo = ?""",
                       [FONTE, CONJUNTO, arquivo]).fetchone()[0] > 0


def registra_retroativo(con, destino, arquivo, url):
    """Anota um pacote que ja estava em disco antes de existir o registro.

    O instante vem da gravacao do Parquet, nao do download - sao proximos, mas
    nao sao a mesma coisa, e a observacao diz isso. A alternativa seria apagar
    e rebaixar 56 pacotes de gigabytes para ganhar precisao de minutos numa
    data que o portal publica por dia.
    """
    con.execute(comum.CRIA_COLETA)
    linhas = comum.linhas_parquet(con, destino)
    quando = datetime.datetime.fromtimestamp(os.path.getmtime(destino))
    con.execute("DELETE FROM coleta WHERE fonte=? AND conjunto=? AND arquivo=?",
                [FONTE, CONJUNTO, arquivo])
    con.execute("INSERT INTO coleta VALUES (?,?,?,?,?,?,?,?,?)",
                [FONTE, CONJUNTO, arquivo, url, quando,
                 os.path.getsize(destino), linhas, None,
                 "instante inferido da gravacao do Parquet, nao do download: "
                 "coleta anterior ao registro de procedencia"])


def processa(uf, turno, url, con):
    arquivo = f"bu_{turno}_{uf}.parquet"
    destino = os.path.join(PQ, arquivo)
    if os.path.exists(destino):
        # existir nao basta: uma execucao interrompida deixa Parquet truncado,
        # que so da erro muito depois, na leitura. Confirma que abre.
        if comum.parquet_valido(con, destino):
            if not ja_registrado(con, arquivo):
                registra_retroativo(con, destino, arquivo, url)
                log(f"{uf} {turno}: ja existe; procedencia registrada")
            else:
                log(f"{uf} {turno}: ja existe, pulando")
            return "pulado"
        log(f"{uf} {turno}: Parquet truncado, refazendo")
        os.remove(destino)

    t0 = time.time()
    csv_local = os.path.join(TMP, f"{uf}_{turno}.csv")
    zip_local = os.path.join(TMP, f"{uf}_{turno}.zip")
    bytes_, sha = None, None
    if os.path.exists(csv_local):
        # sobra de uma execucao anterior que falhou depois do download
        bytes_ = os.path.getsize(csv_local)
        log(f"{uf} {turno}: reaproveitando CSV em disco "
            f"({bytes_ / 1e6:,.0f} MB)")
    else:
        bytes_, sha, _ = comum.baixa(url, zip_local)
        with zipfile.ZipFile(zip_local) as z:
            nome_csv = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(nome_csv) as fonte, open(csv_local, "wb") as alvo:
                while True:
                    bloco = fonte.read(1 << 22)
                    if not bloco:
                        break
                    alvo.write(bloco)
        os.remove(zip_local)

    lista = ", ".join(f"'{c}'" for c in CARGOS)
    linhas, obs = comum.csv_para_parquet(
        con, csv_local, destino, selecao=COLUNAS, delim=";",
        encoding="latin-1", onde=f"DS_CARGO_PERGUNTA IN ({lista})")
    os.remove(csv_local)
    comum.registra(con, FONTE, CONJUNTO, arquivo, url, bytes_, linhas, sha, obs)

    log(f"{uf} {turno}: {bytes_ / 1e6:,.0f} MB baixados -> {linhas:,} linhas "
        f"({time.time() - t0:,.0f}s)")
    return "ok"


def main():
    os.makedirs(PQ, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    # o banco entra na jogada porque a coleta de cada pacote fica registrada
    # nele; os CSVs de SP, MG, RJ, BA e CE passam de 1 GB, e sem teto de
    # memoria e area de descarga o leitor estoura os 16 GB da maquina
    con = comum.abre_banco()
    con.execute("SET threads=4")

    pacotes = recursos()
    log(f"{len(pacotes)} pacotes a processar")
    falhas = []
    for i, (uf, turno, url) in enumerate(pacotes, 1):
        try:
            processa(uf, turno, url, con)
        except Exception as e:
            log(f"!! {uf} {turno} FALHOU: {type(e).__name__}: {e}")
            falhas.append((uf, turno))
        if i % 10 == 0:
            log(f"--- progresso: {i}/{len(pacotes)}")

    print("\n--- coletado do TSE ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas,
               round(SUM(bytes) / 1e6, 1) AS mb, min(baixado_em)::DATE AS coletado_em
        FROM coleta WHERE fonte = 'tse' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()

    log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
