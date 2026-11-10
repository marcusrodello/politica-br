# TSE 2026 — migração de votos entre turnos

Primeiro módulo do portal: como os votos se moveram do 1º para o 2º turno de
2026, no nível do local de votação, com um infográfico de fluxo como saída.

Fonte: boletins de urna do [Portal de Dados Abertos do
TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna).
Cargos carregados: Presidente e Governador, nos dois turnos.

## O que a base contém

| | |
| --- | --- |
| Boletins | 9.042.567 linhas |
| Locais de votação | 94.709 |
| Seções | 499.206 |
| Eleitores aptos (Presidente) | 158.745.007 |
| Parquet em disco | 126 MB |

Resultado de Presidente, em votos:

| | 1º turno | 2º turno |
| --- | --- | --- |
| Lula | 53.879.538 | 64.256.232 |
| Flavio Bolsonaro | 56.104.503 | 59.826.041 |
| Abstenção | 33.469.172 | 30.508.903 |
| Branco + nulo | 5.969.801 | 4.153.801 |

A contabilidade nacional fecha: os dois finalistas ganharam 14,10 milhões de
votos entre os turnos, e as fontes somam 14,07 milhões — 9,29 dos candidatos
eliminados, 2,96 de abstenção que voltou às urnas e 1,82 de quem deixou de
votar branco ou nulo.

## Três armadilhas dos dados do TSE

Todas já tratadas no código. Quem mexer na base não deve reintroduzi-las.

**O eleitorado é por seção e cargo, não por seção.** Em 19.776 seções o número
de aptos e o de comparecimento divergem entre Presidente e Governador, porque o
eleitor em trânsito vota só para Presidente. Tratar como valor único por seção
inflava o total nacional de aptos em 4,6 milhões.

**Governador teve 2º turno em apenas 6 UFs** (AC, AM, DF, ES, RN, TO). A
abstenção precisa ser derivada por cargo, senão vaza para locais onde aquele
cargo não foi disputado.

**O leitor de CSV estoura a memória nos estados grandes.** O CSV de São Paulo
tem 7,7 GB; pedir ao DuckDB para inferir tipos varrendo o arquivo inteiro
(`sample_size=-1`) consome os 16 GB da máquina. A carga usa `all_varchar=true`
com conversão na seleção, teto de memória e área de descarga em disco.

## Decisões de modelagem

A unidade de comparação entre turnos é o **local de votação**, não a seção.
Seções agregadas — aquelas que recebem o eleitorado de outras somado nelas —
mudam de agrupamento entre os turnos, então a mesma seção pode representar
eleitorados diferentes em outubro e em novembro. O local dissolve o problema e
ainda deixa 94.709 unidades de observação.

Abstenção e branco/nulo entram como rótulos em `fluxo_insumo`, ao lado dos
candidatos, para que o fluxo feche em 100% dos eleitores aptos nos dois lados.
Sem isso, os votos que viraram abstenção parecem desaparecer do gráfico.

## Limite do que a base permite afirmar

As barras do infográfico são medidas; as setas entre elas são estimadas. No
nível do local observa-se mudança de agregados, não migração individual: uma
alta de 50 votos num candidato é igualmente compatível com migração direta e
com movimentos opostos que se cancelam. Isso se chama falácia ecológica. Com
94.709 locais de perfil político variado, a estimativa por regressão fica
estreita, mas o infográfico deve dizer "fluxo estimado", não "fluxo medido".

A consequência prática é que o que se estima é o fluxo **líquido**: o menor
remanejamento compatível com o que cada local registrou nas duas datas. A
lealdade de cada candidato sai como um teto e a troca entre candidatos como um
piso.

## A estimativa do fluxo

`transformacao/tse/estima_fluxo.py` grava a tabela `fluxo_estimado`. Para cada
origem *i* do 1º turno e destino *j* do 2º, em cada local *l*:

    y_lj = Σ_i β_ij · x_li + erro_l

