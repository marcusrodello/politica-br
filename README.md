# Eleições 2026 — migração de votos entre turnos

Base e scripts para analisar como os votos se moveram do 1º para o 2º turno de
2026, no nível do local de votação, e produzir um infográfico de fluxo.

Fonte: boletins de urna do [Portal de Dados Abertos do
TSE](https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna).
Cargos carregados: Presidente e Governador, nos dois turnos.

## Como reconstruir a base

```
python ingere_bu.py        # baixa os 56 pacotes do TSE e grava Parquet
python monta_banco.py      # monta as tabelas e roda as conferências
python documenta_banco.py  # grava as descrições no banco e regera o dicionário
```

`ingere_bu.py` é retomável: reexecutar pula o que já tem Parquet válido. Ele
confere se o Parquet abre antes de pular, porque uma execução interrompida
deixa arquivo truncado que só acusa erro muito depois, na leitura.

Nada em `parquet/`, `_tmp/` ou `eleicoes2026.duckdb` está versionado — tudo se
regera dos scripts. O dicionário de dados está em `DICIONARIO.md`, gerado do
catálogo do banco.

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

## Pendente

A estimativa dos fluxos por local de votação (regressão), e o infográfico.
