"""Estima a matriz de fluxo de votos entre o 1o e o 2o turno de 2026.

Metodo: regressao ecologica com restricao de simplex, no nivel do LOCAL DE
VOTACAO, estimada DENTRO DE CADA UF. Para cada rotulo de origem i do 1o turno e
destino j do 2o turno:

    y_lj = SUM_i beta_ij * x_li + erro_l

x_li e a fracao dos eleitores aptos do local l que escolheu i no 1o turno e
y_lj a fracao que escolheu j no 2o. Os dois usam o MESMO denominador - os aptos
do local no 1o turno -, o que e legitimo porque o eleitorado do local quase nao
muda entre turnos: 72% dos locais tem numero identico de aptos, 99,7% variam
menos de 1% e o total nacional dos locais pareados e igual nos dois turnos.

Restricoes: beta >= 0 e cada LINHA soma 1, isto e, todo eleitor de i foi para
algum destino j. Abstencao e branco/nulo sao rotulos como os outros, nos dois
lados, por isso o sistema fecha. A ponderacao e pelos aptos do local, porque a
variancia de uma fracao cai com o tamanho do denominador.

POR QUE DENTRO DA UF, e nao no pais inteiro de uma vez: uma unica regressao
nacional supoe que o eleitor de um candidato se comporta igual em Roraima e no
Parana. Quando esse molde nao cabe, o estimador nao erra pouco em tudo - ele
foge para os vertices e crava 0% ou 100% com intervalo de confianca estreito. Na
pratica: 27 das 50 celulas da matriz nacional direta ficam coladas em 0 ou 1,
contra 2 quando a estimativa respeita a UF. O numero nacional publicado e a
media das 27 matrizes estaduais, ponderada pelos eleitores de cada origem. A
matriz nacional direta fica gravada como BRASIL_DIRETO, para comparacao.

O solver e gradiente projetado acelerado (FISTA com projecao no simplex por
linha). O problema inteiro cabe em duas matrizes de momento - A, de origem por
origem, e B, de origem por destino -, entao o custo do solver nao depende do
numero de locais, o que torna o bootstrap barato.

O intervalo publicado vem de bootstrap por MUNICIPIO, nao por local: locais do
mesmo municipio se parecem, e reamostrar local a local trataria 94 mil
observacoes como independentes e estreitaria o intervalo artificialmente. Cada
replica reamostra os municipios dentro de cada UF e refaz as 27 matrizes e a
media nacional, para o intervalo nacional carregar tambem a incerteza da
composicao entre estados.

O QUE O RESULTADO NAO E: migracao individual medida, e nem fluxo bruto. Com dado
agregado, dois movimentos opostos que se cancelam dentro do mesmo local sao
invisiveis - e a falacia ecologica, discutida em
docs/tse-2026-migracao-votos.md. O que sai daqui e o fluxo LIQUIDO: o menor
remanejamento de votos compativel com o que cada local registrou nos dois
turnos. A lealdade estimada e, por isso, um teto, e a troca entre candidatos um
piso.

Uso:  python transformacao/tse/estima_fluxo.py
"""
import os
import sys
import time

import numpy as np
import duckdb

# raiz do repositorio, derivada do proprio arquivo: transformacao/tse/ -> duas acima
BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")

# rotulo com menos que isso dos aptos entra no agregado OUTROS: abaixo desse
# ponto a coluna da regressao e quase constante entre locais e o coeficiente
# nao se identifica.
LIMIAR_ROTULO = 0.002
MIN_LOCAIS = 50       # abaixo disso a UF nao sustenta a regressao (ZZ, exterior)
MIN_CLUSTERS = 20     # menos clusters que isso: bootstrap desce para a zona
REPLICAS = 150        # replicas do bootstrap
ITER_PONTO = 4000     # iteracoes do solver na estimativa publicada
ITER_BOOT = 1500      # idem nas replicas, onde a precisao exigida e menor
SEMENTE = 20261025    # data do 2o turno, para o bootstrap ser reproduzivel


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# =========================== solver =======================================
def projeta_simplex(V):
    """Projeta cada linha de V no simplex (soma 1, nao negativa).

    Euclidiana, pelo algoritmo de Duchi et al. (2008): ordena a linha, acha
    quantas coordenadas sobrevivem e desloca todas pelo mesmo theta.
    """
    U = -np.sort(-V, axis=1)
    acum = np.cumsum(U, axis=1) - 1.0
    k = np.arange(1, V.shape[1] + 1)
    rho = (U - acum / k > 0).sum(axis=1)
    theta = acum[np.arange(V.shape[0]), rho - 1] / rho
    return np.maximum(V - theta[:, None], 0.0)


