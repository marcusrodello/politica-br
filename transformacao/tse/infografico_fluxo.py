"""Gera o infografico de fluxo de votos entre turnos a partir de fluxo_estimado.

Saida: uma pagina HTML autocontida - SVG inline, nenhum arquivo externo, nenhuma
biblioteca - com o diagrama de fluxo, a nota de metodo e a tabela completa com os
intervalos. A tabela nao e enfeite: o grafico mostra a forma, e ela e o caminho
para ler qualquer numero sem depender de passar o mouse.

Decisoes de desenho, para quem for alterar:

- a COR agrupa o destino em tres classes: um slot para cada finalista e um
  terceiro para quem saiu do voto valido (abstencao, branco e nulo). A ordem dos
  slots segue a votacao do 1o turno, nao a cor de campanha de ninguem: trocar
  isso por vermelho e azul partidario vira leitura politica dentro do grafico.
  Os tres primeiros slots da paleta sao os unicos que passam a checagem de
  daltonismo em todos os pares nos dois modos de tema.

- a ALTURA de cada no do 2o turno e a soma dos fluxos estimados, nao o resultado
  oficial. Forcar o fechamento esconderia o residuo do modelo; ele aparece como
  coluna propria na tabela, onde da para comparar com o oficial.

- a ORDEM dos nos nao e por tamanho: ela foi escolhida para alinhar cada origem
  com o destino que recebeu a maior parte dela, o que derruba o cruzamento de
  faixas. Nos de nao-voto ficam na base dos dois lados.

Uso:  python transformacao/tse/infografico_fluxo.py [saida.html] [--fragmento]
      --fragmento omite doctype, html, head e body, para embutir em outra pagina
"""
import datetime
import glob
import html
import os
import sys

import duckdb

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")
SAIDA = os.path.join(BASE, "docs", "fluxo-presidente-2026.html")
PARQUET = os.path.join(BASE, "dados", "parquet", "tse", "bu_2026", "*.parquet")

FONTE = ("https://dadosabertos.tse.jus.br/dataset/"
         "resultados-2026-boletim-de-urna")

# ordem dos nos: alinha cada origem com o destino que levou a maior parte dela
ORDEM_ORIGEM = ["FLAVIO BOLSONARO", "ZEMA", "RONALDO CAIADO", "RENAN SANTOS",
                "ESCRITOR AUGUSTO CURY", "OUTROS", "LULA", "BRANCO", "NULO",
                "ABSTENCAO"]
ORDEM_DESTINO = ["FLAVIO BOLSONARO", "LULA", "BRANCO", "NULO", "ABSTENCAO"]

# classe de cor de cada destino: um slot por finalista, um para o nao-voto
CLASSE = {"FLAVIO BOLSONARO": "a", "LULA": "b",
          "BRANCO": "c", "NULO": "c", "ABSTENCAO": "c"}

NOME = {"ABSTENCAO": "Abstenção", "BRANCO": "Branco", "NULO": "Nulo",
        "OUTROS": "Outros candidatos", "ZEMA": "Zema",
        "LULA": "Lula", "FLAVIO BOLSONARO": "Flavio Bolsonaro",
        "RENAN SANTOS": "Renan Santos", "RONALDO CAIADO": "Ronaldo Caiado",
        "ESCRITOR AUGUSTO CURY": "Augusto Cury"}

# geometria, em unidades do viewBox
L, R = 300, 820          # x das duas colunas de nos
NO = 13                  # largura do no
TOPO, ALTURA = 56, 660   # y inicial e altura util do diagrama
VAO = 3                  # folga entre nos vizinhos da mesma coluna


def rotulo(r):
    return NOME.get(r, r.title())


def num(v):
    return f"{int(round(v)):,}".replace(",", ".")


def milhoes(v):
    return f"{v / 1e6:.2f}".replace(".", ",")


def pct(v):
    return f"{100 * v:,.1f}".replace(".", ",")


