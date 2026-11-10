"""Confere se cada arquivo coletado chegou inteiro, contra o portal de origem.

Um download cortado no meio nao acusa erro: o arquivo existe, abre, e so tem
menos linhas. Na primeira coleta da Camara foi exatamente o que houve com
votacoesVotos-2021, e o CSV pareceu defeituoso na origem quando o problema era
local. Esta conferencia pergunta o tamanho ao portal (HEAD, sem baixar de novo)
e compara com o que ficou registrado em coleta.

Divergencia nao significa necessariamente erro: o portal republica arquivo e o
tamanho muda de verdade. O que ela significa e "este arquivo merece ser baixado
outra vez".

Uso:  python ingestao/confere_coleta.py [fonte]
"""
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import comum                                                  # noqa: E402


def tamanho_remoto(url):
    """Content-Length por HEAD; None quando o portal nao informa."""
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": comum.AGENTE})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            n = r.headers.get("Content-Length")
            return int(n) if n else None
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except Exception as e:
        return type(e).__name__


def main():
    fonte = sys.argv[1] if len(sys.argv) > 1 else None
    con = comum.abre_banco(somente_leitura=True)
    onde = "WHERE fonte = ?" if fonte else ""
    arg = [fonte] if fonte else []
    linhas = con.execute(f"""
        SELECT fonte, conjunto, arquivo, url, bytes, linhas
        FROM coleta {onde} ORDER BY fonte, conjunto, arquivo
    """, arg).fetchall()
    con.close()

    if not linhas:
        print("nada registrado em coleta" + (f" para {fonte}" if fonte else ""))
        return 0

    comum.log(f"conferindo {len(linhas)} arquivos")
    suspeitos, sem_info = [], 0
    for f, conj, arq, url, bytes_, nl in linhas:
        remoto = tamanho_remoto(url)
        if remoto is None:
            sem_info += 1
            continue
        if isinstance(remoto, str):
            suspeitos.append((f, conj, arq, bytes_, remoto, nl))
            print(f"  ?? {f}/{conj}/{arq}: {remoto}")
        elif remoto != bytes_:
            dif = remoto - bytes_
            suspeitos.append((f, conj, arq, bytes_, remoto, nl))
            print(f"  !! {f}/{conj}/{arq}: local {bytes_:,} x portal "
                  f"{remoto:,} ({dif:+,} bytes)")

    print()
    comum.log(f"{len(linhas) - len(suspeitos) - sem_info} iguais, "
              f"{len(suspeitos)} divergentes, {sem_info} sem Content-Length")
    if suspeitos:
        print("\nPara refazer os divergentes, apague o Parquet correspondente em")
        print("dados/parquet/<fonte>/<conjunto>/ e rode a ingestao da fonte.")
    return 1 if suspeitos else 0


if __name__ == "__main__":
    sys.exit(main())
