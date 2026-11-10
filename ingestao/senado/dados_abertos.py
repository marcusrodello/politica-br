"""Baixa os dados abertos do Senado Federal e grava em Parquet.

O Senado nao publica arquivo em lote: tudo vem por API JSON, uma chamada por
ano, por legislatura ou por parlamentar.

ATENCAO AO QUE ESTA DEPRECIADO. A API do Senado tem duas geracoes vivas ao
mesmo tempo. Os endpoints classicos - /materia/pesquisa/lista,
/plenario/lista/votacao, /senador/{cod}/votacoes - trazem no proprio corpo da
resposta um aviso de descontinuacao com DataDesativacaoCompleta em 2026-02-01,
data que JA PASSOU: eles respondem hoje por tolerancia, nao por contrato. Esta
ingestao usa os substitutos indicados pelo proprio portal, /votacao e
/processo, que devolvem JSON plano em vez do envelope herdado do XML.

O que entra:

  LISTAS INTEIRAS
    legislaturas   as legislaturas e suas sessoes legislativas
    partidos       partidos em atividade e extintos
    colegiados     comissoes e demais colegiados em atividade

  POR LEGISLATURA
    senadores      quem exerceu mandato em cada legislatura

  POR PARLAMENTAR
    mandatos       mandatos, com UF e tipo de participacao
    filiacoes      historico de filiacao partidaria - a materia-prima para
                   acompanhar troca de partido ao longo do tempo

  POR ANO
    votacoes       votacoes nominais, com o resultado
    votos          o voto de cada senador em cada votacao
    processos      processos legislativos (o que antes se chamava materia)
    normas         normas juridicas federais

Uso:  python ingestao/senado/dados_abertos.py [--desde ANO] [--so CONJUNTO]
Retomavel: reexecutar pula o que ja tem Parquet valido.
"""
import os
import sys
import time

# ingestao/senado/ -> uma acima, para achar comum.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comum                                                  # noqa: E402

FONTE = "senado"
API = "https://legis.senado.leg.br/dadosabertos"
ANO_FIM = 2026
ANO_LIMITE = 1826
PAUSA = 0.15        # segundos entre chamadas por parlamentar, por educacao

SIMPLES = {
    "legislaturas": "plenario/lista/legislaturas",
    "partidos": "composicao/lista/partidos",
    "colegiados": "comissao/lista/colegiados",
}

ANUAIS = {
    "votacoes": "votacao?ano={ano}",
    "processos": "processo?ano={ano}",
    "normas": "legislacao/lista?ano={ano}",
}

POR_PARLAMENTAR = {
    "mandatos": "senador/{cod}/mandatos",
    "filiacoes": "senador/{cod}/filiacoes",
}

IGNORADAS = ("Metadados", "noNamespaceSchemaLocation")


def desembrulha(no):
    """Desce no envelope do Senado ate a lista de registros.

    Os endpoints da geracao antiga embrulham tudo em camadas herdadas do XML -
    {"ListaLegislatura": {"Metadados": ..., "Legislaturas": {"Legislatura":
    [...]}}} -, e quando ha um unico registro a camada final vem como objeto,
    nao como lista de um. Os endpoints novos ja chegam como lista. Isso resolve
    os tres casos sem o chamador precisar saber qual geracao respondeu.
    """
    if isinstance(no, list):
        return no
    if not isinstance(no, dict):
        return None
    uteis = {k: v for k, v in no.items() if k not in IGNORADAS}
    for v in uteis.values():
        achado = desembrulha(v)
        if achado is not None:
            return achado
    # folha: um registro so, devolvido como objeto
    if uteis and all(not isinstance(v, (dict, list)) for v in uteis.values()):
        return [uteis]
    return None