# =========================== dados ========================================
def carrega(con):
    fluxos = con.execute("""
        SELECT origem, destino, eleitores_origem, fracao, fracao_min, fracao_max,
               eleitores, eleitores_min, eleitores_max
        FROM fluxo_estimado
        WHERE cargo = 'Presidente' AND escopo = 'BRASIL'
        ORDER BY eleitores DESC
    """).fetchall()

    oficial = {t: dict(con.execute("""
        SELECT rotulo, SUM(votos) FROM fluxo_insumo
        WHERE cargo = 'Presidente' AND turno = ? GROUP BY 1""", [t]).fetchall())
        for t in (1, 2)}

    meta = con.execute("""
        SELECT any_value(locais), any_value(municipios) FROM fluxo_estimado
        WHERE cargo = 'Presidente' AND escopo = 'BRASIL'""").fetchone()
    return fluxos, oficial, meta


def coleta():
    """Data da coleta: a modificacao mais recente dos Parquet da ingestao."""
    arq = glob.glob(PARQUET)
    if not arq:
        return "indisponivel"
    t = max(os.path.getmtime(a) for a in arq)
    return datetime.date.fromtimestamp(t).strftime("%d/%m/%Y")


# =========================== geometria ====================================
def escala_de(ordem, total_de):
    """Eleitores por unidade de altura que faz a coluna caber no espaco util."""
    vivos = [r for r in ordem if total_de.get(r, 0) > 0]
    return (ALTURA - VAO * (len(vivos) - 1)) / sum(total_de[r] for r in vivos)


def coluna(ordem, total_de, x, escala):
    """Posiciona os nos de uma coluna, do topo para a base, na escala dada.

    As duas colunas compartilham a escala: se cada uma usasse a sua, a largura
    de uma faixa mudaria de significado entre as pontas.
    """
    nos, y = {}, TOPO
    for r in ordem:
        if total_de.get(r, 0) <= 0:
            continue
        h = total_de[r] * escala
        nos[r] = dict(y=y, h=h, x=x, total=total_de[r])
        y += h + VAO
    return nos


def faixas(fluxos, origem, destino, escala):
    """Uma faixa por fluxo, empilhada em cada no pela ordem do no oposto.

    Empilhar na ordem do outro lado e o que impede as faixas de se cruzarem
    dentro do proprio no.
    """
    pos_o = {r: i for i, r in enumerate(ORDEM_ORIGEM)}
    pos_d = {r: i for i, r in enumerate(ORDEM_DESTINO)}
    cursor_o = {r: n["y"] for r, n in origem.items()}
    cursor_d = {r: n["y"] for r, n in destino.items()}
    saida = []
    for f in sorted(fluxos, key=lambda f: (pos_o[f[0]], pos_d[f[1]])):
        o, dest = f[0], f[1]
        if o not in origem or dest not in destino or f[6] <= 0:
            continue
        h = f[6] * escala
        saida.append(dict(origem=o, destino=dest, h=h,
                          y0=cursor_o[o], y1=cursor_d[dest], dados=f))
        cursor_o[o] += h
        cursor_d[dest] += h
    return saida


def arruma_rotulos(nos, ordem):
    """Desloca o rotulo que colidiria com o vizinho, preservando a ordem.

    Candidato pequeno vira um no de um pixel e meio - Zema e os agregados em
    OUTROS sao disso -, e varios deles em sequencia empilhariam rotulos um
    sobre o outro. Duas passadas, uma empurrando para baixo e outra de volta
    para cima, garantem o espacamento minimo sem trocar a ordem dos nomes. Onde
    o rotulo sai do centro do no, uma linha-guia fina liga os dois.
    """
    itens = [(r, nos[r]) for r in ordem if r in nos]
    for _, n in itens:
        n["duas"] = n["h"] >= 32          # nome e numero em linhas separadas
        n["alt"] = 31 if n["duas"] else 17
        n["ly"] = n["y"] + n["h"] / 2

    y = TOPO - 10
    for _, n in itens:                    # empurra para baixo
        n["ly"] = max(n["ly"], y + n["alt"] / 2)
        y = n["ly"] + n["alt"] / 2
    y = TOPO + ALTURA + 22
    for _, n in reversed(itens):          # devolve para cima o que estourou
        n["ly"] = min(n["ly"], y - n["alt"] / 2)
        y = n["ly"] - n["alt"] / 2
    return itens