def resolve(A, B, iteracoes=ITER_PONTO):
    """Minimiza tr(b'Ab) - 2tr(b'B) sobre o produto de simplexes por linha.

    Equivale a minimos quadrados ponderados nas fracoes, porque A e B sao as
    matrizes de momento dos dados. FISTA com reinicio quando o passo piora o
    objetivo - sem o reinicio a extrapolacao oscila perto da fronteira.
    """
    maior = np.linalg.eigvalsh(A)[-1]
    if maior <= 0:
        return np.full(B.shape, np.nan)
    passo = 1.0 / (2.0 * maior)

    def objetivo(b):
        return float(np.trace(b.T @ A @ b) - 2.0 * np.trace(b.T @ B))

    b = np.full(B.shape, 1.0 / B.shape[1])
    extrap, t, f_ant = b, 1.0, objetivo(b)
    for _ in range(iteracoes):
        b_novo = projeta_simplex(extrap - passo * 2.0 * (A @ extrap - B))
        f_novo = objetivo(b_novo)
        if f_novo > f_ant:                 # reinicio: volta ao gradiente simples
            b_novo = projeta_simplex(b - passo * 2.0 * (A @ b - B))
            f_novo, t = objetivo(b_novo), 1.0
        t_novo = (1.0 + np.sqrt(1.0 + 4.0 * t * t)) / 2.0
        extrap = b_novo + ((t - 1.0) / t_novo) * (b_novo - b)
        b, t, f_ant = b_novo, t_novo, f_novo
    return b


def momentos(X, Y, peso):
    """Matrizes de momento ponderadas da regressao: A (k x k) e B (k x m)."""
    Xp = X * peso[:, None]
    return Xp.T @ X, Xp.T @ Y


def media_ponderada(betas, origem):
    """Agrega matrizes de escopos menores pelos eleitores de origem de cada um.

    betas e origem vem na mesma ordem. Origem sem nenhum eleitor no conjunto
    (candidato que nao concorreu ali) sai como NaN, nao como fracao inventada.
    """
    num = sum(np.nan_to_num(b) * o[:, None] for b, o in zip(betas, origem))
    tot = num.sum(axis=1, keepdims=True)
    return np.where(tot > 0, num / np.where(tot > 0, tot, 1.0), np.nan)


# =========================== carga ========================================
def rotulos(con, cargo, uf=None):
    """Separa os rotulos em origens (1o turno) e destinos (2o), agregando os
    pequenos em OUTROS.

    Para Presidente o conjunto e nacional e vale para todos os escopos, para as
    matrizes das UFs serem comparaveis entre si. Para Governador tem de ser por
    UF: cada estado disputou entre candidatos proprios, e um conjunto nacional
    misturaria nomes que nunca estiveram na mesma urna.
    """
    onde = "cargo = ?" + (" AND uf = ?" if uf else "")
    arg = [cargo] + ([uf] if uf else [])
    tot = con.execute(f"""
        SELECT rotulo,
               SUM(votos) FILTER (turno = 1) AS t1,
               SUM(votos) FILTER (turno = 2) AS t2,
               SUM(votos) FILTER (turno = 1)
                 / (SELECT SUM(votos) FROM fluxo_insumo
                    WHERE {onde} AND turno = 1)::DOUBLE AS fr1
        FROM fluxo_insumo WHERE {onde}
        GROUP BY 1 ORDER BY 2 DESC NULLS LAST
    """, arg + arg).fetchall()

    origens = [r[0] for r in tot if r[1] and r[3] >= LIMIAR_ROTULO]
    miudos = [r[0] for r in tot if r[1] and r[3] < LIMIAR_ROTULO]
    destinos = [r[0] for r in tot if r[2]]
    if miudos:
        origens.append("OUTROS")
    return origens, destinos, miudos


def caso(rotulo_sql, lista, miudos):
    """Monta o CASE que mapeia rotulo cru para rotulo do modelo."""
    if not miudos:
        return rotulo_sql
    aceitos = ", ".join(f"'{r}'" for r in lista if r != "OUTROS")
    return f"CASE WHEN {rotulo_sql} IN ({aceitos}) THEN {rotulo_sql} ELSE 'OUTROS' END"


