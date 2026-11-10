"""Monta a base de boletins de urna de 2026 para analise de migracao de votos.

Para cada UF e turno: baixa o pacote bweb do TSE, filtra Presidente e Governador,
grava em Parquet e descarta o material bruto. Pico de disco = o maior CSV.

Uso:  python ingestao/tse/boletins_urna.py
Retomavel: pula o que ja tem Parquet gravado.
"""
import io
import os
import sys
import time
import urllib.request
import zipfile

import duckdb

# raiz do repositorio, derivada do proprio arquivo: ingestao/tse/ -> duas acima
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PQ = os.path.join(BASE, "dados", "parquet", "tse", "bu_2026")
TMP = os.path.join(BASE, "_tmp")
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


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def recursos():
    """URLs dos 56 pacotes bweb, com UF e turno deduzidos do nome do arquivo."""
    import json
    with urllib.request.urlopen(CKAN, timeout=60) as r:
        dados = json.load(r)
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


def processa(uf, turno, url, con):
    destino = os.path.join(PQ, f"bu_{turno}_{uf}.parquet")
    if os.path.exists(destino):
        # existir nao basta: uma execucao interrompida deixa Parquet truncado,
        # que so da erro muito depois, na leitura. Confirma que abre.
        try:
            con.execute("SELECT COUNT(*) FROM read_parquet(?)",
                        [destino.replace("\\", "/")]).fetchone()
            log(f"{uf} {turno}: ja existe, pulando")
            return "pulado"
        except Exception:
            log(f"{uf} {turno}: Parquet truncado, refazendo")
            os.remove(destino)

    t0 = time.time()
    csv_local = os.path.join(TMP, f"{uf}_{turno}.csv")
    if os.path.exists(csv_local):
        # sobra de uma execucao anterior que falhou depois do download
        mb = os.path.getsize(csv_local) / 1024 / 1024
        log(f"{uf} {turno}: reaproveitando CSV em disco ({mb:,.0f} MB)")
    else:
        zip_local = os.path.join(TMP, f"{uf}_{turno}.zip")
        urllib.request.urlretrieve(url, zip_local)
        mb = os.path.getsize(zip_local) / 1024 / 1024
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
    csv_sql = csv_local.replace("\\", "/")
    dest_sql = destino.replace("\\", "/")
    con.execute(f"""
        COPY (
          SELECT {COLUNAS}
          FROM read_csv('{csv_sql}', delim=';', header=true, encoding='latin-1',
                        quote='"', all_varchar=true)
          WHERE DS_CARGO_PERGUNTA IN ({lista})
        ) TO '{dest_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    linhas = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{dest_sql}')").fetchone()[0]
    os.remove(csv_local)

    log(f"{uf} {turno}: {mb:,.0f} MB baixados -> {linhas:,} linhas "
        f"({time.time() - t0:,.0f}s)")
    return "ok"


def main():
    os.makedirs(PQ, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    con = duckdb.connect()
    # os CSVs de SP, MG, RJ, BA e CE passam de 1 GB; sem teto de memoria e sem
    # area de spill o leitor estoura os 16 GB da maquina.
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET memory_limit='5GB'")
    con.execute("SET threads=4")
    con.execute(f"SET temp_directory='{TMP.replace(chr(92), '/')}'")

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

    log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