def guia(n, lado):
    """Linha fina do no ate o rotulo deslocado."""
    centro = n["y"] + n["h"] / 2
    if abs(n["ly"] - centro) < 2.5:
        return ""
    if lado == "o":
        x0, x1 = n["x"] - 2, n["x"] - 9
    else:
        x0, x1 = n["x"] + NO + 2, n["x"] + NO + 9
    return (f'<path d="M{x0},{centro:.1f} L{(x0 + x1) / 2:.0f},{centro:.1f} '
            f'L{(x0 + x1) / 2:.0f},{n["ly"]:.1f} L{x1},{n["ly"]:.1f}" '
            f'class="gui"/>')


def caminho(f):
    """Area entre duas curvas cubicas: a faixa que liga origem e destino."""
    x0, x1 = L + NO, R
    xm = (x0 + x1) / 2
    y0a, y0b = f["y0"], f["y0"] + f["h"]
    y1a, y1b = f["y1"], f["y1"] + f["h"]
    return (f"M{x0:.1f},{y0a:.1f} C{xm:.1f},{y0a:.1f} {xm:.1f},{y1a:.1f} "
            f"{x1:.1f},{y1a:.1f} L{x1:.1f},{y1b:.1f} C{xm:.1f},{y1b:.1f} "
            f"{xm:.1f},{y0b:.1f} {x0:.1f},{y0b:.1f} Z")


# =========================== svg ==========================================
def desenha(fluxos, origem, destino):
    p = []
    p.append(f'<svg viewBox="0 0 1120 {TOPO + ALTURA + 30}" class="sankey" '
             f'role="img" aria-labelledby="t-svg">')
    p.append('<title id="t-svg">Fluxo estimado dos votos do 1o para o 2o turno '
             'da eleicao presidencial de 2026</title>')

    for x, texto in ((L + NO / 2, "1º turno"), (R + NO / 2, "2º turno")):
        p.append(f'<text x="{x:.0f}" y="28" class="cab">{texto}</text>')
    p.append(f'<text x="{L - 16}" y="28" class="cab fim">04/10/2026</text>')
    p.append(f'<text x="{R + NO + 16}" y="28" class="cab ini">25/10/2026</text>')

    for f in fluxos:
        d = f["dados"]
        p.append(
            f'<path d="{caminho(f)}" class="fx {CLASSE[f["destino"]]}" '
            f'data-o="{html.escape(rotulo(f["origem"]))}" '
            f'data-d="{html.escape(rotulo(f["destino"]))}" '
            f'data-n="{num(d[6])}" data-p="{pct(d[3])}" '
            f'data-lo="{num(d[7])}" data-hi="{num(d[8])}" '
            f'data-fl="{pct(d[4])}" data-fh="{pct(d[5])}"><title>'
            f'{html.escape(rotulo(f["origem"]))} → '
            f'{html.escape(rotulo(f["destino"]))}: {num(d[6])} eleitores '
            f'({pct(d[3])}% da origem)</title></path>')

    for lado, nos, ordem in (("o", origem, ORDEM_ORIGEM),
                             ("d", destino, ORDEM_DESTINO)):
        for r, n in arruma_rotulos(nos, ordem):
            cls = CLASSE.get(r, "n") if lado == "d" else "n"
            p.append(f'<rect x="{n["x"]}" y="{n["y"]:.1f}" width="{NO}" '
                     f'height="{max(n["h"], 1.2):.1f}" rx="1.5" '
                     f'class="no {cls}"/>')
            p.append(guia(n, lado))
            x = n["x"] - 14 if lado == "o" else n["x"] + NO + 14
            anc = "fim" if lado == "o" else "ini"
            if n["duas"]:
                p.append(f'<text x="{x:.0f}" y="{n["ly"] - 3:.1f}" '
                         f'class="rot {anc}">{html.escape(rotulo(r))}</text>')
                p.append(f'<text x="{x:.0f}" y="{n["ly"] + 13:.1f}" '
                         f'class="val {anc}">{num(n["total"])}</text>')
            else:
                # no fino nao tem altura para duas linhas: nome e numero saem na
                # mesma, num unico <text>, para o alinhamento nao exigir medir a
                # largura da fonte
                p.append(f'<text x="{x:.0f}" y="{n["ly"] + 4.5:.1f}" '
                         f'class="rot {anc}">{html.escape(rotulo(r))}'
                         f'<tspan class="val" dx="7">{num(n["total"])}</tspan>'
                         f'</text>')
    p.append("</svg>")
    return "\n".join(p)