def carrega(con, cargo, uf=None):
    """Uma linha por local pareado, com as fracoes de origem e de destino.

    Pareia o local nos dois turnos pela chave (uf, municipio, zona, local): a
    secao nao serve de chave porque o agrupamento de secoes agregadas muda entre
    os turnos. Local sem par - um em 94.709 na eleicao presidencial - fica de
    fora, porque nao ha de onde nem para onde estimar fluxo.
    """
    origens, destinos, miudos = rotulos(con, cargo, uf)
    if len(destinos) < 2:
        return None
    g = caso("rotulo", origens, miudos)

    col_o = ",\n".join(
        f"SUM(votos) FILTER (turno = 1 AND g = '{r}') AS o{i}"
        for i, r in enumerate(origens))
    col_d = ",\n".join(
        f"SUM(votos) FILTER (turno = 2 AND g = '{r}') AS d{i}"
        for i, r in enumerate(destinos))
    arg = ([cargo, cargo] + ([uf] if uf else [])
           + [cargo] + ([uf] if uf else []))

    df = con.execute(f"""
        WITH par AS (
          SELECT a.uf, a.cd_municipio, a.zona, a.local_votacao, a.aptos
          FROM local a JOIN local b USING (uf, cd_municipio, zona, local_votacao)
          WHERE a.cargo = ? AND a.turno = 1 AND b.cargo = ? AND b.turno = 2
                {"AND a.uf = ?" if uf else ""}
        ), v AS (
          SELECT uf, cd_municipio, zona, local_votacao, turno, {g} AS g,
                 SUM(votos) AS votos
          FROM fluxo_insumo WHERE cargo = ? {"AND uf = ?" if uf else ""}
          GROUP BY ALL
        )
        SELECT p.uf, p.cd_municipio, p.zona, p.aptos, {col_o}, {col_d}
        FROM par p JOIN v USING (uf, cd_municipio, zona, local_votacao)
        GROUP BY p.uf, p.cd_municipio, p.zona, p.local_votacao, p.aptos
    """, arg).df()

    aptos = df["aptos"].to_numpy(dtype=np.float64)
    bruto_o = np.nan_to_num(
        df[[f"o{i}" for i in range(len(origens))]].to_numpy(dtype=np.float64))
    bruto_d = np.nan_to_num(
        df[[f"d{i}" for i in range(len(destinos))]].to_numpy(dtype=np.float64))
    chave = df["uf"].astype(str) + "/" + df["cd_municipio"].astype(str)
    _, municipio = np.unique(chave, return_inverse=True)
    _, zona = np.unique(chave + "/" + df["zona"].astype(str), return_inverse=True)
    return dict(origens=origens, destinos=destinos, miudos=miudos,
                X=bruto_o / aptos[:, None], Y=bruto_d / aptos[:, None],
                aptos=aptos, bruto_o=bruto_o, bruto_d=bruto_d,
                uf=df["uf"].to_numpy(), municipio=municipio, zona=zona)


# =========================== estimacao ====================================
def blocos(d, por_uf):
    """Fatia os dados nos conjuntos em que a regressao vai rodar.

    por_uf=True: um bloco por UF com locais suficientes. por_uf=False: um bloco
    unico com tudo (usado na matriz BRASIL_DIRETO e nas UFs de Governador, que
    ja vem carregadas uma por vez).
    """
    if not por_uf:
        nomes = [None]
        mascaras = [np.ones(len(d["X"]), dtype=bool)]
    else:
        nomes, mascaras = [], []
        for uf in sorted(set(d["uf"])):
            m = d["uf"] == uf
            if m.sum() >= MIN_LOCAIS:
                nomes.append(uf)
                mascaras.append(m)
    saida = []
    for nome, m in zip(nomes, mascaras):
        _, mun = np.unique(d["municipio"][m], return_inverse=True)
        # o cluster do bootstrap e o municipio, mas no DF o municipio e unico:
        # reamostrar um cluster so devolveria sempre a mesma amostra e um
        # intervalo de largura zero. Nesse caso desce para a zona eleitoral.
        cluster, nivel = mun, "municipio"
        if mun.max() + 1 < MIN_CLUSTERS:
            _, cluster = np.unique(d["zona"][m], return_inverse=True)
            nivel = "zona"
        saida.append(dict(nome=nome, X=d["X"][m], Y=d["Y"][m], w=d["aptos"][m],
                          mun=cluster, n_mun=int(cluster.max() + 1), nivel=nivel,
                          municipios=int(mun.max() + 1),
                          origem=d["bruto_o"][m].sum(axis=0), locais=int(m.sum())))
    return saida


