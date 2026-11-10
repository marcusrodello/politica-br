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

**Um schema por fonte** — `tse.bu`, `camara.voto`, `senado.senador`. Em `main`
fica só o que atravessa fontes: hoje, a tabela `coleta`. Sem essa separação a
segunda fonte colide, porque os nomes naturais dessas tabelas são genéricos:
`local`, `secao` e `votos_local` não pertencem ao TSE por direito de chegada.

Toda ingestão passa por `ingestao/comum.py`, que grava em `main.coleta` a URL,
o instante, o tamanho e o sha256 de cada arquivo que entrou — é o que sustenta a
promessa de rastreabilidade. O download confere o tamanho contra o que o portal
declara: um arquivo cortado no meio falha em vez de entrar na base como se
estivesse bom.

Os Parquets guardam **texto puro**, de propósito: campo que muda de formato no
meio de uma série histórica derruba a leitura inteira. A tipagem acontece na
transformação, com `TRY_CAST`, e cada script conta e imprime o que não
converteu — senão o estrago fica silencioso.

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
| TSE | CKAN em `dadosabertos.tse.jus.br`. Boletins de urna em ZIP por UF e turno; o acervo histórico (1933–2026) em ZIP por ano, com um CSV por UF dentro |
| Câmara | arquivos em lote CSV em `dadosabertos.camara.leg.br/arquivos`. A API v2 responde 503 em rajadas e exigiria dezenas de milhares de requisições paginadas para o mesmo conteúdo |
| Senado | API JSON em `legis.senado.leg.br/dadosabertos`. Os endpoints clássicos (`/materia`, `/plenario/lista/votacao`) estão depreciados com data de desativação vencida — os vivos são `/processo` e `/votacao` |
| Ipeadata | OData em `ipeadata.gov.br/api/odata4`, uma requisição por série. É agregador: o catálogo aponta a fonte primária de cada série, e é ela que o portal cita |
| IBGE | `servicodados.ibge.gov.br`, API v1 de localidades e v3 do SIDRA |
| Banco Central | SGS em `api.bcb.gov.br/dados/serie`. Sem catálogo por API — as séries entram por lista explícita |
| Judiciário | DataJud do CNJ (`api-publica.datajud.cnj.jus.br`), que recebe os dados dos tribunais por obrigação normativa. **Exige chave** |
| Executivo | Portal da Transparência e `dados.gov.br` **exigem chave**. SICONFI (Tesouro) é aberto |

### O que o STF não dá

Não há dados abertos estruturados acessíveis: o portal de dados abertos é uma
aplicação de página única que não serve JSON para fora, o Corte Aberta é um
painel Qlik Sense cujos números só saem por engine websocket, e a API de
jurisprudência não aceita GET. Raspar qualquer um dos três daria um pipeline
que quebra no próximo deploy do tribunal. A via usada é o DataJud.

### Chaves de API que precisam de cadastro

Três fontes passaram a exigir credencial pessoal. Os scripts leem a chave de
variável de ambiente e nunca do código, que é público.

| Fonte | Onde se cadastra | Variável |
| --- | --- | --- |
| DataJud (CNJ) | `datajud.cnj.jus.br` → Meu Perfil → API Key | `POLITICA_BR_DATAJUD_KEY` |
| Portal da Transparência | `portaldatransparencia.gov.br/api-de-dados` | não implementado |
| dados.gov.br | `dados.gov.br` | não implementado |

A chave pública compartilhada do DataJud, que circulava no tutorial de 2023,
foi desativada e hoje responde 401.