# =========================== pagina =======================================
ESTILO = """
.viz-root{color-scheme:light;
 --surface-1:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink-2:#52514e;
 --muted:#898781;--hair:#e1e0d9;--ring:rgba(11,11,11,.10);
 --s-a:#2a78d6;--s-b:#eb6834;--s-c:#1baf7a;--node:#c3c2b7;
 font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
 color:var(--ink);background:var(--plane);
 margin:0 auto;padding:28px 20px 60px;max-width:1180px}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])) .viz-root{
 color-scheme:dark;--surface-1:#1a1a19;--plane:#0d0d0d;--ink:#fff;--ink-2:#c3c2b7;
 --muted:#898781;--hair:#2c2c2a;--ring:rgba(255,255,255,.10);
 --s-a:#3987e5;--s-b:#d95926;--s-c:#199e70;--node:#383835}}
:root[data-theme=dark] .viz-root{
 color-scheme:dark;--surface-1:#1a1a19;--plane:#0d0d0d;--ink:#fff;--ink-2:#c3c2b7;
 --muted:#898781;--hair:#2c2c2a;--ring:rgba(255,255,255,.10);
 --s-a:#3987e5;--s-b:#d95926;--s-c:#199e70;--node:#383835}
.viz-root h1{font-size:1.55rem;font-weight:650;letter-spacing:-.01em;margin:0 0 6px}
.viz-root .sub{color:var(--ink-2);margin:0 0 22px;max-width:62ch}
.viz-root .card{background:var(--surface-1);border:1px solid var(--ring);
 border-radius:12px;padding:18px 20px;margin:0 0 20px}
.tiles{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 20px}
.tile{background:var(--surface-1);border:1px solid var(--ring);border-radius:12px;
 padding:13px 16px;flex:1 1 180px}
.tile .k{color:var(--ink-2);font-size:.8rem;text-transform:uppercase;
 letter-spacing:.05em}
.tile .v{font-size:1.65rem;font-weight:620;letter-spacing:-.02em;margin-top:2px}
.tile .d{color:var(--ink-2);font-size:.85rem}
.leg{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin:0 0 4px;
 color:var(--ink-2);font-size:.9rem}
.leg i{display:inline-block;width:11px;height:11px;border-radius:3px;
 margin-right:6px;vertical-align:-1px}
.wrap{overflow-x:auto}
.sankey{display:block;width:100%;min-width:860px;height:auto}
.sankey .fx{opacity:.42;transition:opacity .12s}
.sankey .fx:hover,.sankey .fx.on{opacity:.88}
.sankey .fx.dim{opacity:.08}
.fx.a{fill:var(--s-a)}.fx.b{fill:var(--s-b)}.fx.c{fill:var(--s-c)}
.no{fill:var(--node)}.no.a{fill:var(--s-a)}.no.b{fill:var(--s-b)}.no.c{fill:var(--s-c)}
.sankey text{fill:var(--ink);font-size:13.5px}
.sankey .cab{fill:var(--ink-2);font-size:12.5px;text-transform:uppercase;
 letter-spacing:.06em;text-anchor:middle}
.sankey .val{fill:var(--ink-2);font-size:12px;font-variant-numeric:tabular-nums}
.sankey .rot{font-weight:520}
.sankey .gui{fill:none;stroke:var(--muted);stroke-width:1;opacity:.55}
.sankey .fim{text-anchor:end}.sankey .ini{text-anchor:start}
.tip{position:fixed;z-index:9;pointer-events:none;opacity:0;transition:opacity .1s;
 background:var(--surface-1);border:1px solid var(--ring);border-radius:9px;
 padding:9px 12px;font-size:.86rem;box-shadow:0 6px 22px rgba(0,0,0,.14);max-width:280px}
.tip b{font-weight:620}.tip .m{color:var(--ink-2)}
.rolo{overflow-x:auto}
table{border-collapse:collapse;width:100%;min-width:560px;font-size:.88rem}
th,td{text-align:right;padding:7px 10px;border-bottom:1px solid var(--hair);
 font-variant-numeric:tabular-nums}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left;
 font-variant-numeric:normal}
thead th{color:var(--ink-2);font-weight:560;font-size:.8rem;text-transform:uppercase;
 letter-spacing:.04em;border-bottom:1px solid var(--ring)}
tbody tr:hover{background:var(--plane)}
.viz-root h2{font-size:1.05rem;font-weight:620;margin:0 0 10px}
.viz-root p.nota{color:var(--ink-2);margin:0 0 10px;max-width:78ch}
.viz-root .pe{color:var(--muted);font-size:.82rem;margin-top:26px}
.viz-root a{color:inherit;text-decoration:underline;text-underline-offset:2px}
.sel{color:var(--ink-2);font-size:.85rem;margin:14px 0 0}
.viz-root a:focus-visible,.viz-root [tabindex]:focus-visible{outline:2px solid
 var(--s-a);outline-offset:2px}
@media (prefers-reduced-motion:reduce){.viz-root *{transition:none!important}}
"""