def achata(registros):
    """Um dicionario por registro, com as chaves aninhadas viradas a.b.c.

    Tudo como texto: o Senado troca o tipo do mesmo campo entre anos, e um
    Parquet com tipo declarado quebraria na leitura do conjunto todo.
    """
    import pandas as pd
    df = pd.json_normalize(registros, sep=".")
    # coluna que ainda contem lista ou dicionario vira JSON em texto, para nao
    # perder o conteudo nem estourar o schema do Parquet
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, (list, dict))).any():
            import json
            df[c] = df[c].map(
                lambda v: json.dumps(v, ensure_ascii=False)
                if isinstance(v, (list, dict)) else v)
    return df.astype("string")


def grava(con, conjunto, nome, url, registros, observacao=None):
    """Grava um Parquet a partir dos registros e anota a coleta."""
    destino = comum.caminho(FONTE, conjunto, f"{nome}.parquet")
    df = achata(registros)
    con.register("_lote", df)
    con.execute(f"COPY _lote TO '{comum.sql(destino)}' "
                f"(FORMAT PARQUET, COMPRESSION ZSTD)")
    con.unregister("_lote")
    comum.registra(con, FONTE, conjunto, f"{nome}.parquet", url,
                   os.path.getsize(destino), len(df), None, observacao)
    comum.log(f"  {conjunto}/{nome}: {len(df):,} registros, "
              f"{len(df.columns)} colunas")
    return len(df)


def existe(con, conjunto, nome):
    destino = comum.caminho(FONTE, conjunto, f"{nome}.parquet")
    return os.path.exists(destino) and comum.parquet_valido(con, destino)


def baixa_lista(caminho):
    """Pega o JSON e devolve a lista de registros, ou [] quando vazio."""
    d = comum.pega_json(f"{API}/{caminho}", tempo=240, aceita_404=True)
    if d is None:
        return []
    return desembrulha(d) or []


# =========================== conjuntos ====================================
def faz_simples(con, conjunto, caminho):
    if existe(con, conjunto, "completo"):
        comum.log(f"  {conjunto}: ja existe, pulando")
        return
    registros = baixa_lista(caminho)
    if registros:
        grava(con, conjunto, "completo", f"{API}/{caminho}", registros)


def faz_anuais(con, conjunto, molde, desde):
    """Desce ano a ano e para em duas respostas vazias seguidas.

    Vazio aqui nao e 404: a API responde 200 com lista vazia para ano sem
    registro, entao o fim da serie se descobre pelo conteudo.
    """
    vazios, achados = 0, []
    for ano in range(ANO_FIM, max(desde, ANO_LIMITE) - 1, -1):
        nome = str(ano)
        if existe(con, conjunto, nome):
            achados.append(ano)
            vazios = 0
            continue
        caminho = molde.format(ano=ano)
        registros = baixa_lista(caminho)
        if not registros:
            vazios += 1
            if vazios >= 2:
                break
            continue
        vazios = 0
        achados.append(ano)
        grava(con, conjunto, nome, f"{API}/{caminho}", registros)

        # as votacoes trazem o voto de cada senador embutido; eles viram
        # conjunto proprio, senao o voto individual ficaria preso num campo
        # de texto JSON dentro da votacao
        if conjunto == "votacoes":
            votos = []
            for v in registros:
                for voto in (v.get("votos") or []):
                    votos.append({**voto,
                                  "codigoSessaoVotacao": v.get("codigoSessaoVotacao"),
                                  "sequencialVotacao": v.get("sequencialVotacao"),
                                  "dataSessao": v.get("dataSessao"),
                                  "identificacao": v.get("identificacao")})
            if votos and not existe(con, "votos", nome):
                grava(con, "votos", nome, f"{API}/{caminho}", votos)
    if achados:
        comum.log(f"{conjunto}: {len(achados)} anos, de {min(achados)} "
                  f"a {max(achados)}")
    else:
        comum.log(f"{conjunto}: nada disponivel")


def codigos_de_senador(con):
    """Codigos de todo senador presente nos arquivos de senadores."""
    pasta = comum.caminho(FONTE, "senadores", "x").rsplit(os.sep, 1)[0]
    alvo = comum.sql(os.path.join(pasta, "*.parquet"))
    try:
        linhas = con.execute(f"""
            SELECT DISTINCT "IdentificacaoParlamentar.CodigoParlamentar" AS cod
            FROM read_parquet('{alvo}', union_by_name=true)
            WHERE cod IS NOT NULL ORDER BY 1
        """).fetchall()
        return [c[0] for c in linhas]
    except Exception as e:
        comum.log(f"  nao foi possivel listar senadores: {type(e).__name__}: {e}")
        return []