def estima(d, por_uf=True, com_media=True, replicas=REPLICAS):
    """Estima a matriz de cada bloco e, se pedido, a media ponderada deles.

    Devolve (pontos, faixas) indexados pelo nome do bloco, mais a chave 'MEDIA'
    quando com_media. Uma unica passada de bootstrap serve os dois niveis: a
    replica reamostra os municipios de cada bloco e reconstroi tambem a media,
    para o intervalo agregado incluir a incerteza da composicao entre blocos.
    """
    bl = blocos(d, por_uf)

    def rodada(contagens, iteracoes):
        betas = []
        for b, conta in zip(bl, contagens):
            peso = b["w"] if conta is None else b["w"] * conta[b["mun"]]
            A, B = momentos(b["X"], b["Y"], peso)
            betas.append(resolve(A, B, iteracoes))
        return betas

    pontos = rodada([None] * len(bl), ITER_PONTO)
    saida = {b["nome"]: p for b, p in zip(bl, pontos)}
    if com_media:
        saida["MEDIA"] = media_ponderada(pontos, [b["origem"] for b in bl])

    if not replicas:
        return saida, None, bl

    rng = np.random.default_rng(SEMENTE)
    pilha = {k: [] for k in saida}
    for _ in range(replicas):
        contagens = [rng.multinomial(b["n_mun"], np.full(b["n_mun"], 1.0 / b["n_mun"]))
                     for b in bl]
        betas = rodada(contagens, ITER_BOOT)
        for b, beta in zip(bl, betas):
            pilha[b["nome"]].append(beta)
        if com_media:
            # a composicao entre blocos tambem e reamostrada: o peso de cada
            # bloco na media acompanha os municipios que a replica sorteou
            origem_r = [(b["X"] * (b["w"] * c[b["mun"]])[:, None]).sum(axis=0)
                        for b, c in zip(bl, contagens)]
            pilha["MEDIA"].append(media_ponderada(betas, origem_r))
    faixas = {}
    for k, v in pilha.items():
        lo, hi = np.nanpercentile(np.array(v), [2.5, 97.5], axis=0)
        # a faixa precisa conter a estimativa publicada. Em celula mal
        # identificada - fluxo de poucos milhares de eleitores, onde o dado nao
        # decide nada - o percentil do bootstrap as vezes cai todo de um lado do
        # ponto, e sair uma tabela dizendo "616 eleitores, faixa de 3.040 a
        # 8.891" parece erro de conta. Alargar e honesto; estreitar nunca.
        faixas[k] = np.array([np.minimum(lo, saida[k]),
                              np.maximum(hi, saida[k])])
    return saida, faixas, bl


def ajuste(X, Y, w, beta):
    """R2 ponderado por destino: quanto da variacao entre locais o modelo pega."""
    pred = X @ beta
    media = (Y * w[:, None]).sum(axis=0) / w.sum()
    res = (w[:, None] * (Y - pred) ** 2).sum(axis=0)
    tot = (w[:, None] * (Y - media) ** 2).sum(axis=0)
    return 1.0 - res / tot


# =========================== gravacao =====================================
CRIA = """
CREATE OR REPLACE TABLE fluxo_estimado (
  cargo VARCHAR, escopo VARCHAR, uf VARCHAR,
  origem VARCHAR, destino VARCHAR,
  eleitores_origem HUGEINT, fracao DOUBLE,
  fracao_min DOUBLE, fracao_max DOUBLE,
  eleitores HUGEINT, eleitores_min HUGEINT, eleitores_max HUGEINT,
  locais BIGINT, municipios BIGINT
)
"""