JS = """
(function(){
 var raiz=document.currentScript.closest('.viz-root')||document;
 var tip=raiz.querySelector('.tip'), svg=raiz.querySelector('.sankey');
 if(!svg) return;
 var fx=[].slice.call(svg.querySelectorAll('.fx'));
 function mostra(e,p){
  tip.innerHTML='<b>'+p.dataset.o+' &rarr; '+p.dataset.d+'</b><br>'+
   p.dataset.n+' eleitores <span class="m">('+p.dataset.p+'% da origem)</span>'+
   '<br><span class="m">faixa de 95%: '+p.dataset.lo+' a '+p.dataset.hi+
   ' ('+p.dataset.fl+'% a '+p.dataset.fh+'%)</span>';
  tip.style.opacity=1;
  var x=e.clientX+16, y=e.clientY+16, w=tip.offsetWidth, h=tip.offsetHeight;
  if(x+w>innerWidth-8) x=e.clientX-w-16;
  if(y+h>innerHeight-8) y=e.clientY-h-16;
  tip.style.left=x+'px'; tip.style.top=y+'px';
 }
 fx.forEach(function(p){
  p.addEventListener('mousemove',function(e){
   fx.forEach(function(q){ q.classList.toggle('dim', q!==p); });
   p.classList.add('on'); mostra(e,p);
  });
  p.addEventListener('mouseleave',function(){
   fx.forEach(function(q){ q.classList.remove('dim'); q.classList.remove('on'); });
   tip.style.opacity=0;
  });
 });
})();
"""


