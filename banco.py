"""Abertura do banco, compartilhada por ingestao e transformacao.

Vive na raiz porque as duas camadas precisam da mesma coisa e nenhuma das duas
deve depender da outra: a ingestao nao e dona da conexao, e a transformacao nao
tem por que importar de dentro de ingestao/.

O TETO DE MEMORIA SE ADAPTA AO QUE A MAQUINA TEM NA HORA. Pedir 6 GB numa
maquina com 2 GB livres nao faz o DuckDB economizar: faz ele aceitar o pedido e
falhar com Allocation failure na primeira alocacao grande. Aconteceu duas vezes
neste projeto - derrubou a coleta de colegiados do Senado e a tabela de despesas
da Camara, 5,2 milhoes de linhas, as duas sem nenhuma relacao com o dado ou com
o portal. Com teto menor o DuckDB desce para a area de descarga em disco e fica
mais lento, o que e um preco melhor que perder o trabalho.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO = os.path.join(BASE, "dados", "politica_br.duckdb")
TMP = os.path.join(BASE, "_tmp")


def sql(p):
    """Caminho do Windows como o DuckDB aceita dentro de uma string SQL."""
    return p.replace("\\", "/")


def memoria_livre_gb():
    """RAM fisica livre, em GB. Devolve None quando nao da para saber."""
    try:
        if sys.platform == "win32":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            s = Status()
            s.dwLength = ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
                return s.ullAvailPhys / 1024 ** 3
        else:
            with open("/proc/meminfo") as fh:
                for linha in fh:
                    if linha.startswith("MemAvailable:"):
                        return int(linha.split()[1]) / 1024 ** 2
    except Exception:
        pass
    return None


def abre(somente_leitura=False, teto_gb=6, schema=None, threads=None,
         silencioso=False):
    """Conexao padrao: teto de memoria adaptativo e descarga em disco.

    schema, quando dado, entra com USE - os scripts de uma fonte trabalham
    dentro do schema dela sem qualificar cada nome.
    """
    import duckdb
    os.makedirs(TMP, exist_ok=True)
    con = duckdb.connect(CAMINHO, read_only=somente_leitura)
    con.execute("SET preserve_insertion_order=false")
    if not somente_leitura:
        livre = memoria_livre_gb()
        gb = teto_gb if livre is None else max(1, min(teto_gb, int(livre - 1)))
        # CADA THREAD TEM SEU BUFFER. Com teto baixo, quatro threads lendo
        # arquivos grandes batem no limite antes de qualquer uma terminar - foi
        # assim que a carga do acervo do TSE falhou em 946 MiB de 953. Uma
        # thread por GB de teto mantem o paralelismo onde ha folga e desiste
        # dele onde nao ha, que e melhor que falhar rapido.
        if threads is None:
            threads = max(1, min(4, gb))
        if livre is not None and gb < teto_gb and not silencioso:
            print(f"memoria livre {livre:.1f} GB; teto do banco em {gb} GB e "
                  f"{threads} thread(s) (descarga em disco cobre o resto)",
                  flush=True)
        con.execute(f"SET memory_limit='{gb}GB'")
        con.execute(f"SET temp_directory='{sql(TMP)}'")
    if threads:
        con.execute(f"SET threads={threads}")
    if schema:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        con.execute(f"USE {schema}")
    return con