def linhas_de(cargo, escopo, uf, origens, destinos, beta, faixa, origem_total,
              locais, municipios):
    """Converte uma matriz de fracoes em linhas com numero de eleitores."""
    saida = []
    for i, o in enumerate(origens):
        if origem_total[i] <= 0 or np.isnan(beta[i]).all():
            continue          # candidato sem voto nesse escopo: nada a estimar
        for j, dest in enumerate(destinos):
            lo = None if faixa is None else faixa[0][i, j]
            hi = None if faixa is None else faixa[1][i, j]
            saida.append((
                cargo, escopo, uf, o, dest,
                int(origem_total[i]), float(beta[i, j]),
                None if lo is None else float(lo),
                None if hi is None else float(hi),
                int(round(origem_total[i] * beta[i, j])),
                None if lo is None else int(round(origem_total[i] * lo)),
                None if hi is None else int(round(origem_total[i] * hi)),
                int(locais), int(municipios)))
    return saida


# =========================== conferencias =================================
def imprime(origens, destinos, beta, faixa, titulo):
    log(f"--- {titulo} ---")
    larg = max(len(o) for o in origens) + 2
    print(" " * larg + "".join(f"{x[:11]:>12}" for x in destinos))
    for i, o in enumerate(origens):
        print(f"{o:<{larg}}" + "".join(f"{100 * beta[i, j]:>11.1f} "
                                       for j in range(len(destinos))))
        if faixa is not None:
            print(" " * larg + "".join(
                f"{100 * faixa[0][i, j]:>5.0f}-{100 * faixa[1][i, j]:<6.0f}"
                for j in range(len(destinos))))


def confere(d, beta_media, beta_direto, bl):
    print()
    log("--- restricoes (beta >= 0 e linha somando 1) ---")
    for nome, b in (("por UF, agregada", beta_media), ("nacional direta", beta_direto)):
        soma = np.nansum(b, axis=1)
        print(f"  {nome:<18} menor coeficiente {np.nanmin(b):+.1e}, "
              f"pior desvio da soma 1 {np.abs(soma[soma > 0] - 1).max():.1e}")

    log("--- celulas colada na fronteira (o sintoma de identificacao fraca) ---")
    for nome, b in (("por UF, agregada", beta_media), ("nacional direta", beta_direto)):
        print(f"  {nome:<18} {(b < 1e-9).sum():>3} em 0 e {(b > 1 - 1e-9).sum():>2} em 1, "
              f"de {b.size} celulas")

    niveis = [b["nome"] for b in bl if b["nivel"] == "zona"]
    if niveis:
        log(f"bootstrap por zona eleitoral (municipio unico) em: "
            f"{', '.join(niveis)}")

    log("--- totais do 2o turno: observado x reconstruido do fluxo ---")
    obs = d["bruto_d"].sum(axis=0)
    org = d["bruto_o"].sum(axis=0)
    print(f"  {'destino':<18}{'observado':>14}{'por UF':>14}{'dif %':>9}"
          f"{'direto':>14}{'dif %':>9}")
    for j, dest in enumerate(d["destinos"]):
        a = float(org @ np.nan_to_num(beta_media)[:, j])
        b = float(org @ np.nan_to_num(beta_direto)[:, j])
        print(f"  {dest:<18}{obs[j]:>14,.0f}{a:>14,.0f}"
              f"{100 * (a - obs[j]) / obs[j]:>8.2f}%{b:>14,.0f}"
              f"{100 * (b - obs[j]) / obs[j]:>8.2f}%")



def confere_r2(bl, pontos, destinos):
    """R2 por destino em cada UF, resumido: a regressao roda por UF, logo o
    ajuste tambem e por UF."""
    log("--- R2 ponderado por destino, nas 27 regressoes estaduais ---")
    print(f"  {'destino':<18}{'mediana':>10}{'minimo':>10}{'maximo':>10}")
    r2 = np.array([ajuste(b["X"], b["Y"], b["w"], pontos[b["nome"]]) for b in bl])
    for j, dest in enumerate(destinos):
        c = r2[:, j]
        c = c[~np.isnan(c)]
        print(f"  {dest:<18}{np.median(c):>10.3f}{c.min():>10.3f}{c.max():>10.3f}")


