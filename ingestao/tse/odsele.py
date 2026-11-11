"""Baixa os dados abertos eleitorais do TSE (ODSELE) e grava em Parquet.

Alem dos boletins de urna de 2026, que tem script proprio, o TSE publica 190
pacotes no CKAN. Este script cobre os que sustentam o portal:

  candidatos                  1933-2026. Quem se candidatou, por qual partido, a
                              que cargo, e com que resultado. E a espinha da
                              identidade de politico do projeto: o SQ_CANDIDATO
                              amarra a pessoa dentro de uma eleicao e o CPF, nos
                              anos em que vem preenchido, amarra entre eleicoes.
  candidatos_complementar     ocupacao, grau de instrucao, estado civil, raca
  bens_candidato              patrimonio declarado na candidatura
  coligacoes                  composicao das coligacoes
  votacao_candidato_munzona   votos de cada candidato por municipio e zona
  votacao_partido_munzona     votos por partido, por municipio e zona
  detalhe_votacao_munzona     comparecimento e abstencao por municipio e zona
  perfil_eleitorado           eleitorado por sexo, idade e instrucao
  contas_candidatos           prestacao de contas de campanha
  municipio_tse_ibge          a ponte entre o codigo do municipio no TSE e no
                              IBGE - sem ela nao se cruza eleicao com indicador

As URLs vem do CKAN, nao montadas a mao: o TSE muda o caminho no CDN de vez em
quando, e o catalogo e a unica fonte que acompanha.

Cada ZIP traz um CSV por UF mais um BR consolidado, e a carga grava UM PARQUET
POR CSV, em dados/parquet/tse/<conjunto>/<ano>/<UF>.parquet. Ler os 28 de uma
vez estourava a memoria em maquina apertada; um a um, o pico cai para o tamanho
de uma UF e a retomada nao perde o ano inteiro por causa do ultimo arquivo. Na
leitura depois, o glob recursivo junta tudo igual - com union_by_name, porque o
arquivo BR as vezes tem coluna que os de UF nao tem.

Uso:  python ingestao/tse/odsele.py [--so CONJUNTO] [--desde ANO] [--listar]
Retomavel: reexecutar pula o que ja tem Parquet valido.
"""
import glob as glob_
import os
import shutil
import sys
import zipfile

# ingestao/tse/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "tse"
CKAN = "https://dadosabertos.tse.jus.br/api/3/action"

# pacotes do CKAN que entram, por prefixo; o ano vem do proprio nome do pacote
PACOTES = ["candidatos", "resultados", "eleitorado",
           "prestacao-de-contas-eleitorais"]

# pedaco do URL -> nome do conjunto local. O que nao casar com nenhum destes
# fica de fora, de proposito: o TSE publica muita coisa que o portal nao usa.
#
# A SERIE HISTORICA TROCA DE FORMATO EM 1994. Antes disso nao existe cadastro
# de candidato padronizado: de 1933 a 1990 o que ha e a legenda (partido) e o
# vinculo candidato-legenda, e o resultado vem agregado por UF, nao por
# municipio e zona. Quem for cruzar as duas eras precisa saber que
# votacao_candidato_uf e votacao_candidato_munzona respondem a perguntas
# diferentes, e que o nome do candidato antes de 1994 nem sempre identifica
# uma pessoa.
CONJUNTOS = {
    # 1994 em diante
    "consulta_cand_complementar/": "candidatos_complementar",
    "consulta_cand/": "candidatos",
    "bem_candidato/": "bens_candidato",
    "consulta_coligacao/": "coligacoes",
    "votacao_candidato_munzona/": "votacao_candidato_munzona",
    "votacao_partido_munzona/": "votacao_partido_munzona",
    "detalhe_votacao_munzona/": "detalhe_votacao_munzona",
    "perfil_eleitorado/": "perfil_eleitorado",
    "prestacao_de_contas_eleitorais_candidatos": "contas_candidatos",
    # 1933 a 1992
    "consulta_legendas/": "legendas",
    "candidato_legenda/": "candidato_legenda",
    "votacao_candidato_uf/": "votacao_candidato_uf",
    "votacao_partido_uf/": "votacao_partido_uf",
    "detalhe_votacao_uf/": "detalhe_votacao_uf",
    "consulta_vagas/": "vagas",
    # atemporal
    "municipio_tse_ibge/": "municipio_tse_ibge",
}