def faz_senadores(con, con_legislaturas):
    """Um arquivo por legislatura, da mais recente para a mais antiga."""
    nums = sorted({str(r.get("NumeroLegislatura"))
                   for r in con_legislaturas
                   if r.get("NumeroLegislatura")},
                  key=lambda x: -int(x))
    comum.log(f"  {len(nums)} legislaturas no portal")
    achados = []
    for n in nums:
        if existe(con, "senadores", f"L{n}"):
            achados.append(n)
            continue
        caminho = f"senador/lista/legislatura/{n}"
        registros = baixa_lista(caminho)
        if registros:
            achados.append(n)
            grava(con, "senadores", f"L{n}", f"{API}/{caminho}", registros)
        time.sleep(PAUSA)
    comum.log(f"senadores: {len(achados)} legislaturas com dado")


def faz_por_parlamentar(con, conjunto, molde):
    if existe(con, conjunto, "completo"):
        comum.log(f"  {conjunto}: ja existe, pulando")
        return
    codigos = codigos_de_senador(con)
    if not codigos:
        comum.log(f"  {conjunto}: sem lista de senadores, pulando")
        return
    comum.log(f"  {conjunto}: consultando {len(codigos)} parlamentares")
    tudo, vazios = [], 0
    for i, cod in enumerate(codigos, 1):
        try:
            registros = baixa_lista(molde.format(cod=cod))
        except Exception as e:
            comum.log(f"    {cod}: {type(e).__name__}, seguindo")
            registros = []
        if registros:
            for r in registros:
                r["codigoParlamentar"] = cod
            tudo += registros
        else:
            vazios += 1
        if i % 200 == 0:
            comum.log(f"    {i}/{len(codigos)}, {len(tudo):,} registros")
        time.sleep(PAUSA)
    if tudo:
        grava(con, conjunto, "completo", f"{API}/{molde}", tudo,
              observacao=f"uniao de {len(codigos)} consultas por parlamentar; "
                         f"{vazios} sem registro")


def main():
    desde = ANO_LIMITE
    if "--desde" in sys.argv:
        desde = int(sys.argv[sys.argv.index("--desde") + 1])
    so = None
    if "--so" in sys.argv:
        so = sys.argv[sys.argv.index("--so") + 1]

    con = comum.abre_banco()
    falhas = []

    def tenta(nome, acao):
        if so and so != nome:
            return
        comum.log(f"===== {nome} =====")
        try:
            acao()
        except Exception as e:
            comum.log(f"!! {nome} FALHOU: {type(e).__name__}: {e}")
            falhas.append(nome)

    for conjunto, caminho in SIMPLES.items():
        tenta(conjunto, lambda c=conjunto, p=caminho: faz_simples(con, c, p))

    legislaturas = baixa_lista(SIMPLES["legislaturas"])
    tenta("senadores", lambda: faz_senadores(con, legislaturas))

    for conjunto, molde in POR_PARLAMENTAR.items():
        tenta(conjunto, lambda c=conjunto, m=molde:
              faz_por_parlamentar(con, c, m))

    for conjunto, molde in ANUAIS.items():
        tenta(conjunto, lambda c=conjunto, m=molde:
              faz_anuais(con, c, m, desde))

    print("\n--- coletado do Senado ---")
    print(con.sql("""
        SELECT conjunto, COUNT(*) AS arquivos, SUM(linhas) AS linhas,
               min(baixado_em)::DATE AS coletado_em
        FROM coleta WHERE fonte = 'senado' GROUP BY 1 ORDER BY 3 DESC
    """))
    con.close()
    comum.log(f"concluido. falhas: {falhas if falhas else 'nenhuma'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