def fora_da_amostra(d, por_uf=True):
    """Estima em metade dos municipios e mede o ajuste na outra metade.

    Se o modelo so decorasse ruido, o R2 cairia na metade nao vista.
    """
    rng = np.random.default_rng(SEMENTE)
    n_mun = d["municipio"].max() + 1
    treino_mun = rng.random(n_mun) < 0.5
    treino = treino_mun[d["municipio"]]
    print(f"  municipios de treino: {treino_mun.sum():,} de {n_mun:,}")
    for uf in sorted(set(d["uf"])):
        m = d["uf"] == uf
        if m.sum() < MIN_LOCAIS:
            continue
        A, B = momentos(d["X"][m & treino], d["Y"][m & treino], d["aptos"][m & treino])
        beta = resolve(A, B)
        teste = m & ~treino
        if uf in ("SP", "MG", "BA", "RS"):
            r2 = ajuste(d["X"][teste], d["Y"][teste], d["aptos"][teste], beta)
            print(f"  {uf}: R2 fora da amostra " +
                  ", ".join(f"{dest[:9]} {v:.3f}"
                            for dest, v in zip(d["destinos"], r2)))


# =========================== principal ====================================
def main():
    con = duckdb.connect(BANCO)
    con.execute("SET preserve_insertion_order=false")
    con.execute("SET memory_limit='6GB'")
    con.execute(f"SET temp_directory='{os.path.join(BASE, '_tmp').replace(chr(92), '/')}'")

    linhas = []

    # --- Presidente: uma matriz por UF, mais a media nacional delas ---------
    log("===== Presidente =====")
    d = carrega(con, "Presidente")
    log(f"{len(d['X']):,} locais pareados, {len(d['origens'])} origens: "
        f"{', '.join(d['origens'])}")
    if d["miudos"]:
        log(f"agregados em OUTROS: {', '.join(d['miudos'])}")

    t0 = time.time()
    pontos, faixas, bl = estima(d, por_uf=True, com_media=True)
    log(f"{len(bl)} UFs estimadas com bootstrap de {REPLICAS} replicas "
        f"({time.time() - t0:,.0f}s)")
    imprime(d["origens"], d["destinos"], pontos["MEDIA"], faixas["MEDIA"],
            "Presidente, Brasil: fluxo liquido estimado (% da origem, "
            "faixa de 95%)")

    # a nacional direta nao vai para o grafico; serve de contraste no diagnostico
    direto, faixa_direto, _ = estima(d, por_uf=False, com_media=False,
                                     replicas=REPLICAS)
    confere(d, pontos["MEDIA"], direto[None], bl)
    confere_r2(bl, pontos, d["destinos"])
    log("--- fora da amostra: estima em metade dos municipios, preve na outra ---")
    fora_da_amostra(d)

    org_nac = d["bruto_o"].sum(axis=0)
    n_mun_nac = int(d["municipio"].max() + 1)
    linhas += linhas_de("Presidente", "BRASIL", None, d["origens"], d["destinos"],
                        pontos["MEDIA"], faixas["MEDIA"], org_nac,
                        len(d["X"]), n_mun_nac)
    linhas += linhas_de("Presidente", "BRASIL_DIRETO", None, d["origens"],
                        d["destinos"], direto[None], faixa_direto[None], org_nac,
                        len(d["X"]), n_mun_nac)
    for b in bl:
        linhas += linhas_de("Presidente", "UF", b["nome"], d["origens"],
                            d["destinos"], pontos[b["nome"]], faixas[b["nome"]],
                            b["origem"], b["locais"], b["municipios"])

    # --- Governador: so por UF, e so nas que tiveram 2o turno --------------
    log("===== Governador =====")
    ufs = [r[0] for r in con.execute("""
        SELECT DISTINCT uf FROM fluxo_insumo
        WHERE cargo = 'Governador' AND turno = 2 ORDER BY 1""").fetchall()]
    log(f"2o turno de Governador em: {', '.join(ufs)}")
    for uf in ufs:
        g = carrega(con, "Governador", uf)
        if g is None or len(g["X"]) < MIN_LOCAIS:
            log(f"{uf}: sem 2o turno comparavel, pulando")
            continue
        p, f, bg = estima(g, por_uf=False, com_media=False)
        imprime(g["origens"], g["destinos"], p[None], f[None],
                f"Governador {uf}: fluxo liquido estimado "
                f"({bg[0]['locais']:,} locais)")
        linhas += linhas_de("Governador", "UF", uf, g["origens"], g["destinos"],
                            p[None], f[None], bg[0]["origem"],
                            bg[0]["locais"], bg[0]["municipios"])

    con.execute(CRIA)
    con.executemany(
        "INSERT INTO fluxo_estimado VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", linhas)
    log(f"fluxo_estimado: {len(linhas):,} linhas gravadas")
    con.close()
    print(f"\nbanco: {BANCO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
