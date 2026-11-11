"""Camada compartilhada das ingestoes: baixar, gravar Parquet, registrar coleta.

Toda fonte do portal passa por aqui, por tres razoes:

1. RASTREABILIDADE. O projeto promete que cada numero chega de volta a fonte
   oficial e a data da coleta. Isso nao se sustenta em memoria: `registra` grava
   em main.coleta a URL, o instante, o tamanho, as linhas e o sha256 de cada
   arquivo que entrou na base.

2. DOWNLOAD QUE NAO MENTE. Baixar direto para o destino final deixa arquivo
   truncado quando a conexao cai, e arquivo truncado so acusa erro muito depois,
   na leitura - o projeto ja levou essa mordida na carga dos boletins de urna.
   Aqui o download vai para um .parcial e so e renomeado quando termina, o que
   torna "o arquivo existe" uma afirmacao confiavel e a ingestao retomavel.

3. OS PORTAIS OFICIAIS CAEM. A API da Camara responde 503 em rajadas e o Senado
   as vezes demora 40s. Toda requisicao tem retry com espera crescente, em vez
   de abortar a ingestao inteira por uma falha momentanea.
"""
import datetime
import gzip
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)            # para achar banco.py na raiz
import banco as _banco              # noqa: E402

PARQUET = os.path.join(BASE, "dados", "parquet")
TMP = _banco.TMP
BANCO = _banco.CAMINHO

AGENTE = ("POLITICA_BR/0.1 (base de dados politicos oficiais; "
          "github.com/marcusrodello/politica-br)")
TENTATIVAS = 4
ESPERA = 6          # segundos; dobra a cada tentativa


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def caminho(fonte, conjunto, arquivo):
    """dados/parquet/<fonte>/<conjunto>/<arquivo>, com a pasta criada."""
    pasta = os.path.join(PARQUET, fonte, conjunto)
    os.makedirs(pasta, exist_ok=True)
    return os.path.join(pasta, arquivo)


def sql(p):
    """Caminho do Windows como o DuckDB aceita dentro de uma string SQL."""
    return p.replace("\\", "/")


# =========================== HTTP =========================================
def _abre(url, tempo):
    req = urllib.request.Request(url, headers={
        "User-Agent": AGENTE,
        "Accept": "application/json, text/csv, application/zip, */*",
        "Accept-Encoding": "gzip, identity"})
    return urllib.request.urlopen(req, timeout=tempo)


def tenta(url, acao, tempo=120, tentativas=TENTATIVAS, aceita_404=False):
    """Executa acao(resposta) com retry e espera crescente.

    404 e tratado a parte: na Camara ele significa "esse ano nao existe", que e
    resposta legitima do portal e nao falha de rede - repetir nao ajuda.
    """
    espera = ESPERA
    for n in range(1, tentativas + 1):
        try:
            with _abre(url, tempo) as r:
                return acao(r)
        except urllib.error.HTTPError as e:
            if e.code == 404 and aceita_404:
                return None
            falha = f"HTTP {e.code}"
        except Exception as e:
            falha = f"{type(e).__name__}: {e}"
        if n == tentativas:
            raise RuntimeError(f"{url} falhou em {tentativas} tentativas: {falha}")
        log(f"  {falha} em {url.rsplit('/', 1)[-1]}; "
            f"tentativa {n + 1}/{tentativas} em {espera}s")
        time.sleep(espera)
        espera *= 2


def baixa(url, destino, tempo=600, aceita_404=False):
    """Baixa para destino, atomicamente. Devolve (bytes, sha256) ou None em 404.

    Se o destino ja existe, nao baixa de novo: a ingestao e retomavel. Quem
    precisa de dado fresco apaga o arquivo - ou a pasta - antes de rodar.
    """
    if os.path.exists(destino):
        tam = os.path.getsize(destino)
        return (tam, _hash_de(destino), True)

    parcial = destino + ".parcial"

    def recebe(r):
        h = hashlib.sha256()
        tam = 0
        gz = r.headers.get("Content-Encoding") == "gzip"
        with open(parcial, "wb") as alvo:
            fonte = gzip.GzipFile(fileobj=r) if gz else r
            while True:
                bloco = fonte.read(1 << 20)
                if not bloco:
                    break
                alvo.write(bloco)
                h.update(bloco)
                tam += len(bloco)
        # CONFERE O TAMANHO. Sem isso uma conexao cortada no meio entrega
        # arquivo incompleto como se estivesse bom, e o estrago aparece longe
        # da causa: na primeira carga da Camara, votacoesVotos-2021 chegou
        # truncado e o CSV pareceu defeituoso na origem - 16 mil votos a menos
        # sem ninguem notar. Falhar aqui deixa o retry refazer o download.
        declarado = r.headers.get("Content-Length")
        if declarado and not gz and int(declarado) != tam:
            raise IOError(f"download incompleto: {tam} de {declarado} bytes")
        return tam, h.hexdigest()

    saida = tenta(url, recebe, tempo=tempo, aceita_404=aceita_404)
    if saida is None:
        if os.path.exists(parcial):
            os.remove(parcial)
        return None
    os.replace(parcial, destino)      # so agora o arquivo passa a existir
    return (*saida, False)