# ordem de coleta, do mais valioso e leve ao mais pesado. Importa porque uma
# execucao e interrompida com frequencia - o acervo tem dezenas de GB e os
# arquivos variam de 100 KB a 1,25 GB - e quem para no meio quer ter na mao a
# parte que sustenta o portal, nao a prestacao de contas de 2024 pela metade.
PRIORIDADE = [
    "municipio_tse_ibge",          # a ponte TSE-IBGE, 100 KB e indispensavel
    "candidatos",                  # a espinha da identidade de politico
    "legendas", "candidato_legenda", "vagas",          # a era 1933-1992
    "votacao_candidato_uf", "votacao_partido_uf", "detalhe_votacao_uf",
    "candidatos_complementar", "coligacoes",
    "votacao_candidato_munzona", "votacao_partido_munzona",
    "detalhe_votacao_munzona",
    "bens_candidato",
    "perfil_eleitorado",           # centenas de MB por ano
    "contas_candidatos",           # mais de 1 GB por ano; por ultimo
]


def nome_conjunto(url):
    for pedaco, nome in CONJUNTOS.items():
        if pedaco in url:
            return nome
    return None


def peso(conjunto):
    """Posicao do conjunto na ordem de coleta; desconhecido vai para o fim."""
    return PRIORIDADE.index(conjunto) if conjunto in PRIORIDADE \
        else len(PRIORIDADE)


def ano_de(pacote):
    fim = pacote.rsplit("-", 1)[-1]
    return int(fim) if fim.isdigit() and len(fim) == 4 else None


def pacotes_do_ckan():
    """Lista (pacote, ano) dos pacotes de interesse, do mais recente ao antigo."""
    d = comum.pega_json(f"{CKAN}/package_list", tempo=120)
    saida = []
    for p in d["result"]:
        ano = ano_de(p)
        prefixo = p[:-5] if ano else p
        if prefixo in PACOTES or p == "codigos-oficiais-de-uf-e-municipios-" \
                                      "segundo-o-tse-e-o-ibge":
            saida.append((p, ano))
    return sorted(saida, key=lambda x: (-(x[1] or 0), x[0]))


def recursos(pacote):
    d = comum.pega_json(f"{CKAN}/package_show?id={pacote}", tempo=180,
                        aceita_404=True)
    if not d:
        return []
    return [(r.get("url") or "") for r in d["result"]["resources"]]


def pronto(con, conjunto, nome):
    """Esse ano ja foi coletado por INTEIRO?

    A pergunta nao pode ser "existe Parquet na pasta": quando a carga de um ano
    morre no meio - e morreu, por memoria e por encoding - a pasta fica com 5
    dos 29 arquivos, e olhar o disco declara o ano pronto. A lacuna some sem
    aviso: 2016 e 2008 ficaram com um sexto dos candidatos e nada acusou.

    O registro em main.coleta serve de marca de conclusao porque so e gravado
    depois do ultimo CSV do ano. Existe registro -> o ano fechou.
    """
    con.execute(comum.CRIA_COLETA)
    tem = con.execute("""SELECT COUNT(*) FROM main.coleta
                         WHERE fonte = ? AND conjunto = ?""",
                      [FONTE, f"{conjunto}/{nome}"]).fetchall()[0][0]
    if not tem:
        return False
    pasta = os.path.join(comum.PARQUET, FONTE, conjunto, nome)
    arqs = glob_.glob(os.path.join(pasta, "*.parquet"))
    return bool(arqs) and all(comum.parquet_valido(con, a) for a in arqs)