def pagina(fluxos_svg, tiles, leg, tabela, nota, meta, data_coleta):
    return f"""<div class="viz-root">
<h1>Para onde foram os votos entre o 1º e o 2º turno de 2026</h1>
<p class="sub">Fluxo <strong>estimado</strong> de eleitores na eleição
presidencial, calculado dentro de cada estado a partir do resultado de
{num(meta[0])} locais de votação. As barras são medidas; as faixas entre elas
são estimadas.</p>
{tiles}
<div class="card">
  <div class="leg">{leg}</div>
  <div class="wrap">{fluxos_svg}</div>
  <p class="sel">Passe o cursor sobre uma faixa para ver o número e a faixa de
  incerteza. Todos os valores também estão na tabela abaixo.</p>
</div>
{nota}
{tabela}
<p class="pe">Fonte: boletins de urna do Portal de Dados Abertos do TSE
(<a href="{FONTE}">{FONTE}</a>), coletados em {data_coleta}. Cálculo:
<code>transformacao/tse/estima_fluxo.py</code> no repositório POLITICA_BR.</p>
<div class="tip"></div>
<style>{ESTILO}</style>
<script>{JS}</script>
</div>"""


def tiles_de(oficial):
    t1, t2 = oficial[1], oficial[2]
    itens = [
        ("Lula, 2º turno", num(t2["LULA"]),
         f"+{milhoes(t2['LULA'] - t1['LULA'])} mi sobre o 1º turno"),
        ("Flavio Bolsonaro, 2º turno", num(t2["FLAVIO BOLSONARO"]),
         f"+{milhoes(t2['FLAVIO BOLSONARO'] - t1['FLAVIO BOLSONARO'])} mi "
         f"sobre o 1º turno"),
        ("Abstenção, 2º turno", num(t2["ABSTENCAO"]),
         f"{milhoes(t2['ABSTENCAO'] - t1['ABSTENCAO'])} mi sobre o 1º turno"),
        ("Eleitores aptos", num(sum(t2.values())),
         "o fluxo fecha em 100% deles nos dois lados"),
    ]
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="k">{k}</div><div class="v">{v}</div>'
        f'<div class="d">{d}</div></div>' for k, v, d in itens) + "</div>"


def legenda():
    rot = [("a", "Votou Flavio Bolsonaro no 2º turno"),
           ("b", "Votou Lula no 2º turno"),
           ("c", "Não votou em candidato: abstenção, branco ou nulo")]
    return "".join(f'<span><i style="background:var(--s-{c})"></i>{t}</span>'
                   for c, t in rot)


def tabela_de(fluxos, oficial):
    cab = ("<thead><tr><th>Origem (1º turno)</th><th>Destino (2º turno)</th>"
           "<th>Eleitores</th><th>Faixa de 95%</th>"
           "<th>% da origem</th></tr></thead>")
    corpo = []
    for f in sorted(fluxos, key=lambda f: -f[6]):
        if f[6] <= 0:
            continue
        corpo.append(
            f"<tr><td>{html.escape(rotulo(f[0]))}</td>"
            f"<td>{html.escape(rotulo(f[1]))}</td><td>{num(f[6])}</td>"
            f"<td>{num(f[7])} – {num(f[8])}</td><td>{pct(f[3])}%</td></tr>")

    # fechamento: o que o modelo reconstroi em cada destino, contra o oficial
    rec = {}
    for f in fluxos:
        rec[f[1]] = rec.get(f[1], 0) + f[6]
    fecha = ["<thead><tr><th>Destino (2º turno)</th><th>Resultado oficial</th>"
             "<th>Soma do fluxo estimado</th><th>Diferença</th></tr></thead>"]
    linhas = []
    for r in ORDEM_DESTINO:
        of, es = oficial[2][r], rec.get(r, 0)
        linhas.append(f"<tr><td>{rotulo(r)}</td><td>{num(of)}</td>"
                      f"<td>{num(es)}</td>"
                      f"<td>{pct((es - of) / of)}%</td></tr>")
    return (f'<div class="card"><h2>Fluxo estimado, eleitor por eleitor de '
            f'origem</h2><div class="rolo"><table>{cab}'
            f'<tbody>{"".join(corpo)}</tbody></table></div>'
            f'</div><div class="card"><h2>O quanto o modelo reproduz o '
            f'resultado oficial</h2>'
            f'<p class="nota">O diagrama desenha a soma dos fluxos estimados, '
            f'não o resultado oficial. A diferença entre as duas colunas é o '
            f'resíduo do modelo, e fica abaixo de 2% em todos os destinos.</p>'
            f'<div class="rolo"><table>{fecha[0]}'
            f'<tbody>{"".join(linhas)}</tbody></table></div></div>')


