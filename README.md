# POLITICA_BR — dados políticos oficiais do Brasil

Base de dados e, depois, portal público que reúne num só lugar o dado político
oficial hoje espalhado por TSE, Câmara, Senado, STF, IBGE e Ipea — para o
cidadão comparar governos, políticos e partidos e tirar as próprias conclusões.

Brief completo em [`docs/brief-portal-politico.md`](docs/brief-portal-politico.md).

## Princípios (inegociáveis)

- não inventar dado: servir o que existe, completo ou parcial
- quando documentos oficiais se contradizem, exibir os dois
- cada número rastreável até a fonte oficial e à data da coleta
- o portal mostra fato, não opinião; a leitura é do cidadão

## Estrutura

```
ingestao/comum.py          camada compartilhada: baixa, grava Parquet, registra a coleta
ingestao/confere_coleta.py confere contra o portal se cada arquivo chegou inteiro
ingestao/<fonte>/          baixa o dado aberto de uma fonte e grava Parquet
transformacao/<fonte>/     monta as tabelas da fonte no DuckDB
transformacao/documenta_banco.py  grava as descrições no banco e regera o dicionário
dados/                     Parquet e banco (não versionado; se regera dos scripts)
docs/                      brief, dicionário de dados, notas por módulo e infográficos
```

Uma pasta por fonte, dentro de `ingestao/` e `transformacao/`. Banco único em
`dados/politica_br.duckdb`.

Toda ingestão passa por `ingestao/comum.py`, que grava na tabela `coleta` a URL,
o instante, o tamanho e o sha256 de cada arquivo que entrou — é o que sustenta a
promessa de rastreabilidade. O download confere o tamanho contra o que o portal
declara: um arquivo cortado no meio falha em vez de entrar na base como se
estivesse bom.

## Estado atual

| Fonte | Situação |
| --- | --- |
| TSE — boletins de urna 2026 | 9,0 milhões de linhas, 94.709 locais de votação |
| TSE — fluxo de votos entre os turnos | estimado, com infográfico |
| Câmara dos Deputados | 420 arquivos, 11,9 milhões de linhas |
| Senado Federal | em andamento |
| STF, Executivo federal, IBGE, Ipea | não iniciado |

O que entrou da Câmara, e até onde cada série alcança:

| Conjunto | Período | Linhas |
| --- | --- | --- |
| cota parlamentar | 2008–2026 | 5.238.372 |
| votos nominais de cada deputado | 2001–2026 | 1.927.219 |
| autoria de proposições | 1945–2026 | 1.919.153 |
| proposições | 1945–2026 | 993.049 |
| objeto de cada votação | 1988–2026 | 825.484 |
| tema das proposições | 1945–2026 | 338.408 |
| composição das frentes parlamentares | atual | 262.271 |
| votações | 1988–2026 | 194.412 |
| cargos em órgãos, por legislatura | L52–L58 | 85.857 |
| eventos e sessões | 1991–2026 | 62.732 |
| deputados, com CPF e biografia | todos | 7.890 |

Mais ocupações e profissões declaradas, órgãos, frentes, partidos e as 58
legislaturas desde 1826.

Notas por módulo:

- TSE 2026, armadilhas dos dados e o método da estimativa de fluxo:
  [`docs/tse-2026-migracao-votos.md`](docs/tse-2026-migracao-votos.md)
- infográfico do fluxo:
  [`docs/fluxo-presidente-2026.html`](docs/fluxo-presidente-2026.html)
- dicionário de dados, gerado do catálogo do banco:
  [`docs/dicionario.md`](docs/dicionario.md)

## Como reconstruir a base

```
python ingestao/tse/boletins_urna.py          # 56 pacotes do TSE -> Parquet
python ingestao/camara/dados_abertos.py       # arquivos em lote da Câmara -> Parquet
python transformacao/tse/monta_banco.py       # tabelas do TSE e as conferências
python transformacao/tse/estima_fluxo.py      # matriz de fluxo entre turnos (~8 min)
python transformacao/documenta_banco.py       # descrições no banco e dicionário
python transformacao/tse/infografico_fluxo.py # infográfico de fluxo
python ingestao/confere_coleta.py             # confere a integridade do que foi coletado
```

As ingestões são retomáveis: reexecutar pula o que já tem Parquet válido — e
confere que o Parquet abre antes de pular, porque uma execução interrompida
deixa arquivo truncado que só acusa erro muito depois, na leitura.

Nada em `dados/` ou `_tmp/` está versionado.

## Próximos passos

1. separar as tabelas por fonte em schemas do DuckDB (`tse.bu`, `camara.…`) —
   hoje tudo vive em `main` e os nomes genéricos (`bu`, `secao`, `local`) vão
   colidir quando entrar a segunda fonte
2. ingestão do Senado, do TSE histórico (candidatos desde 1933) e dos
   indicadores (IBGE, Ipea, Tesouro, Banco Central)
3. padronização de identidade de político entre as bases — o maior desafio do
   projeto: a mesma pessoa aparece escrita diferente em cada fonte
4. site estático com perfil de político e página de eleição

## Fontes

| Fonte | Como se acessa |
| --- | --- |
| TSE | CKAN em `dadosabertos.tse.jus.br`, pacotes ZIP por UF e turno |
| Câmara | arquivos em lote CSV em `dadosabertos.camara.leg.br/arquivos`; a API v2 responde 503 em rajadas e exigiria dezenas de milhares de requisições para o mesmo conteúdo |
| Senado | API JSON em `legis.senado.leg.br/dadosabertos`; os endpoints clássicos (`/materia`, `/plenario/lista/votacao`) estão depreciados — os vivos são `/processo` e `/votacao` |
| STF | sem dados abertos estruturados acessíveis: o portal é uma SPA, o Corte Aberta responde 403 e a API de jurisprudência não aceita GET |
| Executivo | Portal da Transparência e `dados.gov.br` passaram a exigir chave de API; SICONFI (Tesouro) e SGS (Banco Central) são abertos |
| IBGE e Ipea | `servicodados.ibge.gov.br` e OData do Ipeadata, abertos |