def processa(con, conjunto, nome, url):
    """Baixa um ZIP do TSE e grava UM PARQUET POR CSV de dentro.

    Um por CSV, nao um por ano: o ZIP de um ano traz um arquivo por UF mais o
    BR consolidado, e ler os 28 de uma vez - com union_by_name, que precisa
    inspecionar todos antes de comecar - foi o que estourou a memoria quando a
    maquina estava apertada. Carregando um a um, o pico cai para o tamanho de
    uma UF, a retomada fica fina (nao se perde o ano inteiro por causa do
    ultimo arquivo) e a leitura depois e a mesma coisa, por glob recursivo.
    """
    if pronto(con, conjunto, nome):
        return "pulado"

    zip_local = os.path.join(comum.TMP, f"tse_{conjunto}_{nome}.zip")
    saida = comum.baixa(url, zip_local, aceita_404=True)
    if saida is None:
        return None
    bytes_, sha, _ = saida

    pasta_tmp = os.path.join(comum.TMP, f"tse_{conjunto}_{nome}")
    shutil.rmtree(pasta_tmp, ignore_errors=True)
    os.makedirs(pasta_tmp, exist_ok=True)
    total, obs_geral, gravados = 0, None, 0
    try:
        with zipfile.ZipFile(zip_local) as z:
            # .txt tambem: os pacotes de 1933 a 1992 usam essa extensao, com
            # o mesmo delimitador. Aceitar so .csv fazia o script pular a era
            # inteira dizendo "ZIP sem CSV" - 103 arquivos passando em branco
            csvs = [n for n in z.namelist()
                    if n.lower().endswith((".csv", ".txt"))]
            if not csvs:
                comum.log(f"  {conjunto}/{nome}: ZIP sem CSV nem TXT, pulando")
                return None
            for n in csvs:
                alvo = os.path.join(pasta_tmp, os.path.basename(n))
                with z.open(n) as f, open(alvo, "wb") as w:
                    shutil.copyfileobj(f, w, 1 << 22)
        os.remove(zip_local)

        extraidos = (glob_.glob(os.path.join(pasta_tmp, "*.csv"))
                     + glob_.glob(os.path.join(pasta_tmp, "*.txt")))
        for csv in sorted(extraidos):
            # o sufixo do nome do CSV e a UF (consulta_cand_2026_AC.csv)
            parte = os.path.splitext(os.path.basename(csv))[0].rsplit("_", 1)[-1]
            destino = comum.caminho(FONTE, os.path.join(conjunto, nome),
                                    f"{parte}.parquet")
            if os.path.exists(destino) and comum.parquet_valido(con, destino):
                continue
            linhas, obs = comum.csv_para_parquet(
                con, csv, destino, delim=";", encoding="latin-1")
            total += linhas
            gravados += 1
            obs_geral = obs or obs_geral
            os.remove(csv)
    finally:
        shutil.rmtree(pasta_tmp, ignore_errors=True)
        if os.path.exists(zip_local):
            os.remove(zip_local)

    comum.registra(con, FONTE, f"{conjunto}/{nome}", "*.parquet", url,
                   bytes_, total, sha, obs_geral)
    comum.log(f"  {conjunto}/{nome}: {gravados} arquivos, "
              f"{bytes_ / 1e6:,.1f} MB -> {total:,} linhas"
              + (f"  [{obs_geral}]" if obs_geral else ""))
    return "ok"


def main():
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]
    desde = 0
    if "--desde" in sys.argv:
        desde = int(sys.argv[sys.argv.index("--desde") + 1])

    alvos = []
    for pacote, ano in pacotes_do_ckan():
        if ano and ano < desde:
            continue
        for url in recursos(pacote):
            conjunto = nome_conjunto(url)
            if not conjunto or (so and so != conjunto):
                continue
            alvos.append((conjunto, str(ano) if ano else "completo", url))

    # o mesmo conjunto e ano pode aparecer em mais de um pacote do CKAN
    vistos, unicos = set(), []
    for conjunto, nome, url in alvos:
        if (conjunto, nome) in vistos:
            continue
        vistos.add((conjunto, nome))
        unicos.append((conjunto, nome, url))

    # na ordem de PRIORIDADE e, dentro do conjunto, do ano mais recente para o
    # mais antigo: quem interrompe no meio fica com a parte util
    unicos.sort(key=lambda a: (peso(a[0]),
                               -(int(a[1]) if a[1].isdigit() else 0)))

    if "--listar" in sys.argv:
        for conjunto, nome, url in unicos:
            print(f"{conjunto:<28} {nome:<10} {url}")
        print(f"\n{len(unicos)} arquivos a processar")
        return 0

    con = comum.abre_banco()
    comum.log(f"{len(unicos)} arquivos a processar")
    falhas, feitos = [], 0
    for i, (conjunto, nome, url) in enumerate(unicos, 1):
        try:
            if processa(con, conjunto, nome, url) == "ok":
                feitos += 1
        except Exception as e:
            comum.log(f"!! {conjunto}/{nome} FALHOU: {type(e).__name__}: {e}")
            falhas.append(f"{conjunto}/{nome}")
        if i % 25 == 0:
            comum.log(f"--- progresso: {i}/{len(unicos)}")

    print("\n--- coletado do TSE ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas,
               round(SUM(bytes) / 1e6, 1) AS mb
        FROM main.coleta WHERE fonte = 'tse' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()
    comum.log(f"concluido: {feitos} novos. "
              f"falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