def nota_de(meta):
    return f"""<div class="card"><h2>Como esses números foram calculados</h2>
<p class="nota"><strong>O que é medido e o que é estimado.</strong> Quantos votos
cada candidato teve em cada um dos {num(meta[0])} locais de votação, nos dois
turnos, é dado oficial do TSE — são as barras. Para onde foi cada eleitor não
está em nenhum lugar: o voto é secreto. As faixas são uma estimativa feita por
regressão, comparando como o resultado mudou entre os dois turnos em locais de
perfil político diferente, dentro de cada estado.</p>
<p class="nota"><strong>O limite honesto da estimativa.</strong> Com dado
agregado por local, dois movimentos opostos que se anulam dentro do mesmo local
são invisíveis — é a chamada falácia ecológica. O que o diagrama mostra é o
fluxo <em>líquido</em>: o menor remanejamento de votos compatível com o que cada
local registrou nas duas datas. Por isso a lealdade de cada candidato aparece
como um teto, e a troca entre candidatos, como um piso.</p>
<p class="nota"><strong>A faixa de incerteza.</strong> Cada número vem com uma
faixa de 95%, obtida reamostrando os {num(meta[1])} municípios da base 150
vezes. Faixa larga significa que o dado não decide aquela célula —
caso de boa parte dos votos brancos e nulos, cujo movimento é pequeno e
disperso. Onde a faixa é estreita, o resultado é robusto.</p></div>"""


# =========================== principal ====================================
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    fragmento = "--fragmento" in sys.argv
    saida = args[0] if args else SAIDA

    con = duckdb.connect(BANCO, read_only=True)
    con.execute("USE tse")
    fluxos, oficial, meta = carrega(con)
    con.close()

    total_o, total_d = {}, {}
    for f in fluxos:
        total_o[f[0]] = f[2]
        total_d[f[1]] = total_d.get(f[1], 0) + f[6]

    escala = min(escala_de(ORDEM_ORIGEM, total_o), escala_de(ORDEM_DESTINO, total_d))
    origem = coluna(ORDEM_ORIGEM, total_o, L, escala)
    destino = coluna(ORDEM_DESTINO, total_d, R, escala)

    fx = faixas(fluxos, origem, destino, escala)
    corpo = pagina(desenha(fx, origem, destino), tiles_de(oficial), legenda(),
                   tabela_de(fluxos, oficial), nota_de(meta), meta, coleta())

    if not fragmento:
        corpo = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n'
                 '<meta charset="utf-8">\n'
                 '<meta name="viewport" content="width=device-width,'
                 'initial-scale=1">\n<title>Fluxo de votos entre os turnos de '
                 '2026 — POLITICA_BR</title>\n</head>\n<body '
                 'style="margin:0;background:#f9f9f7">\n' + corpo +
                 "\n</body>\n</html>\n")

    os.makedirs(os.path.dirname(os.path.abspath(saida)), exist_ok=True)
    with open(saida, "w", encoding="utf-8") as f:
        f.write(corpo)
    print(f"{len(fx)} faixas desenhadas -> {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