`x` e `y` são frações dos mesmos aptos — os do 1º turno, porque o eleitorado do
local praticamente não muda entre as duas datas: 72% dos locais têm o número
idêntico de aptos, 99,7% variam menos de 1%, e só 0,033% dos eleitores trocam
de local. Restrições: β ≥ 0 e cada linha somando 1. Ponderação pelos aptos do
local. O solver é gradiente projetado acelerado sobre as duas matrizes de
momento, o que torna o custo independente do número de locais.

**A regressão roda dentro de cada UF, e o número nacional é a média das 27
matrizes** ponderada pelos eleitores de cada origem. Isso não é refinamento: é
a diferença entre um resultado utilizável e um artefato. Uma única regressão
nacional supõe que o eleitor de um candidato se comporta igual em Roraima e no
Paraná; quando o molde não cabe, o estimador não erra pouco em tudo — ele foge
para os vértices. Na regressão nacional direta, 27 das 50 células ficam cravadas
em 0% ou 100%, com intervalo de confiança estreito, inclusive absurdos como
Zema inteiro para um lado. Estimando por UF, sobram 2 células em zero e nenhuma
em 100%. A matriz nacional direta fica gravada como `BRASIL_DIRETO`, só para
quem quiser ver o tamanho do viés de agregação.

O intervalo de 95% vem de bootstrap com 150 réplicas que reamostra **municípios**,
não locais: locais do mesmo município se parecem, e tratá-los como 94 mil
observações independentes estreitaria o intervalo artificialmente.

### O que a estimativa diz

Lula ganhou 10,38 milhões de votos entre os turnos, e a maior parte deles não
veio dos candidatos eliminados:

| Origem no 1º turno | Para Lula | Para Flavio Bolsonaro |
| --- | --- | --- |
| Candidatos eliminados (9,32 mi) | 3,91 mi | 3,64 mi |
| Branco e nulo (5,97 mi) | 4,13 mi | 0,02 mi |
| Abstenção (33,47 mi) | 2,81 mi | 0,63 mi |

Entre os eliminados o fluxo se divide quase ao meio, com os eleitorados puxando
para lados diferentes: 57,9% de Ronaldo Caiado e 93,3% de Zema para Flavio
Bolsonaro, contra 53,0% de Augusto Cury e 45,1% de Renan Santos para Lula. O
que decidiu o segundo turno, nesses números, foi o voto que não era voto no
primeiro: 82,2% dos brancos e 61,1% dos nulos aparecem como voto em Lula, mais
8,4% da abstenção.

### Quanto confiar em cada número

| Conferência | Resultado |
| --- | --- |
| Reconstrução dos totais oficiais do 2º turno | erro ≤ 0,07% nos finalistas e na abstenção; 0,91% no nulo e 1,58% no branco |
| R² ponderado, mediana das 27 UFs | 0,98 Flavio Bolsonaro, 0,97 Lula, 0,82 abstenção, 0,43 nulo, 0,30 branco |
| Previsão fora da amostra (estima em metade dos municípios, prevê na outra) | mesma ordem de ajuste, sem queda |
| Restrições | menor coeficiente 0, pior desvio da soma 1 igual a 2·10⁻¹⁶ |

Os destinos branco e nulo são os frágeis: movimento pequeno, disperso, R² baixo
e faixa larga. Os dois finalistas e a abstenção são sólidos. Vale repetir o que
o R² alto não compra: ele mede o ajuste entre locais, não a validade da
passagem do agregado para o indivíduo.

## O infográfico

`transformacao/tse/infografico_fluxo.py` gera
[`fluxo-presidente-2026.html`](fluxo-presidente-2026.html): página autocontida,
SVG inline, sem biblioteca nem arquivo externo. A altura dos nós do 2º turno é a
soma dos fluxos estimados, não o resultado oficial — forçar o fechamento
esconderia o resíduo do modelo, que aparece como tabela própria na página. A cor
agrupa o destino em três classes (um slot por finalista, um terceiro para
abstenção, branco e nulo) e segue a ordem de votação do 1º turno, não a cor de
campanha de ninguém.
