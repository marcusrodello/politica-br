"""Baixa os dados abertos da Camara dos Deputados e grava em Parquet.

Pela via dos ARQUIVOS EM LOTE (dadosabertos.camara.leg.br/arquivos), nao pela
API v2: a API responde 503 em rajadas e exigiria dezenas de milhares de
requisicoes paginadas para o mesmo conteudo que vem num CSV por ano. Os
arquivos em lote sao o retrato oficial do dia, publicados pela propria Camara.

O que entra:

  CONJUNTOS INTEIROS (um arquivo, todo o historico)
    deputados             todo deputado que ja exerceu mandato, com CPF
    partidos              partidos registrados
    legislaturas          as legislaturas e o ano de eleicao de cada uma
    orgaos                comissoes, mesa, plenario e afins
    frentes               frentes parlamentares
    frentesDeputados      quem compoe cada frente
    deputadosOcupacoes    ocupacao declarada fora da politica
    deputadosProfissoes   profissao declarada

  POR ANO (1934 ate hoje, conforme o conjunto)
    proposicoes           projetos, emendas, requerimentos
    proposicoesAutores    autoria, que liga proposicao a deputado
    proposicoesTemas      classificacao tematica
    votacoes              cada votacao nominal
    votacoesVotos         o voto de cada deputado em cada votacao
    votacoesObjetos       o que foi votado em cada votacao
    eventos               sessoes e reunioes

  POR LEGISLATURA
    orgaosDeputados       quem ocupou qual cargo em qual orgao

  COTA PARLAMENTAR (camara.leg.br/cotas, ZIP por ano)
    despesas              a cota para exercicio da atividade parlamentar

Os conjuntos nao tem a mesma cobertura temporal: votacoesVotos comeca em 2003,
proposicoes vai muito mais fundo. Em vez de cravar o inicio de cada um na mao,
o script desce ano a ano e para quando o portal responde 404 duas vezes
seguidas - e registra o alcance que encontrou.

Uso:  python ingestao/camara/dados_abertos.py [--desde ANO] [--so CONJUNTO]
Retomavel: reexecutar pula o que ja tem Parquet valido.
"""
import os
import sys
import zipfile

# ingestao/camara/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "camara"
ARQUIVOS = "https://dadosabertos.camara.leg.br/arquivos"
COTAS = "https://www.camara.leg.br/cotas"

# conjuntos de arquivo unico
INTEIROS = ["deputados", "partidos", "legislaturas", "orgaos", "frentes",
            "frentesDeputados", "deputadosOcupacoes", "deputadosProfissoes"]

# conjuntos com um arquivo por ano
ANUAIS = ["proposicoes", "proposicoesAutores", "proposicoesTemas",
          "votacoes", "votacoesVotos", "votacoesObjetos", "eventos"]

# conjuntos com um arquivo por legislatura
POR_LEGISLATURA = ["orgaosDeputados"]

ANO_FIM = 2026
ANO_LIMITE = 1826          # a 1a legislatura comeca em 1826, e o portal tem
                           # proposicao do Imperio; o limite so evita loop sem fim
LEGISLATURAS = range(52, 59)   # 52 (2003) ate 58 (eleita em 2026)


def url_ano(conjunto, ano):
    return f"{ARQUIVOS}/{conjunto}/csv/{conjunto}-{ano}.csv"


def url_inteiro(conjunto):
    return f"{ARQUIVOS}/{conjunto}/csv/{conjunto}.csv"


def url_legislatura(conjunto, n):
    return f"{ARQUIVOS}/{conjunto}/csv/{conjunto}-L{n}.csv"


