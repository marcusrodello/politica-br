"""Baixa processos judiciais da API Publica do DataJud (CNJ) e grava em Parquet.

Esta e a unica via legitima para o Judiciario no portal, e a razao esta escrita
aqui para ninguem tentar o caminho curto outra vez:

- O STF NAO PUBLICA DADOS ABERTOS ESTRUTURADOS. O portal de dados abertos
  (portal.stf.jus.br/dadosabertos) e uma aplicacao de pagina unica que nao
  serve JSON para quem chega de fora; o Corte Aberta
  (transparencia.stf.jus.br) e um painel Qlik Sense, cujos numeros so saem por
  engine websocket; e a API de jurisprudencia nao aceita GET. Raspar qualquer
  um dos tres daria um pipeline que quebra no proximo deploy do tribunal.

- O DataJud e a Base Nacional de Processos Judiciais do CNJ, que recebe os
  dados dos proprios tribunais por obrigacao normativa. E a mesma informacao,
  com contrato de API e documentacao.

PRECISA DE CHAVE, e a chave e de quem opera a base: o CNJ descontinuou a chave
publica compartilhada que circulava no tutorial de 2023 (hoje responde 401).
Cadastro gratuito em datajud.cnj.jus.br, em Meu Perfil > API Key. Ponha a chave
na variavel de ambiente POLITICA_BR_DATAJUD_KEY - nunca no codigo, que e
publico.

Uso:  set POLITICA_BR_DATAJUD_KEY=...
      python ingestao/judiciario/datajud.py [--so TRIBUNAL] [--max N]
Retomavel: reexecutar pula o tribunal que ja tem Parquet valido.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ingestao/judiciario/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "judiciario"
API = "https://api-publica.datajud.cnj.jus.br/api_publica_{trib}/_search"
CHAVE = os.environ.get("POLITICA_BR_DATAJUD_KEY", "").strip()
PAGINA = 1000          # teto por requisicao na API publica
PAUSA = 0.3

# os tribunais que o portal usa, e por que
TRIBUNAIS = [
    ("stf", "Supremo Tribunal Federal: controle de constitucionalidade - ADI, "
            "ADPF, ADC - e os processos que decidem a regra do jogo politico"),
    ("stj", "Superior Tribunal de Justica: ultima palavra em lei federal, "
            "inclusive improbidade e crime de agente publico"),
    ("tse", "Tribunal Superior Eleitoral: contencioso eleitoral, registro de "
            "candidatura, cassacao e inelegibilidade"),
]


def consulta(trib, depois=None, tamanho=PAGINA):
    """Uma pagina do indice do tribunal, ordenada para paginar com search_after.

    A ordenacao e obrigatoria e tem de ser estavel: sem ela, duas paginas
    seguidas podem repetir ou pular processo.
    """
    corpo = {"size": tamanho,
             "query": {"match_all": {}},
             "sort": [{"@timestamp": {"order": "asc"}}, {"_id": "asc"}]}
    if depois:
        corpo["search_after"] = depois
    req = urllib.request.Request(
        API.format(trib=trib), data=json.dumps(corpo).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"APIKey {CHAVE}",
                 "Content-Type": "application/json",
                 "User-Agent": comum.AGENTE})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def faz_tribunal(con, trib, motivo, teto):
    destino = comum.caminho(FONTE, trib, "processos.parquet")
    if os.path.exists(destino) and comum.parquet_valido(con, destino):
        comum.log(f"  {trib}: ja existe, pulando")
        return

    tudo, depois, total = [], None, None
    while True:
        try:
            d = consulta(trib, depois)
        except urllib.error.HTTPError as e:
            corpo = e.read(300).decode("utf-8", "replace")
            if e.code == 401:
                raise RuntimeError(
                    "401 do DataJud: chave ausente ou invalida. Gere a sua em "
                    "datajud.cnj.jus.br (Meu Perfil > API Key) e exporte em "
                    "POLITICA_BR_DATAJUD_KEY") from None
            raise RuntimeError(f"HTTP {e.code}: {corpo[:160]}") from None

        if total is None:
            total = d.get("hits", {}).get("total", {}).get("value")
            comum.log(f"  {trib}: {total:,} processos no indice"
                      if total is not None else f"  {trib}: indice aberto")
        itens = d.get("hits", {}).get("hits", [])
        if not itens:
            break
        for h in itens:
            tudo.append(h.get("_source", {}))
        depois = itens[-1].get("sort")
        if not depois:
            break
        if len(tudo) % 10000 < PAGINA:
            comum.log(f"    {len(tudo):,} baixados")
        if teto and len(tudo) >= teto:
            comum.log(f"    teto de {teto:,} alcancado, parando")
            break
        time.sleep(PAUSA)

    if not tudo:
        comum.log(f"  {trib}: nenhum processo retornado")
        return
    import pandas as pd
    df = pd.json_normalize(tudo, sep=".")
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, (list, dict))).any():
            df[c] = df[c].map(lambda v: json.dumps(v, ensure_ascii=False)
                              if isinstance(v, (list, dict)) else v)
    df = df.astype("string")
    con.register("_lote", df)
    con.execute(f"COPY _lote TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_lote")
    obs = motivo + (f"; indice declara {total:,} processos" if total else "")
    if teto and len(tudo) >= teto:
        obs += f"; coleta limitada a {teto:,} por --max"
    comum.registra(con, FONTE, trib, "processos.parquet",
                   API.format(trib=trib), os.path.getsize(destino),
                   len(df), None, obs)
    comum.log(f"  {trib}: {len(df):,} processos, {len(df.columns)} campos")


def main():
    if not CHAVE:
        print(
            "A API Publica do DataJud exige chave, e ela e de quem opera a\n"
            "base: o CNJ descontinuou a chave publica compartilhada que\n"
            "circulava no tutorial de 2023 e hoje ela responde 401.\n\n"
            "  1. cadastro gratuito em https://datajud.cnj.jus.br\n"
            "  2. Meu Perfil > API Key > Gerar Nova Chave\n"
            "  3. exporte em POLITICA_BR_DATAJUD_KEY e rode de novo\n\n"
            "A chave vai na variavel de ambiente, nunca no codigo, que e "
            "publico.")
        return 2

    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]
    teto = None
    if "--max" in sys.argv:
        teto = int(sys.argv[sys.argv.index("--max") + 1])

    con = comum.abre_banco()
    falhas = []
    for trib, motivo in TRIBUNAIS:
        if so and so != trib:
            continue
        comum.log(f"===== {trib} =====")
        try:
            faz_tribunal(con, trib, motivo, teto)
        except Exception as e:
            comum.log(f"!! {trib} FALHOU: {e}")
            falhas.append(trib)

    print("\n--- coletado do Judiciario ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas
        FROM main.coleta WHERE fonte = 'judiciario' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()
    comum.log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