def pega_json(url, tempo=120, aceita_404=False):
    """GET que devolve o JSON decodificado, com retry e gzip transparente."""
    def recebe(r):
        bruto = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            bruto = gzip.GzipFile(fileobj=io.BytesIO(bruto)).read()
        return json.loads(bruto.decode("utf-8", "replace"))
    return tenta(url, recebe, tempo=tempo, aceita_404=aceita_404)


def _hash_de(arquivo):
    h = hashlib.sha256()
    with open(arquivo, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


# =========================== registro de coleta ===========================
# main.coleta, sempre qualificada: cada fonte vive no seu schema e os scripts
# de transformacao usam USE <fonte>, entao um nome solto aqui criaria uma tabela
# coleta dentro do schema da vez e o registro de procedencia se espalharia.
CRIA_COLETA = """
CREATE TABLE IF NOT EXISTS main.coleta (
  fonte VARCHAR, conjunto VARCHAR, arquivo VARCHAR, url VARCHAR,
  baixado_em TIMESTAMP, bytes BIGINT, linhas BIGINT, sha256 VARCHAR,
  observacao VARCHAR
)
"""


def registra(con, fonte, conjunto, arquivo, url, bytes_, linhas, sha256,
             observacao=None):
    """Anota (ou atualiza) a coleta de um arquivo no registro do banco."""
    con.execute(CRIA_COLETA)
    tem = con.execute("""SELECT COUNT(*) FROM duckdb_columns()
                         WHERE schema_name = 'main' AND table_name = 'coleta'
                           AND column_name = 'observacao'""").fetchall()[0][0]
    if not tem:            # banco criado antes da coluna existir
        con.execute("ALTER TABLE main.coleta ADD COLUMN observacao VARCHAR")
    con.execute("""DELETE FROM main.coleta
                   WHERE fonte = ? AND conjunto = ? AND arquivo = ?""",
                [fonte, conjunto, arquivo])
    con.execute("""INSERT INTO main.coleta VALUES (?,?,?,?,?,?,?,?,?)""",
                [fonte, conjunto, arquivo, url, datetime.datetime.now(),
                 bytes_, linhas, sha256, observacao])


def abre_banco(somente_leitura=False, teto_gb=6):
    """Conexao padrao, delegada ao modulo banco da raiz.

    A abertura vive em banco.py porque transformacao precisa dela igual e nao
    deve importar de dentro de ingestao/. Aqui fica so o apelido que os
    modulos de ingestao ja usam.
    """
    return _banco.abre(somente_leitura=somente_leitura, teto_gb=teto_gb)


memoria_livre_gb = _banco.memoria_livre_gb


# =========================== CSV -> Parquet ===============================
def _copia(con, csv, destino, selecao, filtro, delim, encoding, extra,
           tolerante=False):
    """O COPY em si, isolado para poder rodar sobre outro arquivo e encoding.

    all_varchar=true de proposito: deixar o DuckDB inferir tipo varrendo o
    arquivo e o que estoura a memoria nos CSVs grandes, e um campo que muda de
    formato no meio do arquivo derruba a carga inteira. O preco e declarar o
    tipo na selecao, onde ele fica explicito e versionado.

    strict_mode=false aceita aspas sem fechar; null_padding completa com NULL a
    linha que vem cortada no meio, preservando os campos que ela tem.
    """
    modo = ", strict_mode=false, null_padding=true" if tolerante else ""
    con.execute(f"""
        COPY (
          SELECT {selecao}
          FROM read_csv('{sql(csv)}', delim='{delim}', header=true,
                        encoding='{encoding}', quote='"', all_varchar=true
                        {modo}{extra})
          {filtro}
        ) TO '{sql(destino)}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """)
    return con.sql(
        f"SELECT COUNT(*) FROM read_parquet('{sql(destino)}')").fetchall()[0][0]


def _conta_defeitos(con, csv, delim, encoding, extra):
    """Quantas linhas do CSV violam o padrao, pelo registro do DuckDB.

    Serve para a observacao dizer o tamanho do problema em vez de so avisar que
    existe: sem esse numero, "lido em modo tolerante" pode significar uma linha
    cortada ou um arquivo inteiro corrompido.
    """
    try:
        con.execute("DROP TABLE IF EXISTS rejeito_erros")
        con.execute("DROP TABLE IF EXISTS rejeito_scans")
        # .fetchall() e obrigatorio: um resultado pendente trava a conexao para
        # a consulta seguinte, que e justamente a dos rejeitos
        con.sql(f"""
            SELECT COUNT(*) FROM read_csv('{sql(csv)}', delim='{delim}',
                   header=true, encoding='{encoding}', quote='"',
                   all_varchar=true, ignore_errors=true,
                   store_rejects=true, rejects_table='rejeito_erros',
                   rejects_scan='rejeito_scans'{extra})""").fetchall()
        erros = con.sql("""SELECT line, error_type FROM rejeito_erros
                           ORDER BY line""").fetchall()
        con.execute("DROP TABLE IF EXISTS rejeito_erros")
        con.execute("DROP TABLE IF EXISTS rejeito_scans")
        tipos = sorted({e[1] for e in erros})
        quais = ", ".join(str(e[0]) for e in erros[:5])
        if len(erros) > 5:
            quais += ", ..."
        return len(erros), f"{quais} [{'; '.join(tipos)}]"
    except Exception as e:
        log(f"  (nao foi possivel medir os defeitos: {type(e).__name__})")
        return None, None


def _recodifica_cp1252(csv):
    """Reescreve o CSV de CP1252 para UTF-8 num arquivo ao lado.

    Parte dos arquivos do TSE e CP1252 (Windows-1252), nao ISO-8859-1: usam os
    bytes 0x80 a 0x9F, que o latin-1 estrito do DuckDB recusa - "File is not
    latin-1 encoded" - e que ele nao sabe ler, porque so aceita utf-8, utf-16 e
    latin-1. Recodificar e o unico caminho que preserva o acento: forcar a
    leitura como latin-1 transformaria 0x93 em caractere de controle no meio do
    nome do candidato.
    """
    convertido = csv + ".utf8"
    with open(csv, "rb") as origem, open(convertido, "wb") as alvo:
        while True:
            bloco = origem.read(1 << 22)
            if not bloco:
                break
            # CP1252 tem um byte por caractere, entao cortar em blocos nao
            # parte caractere no meio
            alvo.write(bloco.decode("cp1252", "replace").encode("utf-8"))
    return convertido


def csv_para_parquet(con, csv, destino, selecao="*", onde=None, delim=";",
                     encoding="utf-8", extra=""):
    """Converte CSV em Parquet, lendo tudo como texto e convertendo na selecao.

    Devolve (linhas, observacao). A observacao e None quando o arquivo obedeceu
    ao declarado, e traz o motivo quando foi preciso desviar - encoding
    diferente do esperado, ou linha fora do padrao CSV. Isso vai para
    main.coleta: carga que entrou por caminho diferente nao pode ficar
    indistinguivel das outras.
    """
    filtro = f"WHERE {onde}" if onde else ""

    def copia(enc, tolerante=False, arquivo=None):
        return _copia(con, arquivo or csv, destino, selecao, filtro, delim,
                      enc, extra, tolerante)

    # 1. o encoding declarado
    try:
        return copia(encoding), None
    except Exception as e:
        erro = e

    msg = str(erro)
    problema_de_encoding = ("Invalid unicode" in msg
                            or ("encoded" in msg and "not" in msg))

    # 2. o outro encoding comum, quando o problema e de encoding
    if problema_de_encoding:
        for alternativo in ("utf-8", "latin-1"):
            if alternativo == encoding:
                continue
            try:
                n = copia(alternativo)
                log(f"  nao era {encoding}; lido como {alternativo}")
                return n, (f"declarado {encoding}, lido como {alternativo}: "
                           f"o portal mistura encoding entre anos")
            except Exception:
                pass

        # 3. CP1252: recodifica e carrega do arquivo convertido
        convertido = _recodifica_cp1252(csv)
        try:
            n = copia("utf-8", arquivo=convertido)
        finally:
            os.remove(convertido)
        log(f"  nao era {encoding} nem utf-8; recodificado de cp1252")
        return n, ("arquivo em CP1252, que o DuckDB nao le: recodificado para "
                   "UTF-8 na carga, preservando os acentos")

    # 4. linha fora do padrao CSV: mede o estrago e rele em modo tolerante
    if "CSV Error" not in msg:
        raise erro
    n_def, quais = _conta_defeitos(con, csv, delim, encoding, extra)
    quantas = "indeterminadas" if n_def is None else str(n_def)
    onde_txt = f" (linha {quais})" if quais else ""
    log(f"  CSV fora do padrao: {quantas} linha(s){onde_txt}; "
        f"relendo em modo tolerante")
    return copia(encoding, tolerante=True), (
        f"{quantas} linha(s) fora do padrao CSV{onde_txt}; lido com "
        f"strict_mode=false e null_padding=true, sem descartar linha")



def linhas_parquet(con, destino):
    try:
        return con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{sql(destino)}')").fetchall()[0][0]
    except Exception:
        return None


def parquet_valido(con, destino):
    """Parquet truncado nao da erro ao existir, so na leitura - por isso le."""
    return linhas_parquet(con, destino) is not None


def grava_parquet(con, registros, destino, colunas):
    """Grava uma lista de dicionarios como Parquet, pelas colunas declaradas.

    Usado nas fontes de API, onde o dado chega em JSON: as colunas vem
    declaradas para o schema do Parquet nao mudar quando um campo faltar numa
    resposta.
    """
    import pandas as pd
    df = pd.DataFrame(registros, columns=colunas).astype("string")
    con.register("_lote", df)
    con.execute(f"COPY _lote TO '{sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_lote")
    return len(df)