def processa(con, conjunto, nome, url, aceita_404=False):
    """Baixa um CSV, converte em Parquet e registra a coleta.

    Devolve 'ok', 'pulado' ou None quando o portal nao tem esse arquivo.
    """
    destino = comum.caminho(FONTE, conjunto, f"{nome}.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        return "pulado"

    csv = os.path.join(comum.TMP, f"{FONTE}_{conjunto}_{nome}.csv")
    saida = comum.baixa(url, csv, aceita_404=aceita_404)
    if saida is None:
        return None
    bytes_, sha, _ = saida

    linhas, obs = comum.csv_para_parquet(con, csv, destino, delim=";",
                                         encoding="utf-8")
    os.remove(csv)
    comum.registra(con, FONTE, conjunto, f"{nome}.parquet", url,
                   bytes_, linhas, sha, obs)
    comum.log(f"  {conjunto}/{nome}: {bytes_ / 1e6:,.1f} MB -> {linhas:,} linhas"
              + (f"  [{obs}]" if obs else ""))
    return "ok"


def processa_cota(con, ano):
    """A cota parlamentar vem zipada e com um CSV dentro."""
    conjunto, nome = "despesas", str(ano)
    destino = comum.caminho(FONTE, conjunto, f"{nome}.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        return "pulado"

    url = f"{COTAS}/Ano-{ano}.csv.zip"
    zip_local = os.path.join(comum.TMP, f"cota_{ano}.zip")
    saida = comum.baixa(url, zip_local, aceita_404=True)
    if saida is None:
        return None
    bytes_, sha, _ = saida

    csv = os.path.join(comum.TMP, f"cota_{ano}.csv")
    with zipfile.ZipFile(zip_local) as z:
        dentro = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(dentro) as f, open(csv, "wb") as alvo:
            while True:
                bloco = f.read(1 << 22)
                if not bloco:
                    break
                alvo.write(bloco)
    os.remove(zip_local)

    linhas, obs = comum.csv_para_parquet(con, csv, destino, delim=";",
                                         encoding="utf-8")
    os.remove(csv)
    comum.registra(con, FONTE, conjunto, f"{nome}.parquet", url,
                   bytes_, linhas, sha, obs)
    comum.log(f"  despesas/{ano}: {bytes_ / 1e6:,.1f} MB -> {linhas:,} linhas"
              + (f"  [{obs}]" if obs else ""))
    return "ok"


def desce_anos(con, conjunto, desde):
    """Desce ano a ano a partir de ANO_FIM e para em duas ausencias seguidas.

    Duas, e nao uma: um ano sem arquivo no meio da serie e possivel, e abortar
    na primeira falta encurtaria a serie sem motivo.
    """
    faltas, achados = 0, []
    for ano in range(ANO_FIM, max(desde, ANO_LIMITE) - 1, -1):
        r = processa(con, conjunto, str(ano), url_ano(conjunto, ano),
                     aceita_404=True)
        if r is None:
            faltas += 1
            if faltas >= 2:
                break
        else:
            faltas = 0
            achados.append(ano)
    if achados:
        comum.log(f"{conjunto}: {len(achados)} anos, de {min(achados)} "
                  f"a {max(achados)}")
    else:
        comum.log(f"{conjunto}: nenhum ano disponivel")
    return achados


def main():
    desde = ANO_LIMITE
    if "--desde" in sys.argv:
        desde = int(sys.argv[sys.argv.index("--desde") + 1])
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]

    con = comum.abre_banco()
    falhas = []

    def tenta_conjunto(nome, acao):
        if so and so != nome:
            return
        comum.log(f"===== {nome} =====")
        try:
            acao()
        except Exception as e:
            comum.log(f"!! {nome} FALHOU: {type(e).__name__}: {e}")
            falhas.append(nome)

    for conjunto in INTEIROS:
        tenta_conjunto(conjunto, lambda c=conjunto: processa(
            con, c, "completo", url_inteiro(c)))

    for conjunto in ANUAIS:
        tenta_conjunto(conjunto, lambda c=conjunto: desce_anos(con, c, desde))

    for conjunto in POR_LEGISLATURA:
        def legs(c=conjunto):
            for n in LEGISLATURAS:
                processa(con, c, f"L{n}", url_legislatura(c, n),
                         aceita_404=True)
        tenta_conjunto(conjunto, legs)

    def cotas():
        for ano in range(ANO_FIM, max(desde, 2008) - 1, -1):
            processa_cota(con, ano)
    tenta_conjunto("despesas", cotas)

    print("\n--- coletado da Camara ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas,
               round(SUM(bytes) / 1e6, 1) AS mb,
               min(baixado_em)::DATE AS coletado_em
        FROM coleta WHERE fonte = 'camara' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()

    comum.log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
