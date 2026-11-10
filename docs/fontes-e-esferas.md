# Fontes por esfera: o que existe, como se pega, onde dói

Levantamento feito em 10/11/2026, sondando cada endpoint em vez de confiar na
documentação. O que está aqui é o que respondeu naquele dia.

Regra do projeto: a ingestão registra em `main.coleta` a URL, o instante, o
tamanho e o sha256 de cada arquivo. Este documento explica as escolhas; o
registro no banco prova o que de fato entrou.

## Resumo

| Esfera | Fonte | Via | Estado |
| --- | --- | --- | --- |
| Eleitoral | TSE | CKAN + CDN | boletins de 2026 e acervo 1933–2026 |
| Legislativo | Câmara dos Deputados | arquivos em lote CSV | 420 arquivos, 11,9 mi de linhas |
| Legislativo | Senado Federal | API JSON | em coleta |
| Judiciário | STF, STJ, TSE | DataJud (CNJ) | **bloqueado: exige chave** |
| Executivo | Portal da Transparência | API | **bloqueado: exige chave** |
| Executivo | Tesouro (SICONFI) | API ORDS | aberto, não implementado |
| Indicadores | Ipeadata | OData | 4.135 séries |
| Indicadores | IBGE | API v1 e v3 | localidades, SIDRA |
| Indicadores | Banco Central | SGS | 15 séries |

## TSE — eleitoral

Catálogo CKAN em `dadosabertos.tse.jus.br/api/3/action`, com 190 pacotes. Os
arquivos ficam no CDN (`cdn.tse.jus.br/estatistica/sead/odsele/...`), em ZIP com
um CSV por UF mais um `BR` consolidado. Encoding **latin-1**, delimitador `;`.

As URLs vêm do catálogo, nunca montadas à mão: o TSE muda o caminho no CDN de
vez em quando e o CKAN é a única coisa que acompanha.

**A série troca de formato em 1994.** Antes disso não existe cadastro de
candidato padronizado — o que há é a legenda e o vínculo candidato-legenda — e o
resultado vem agregado por UF, não por município e zona. `votacao_candidato_uf`
e `votacao_candidato_munzona` respondem a perguntas diferentes, e o nome do
candidato antes de 1994 nem sempre identifica uma pessoa.

A tabela `municipio_tse_ibge` é a ponte entre o código de município do TSE e o
do IBGE. Sem ela não se cruza eleição com indicador social — o TSE usa
numeração própria, que não é a do IBGE.

Armadilhas dos boletins de urna de 2026 estão em
[`tse-2026-migracao-votos.md`](tse-2026-migracao-votos.md).

## Câmara dos Deputados — legislativo

Dois caminhos, e o escolhido é o segundo:

- **API v2** (`dadosabertos.camara.leg.br/api/v2`): respondeu 503 em todas as
  tentativas da sondagem, e cobrir o mesmo conteúdo exigiria dezenas de
  milhares de requisições paginadas.
- **Arquivos em lote** (`dadosabertos.camara.leg.br/arquivos`): CSV por ano ou
  conjunto inteiro, UTF-8 com BOM, delimitador `;`. É o retrato oficial do dia,
  publicado pela própria Câmara.

A cobertura temporal **não é a mesma em cada conjunto**: votos nominais começam
em 2001, votações em 1988, proposições em 1945, cota parlamentar em 2008, e as
legislaturas vão até 1826. Juntar votações e votos sem olhar isso sugere que o
Congresso não votava nominal antes de 2001 — votava; o registro aberto é que
não existe.

O arquivo de deputados **não tem coluna de id**: a identidade vive no fim da
URI (`.../deputados/204382`), e é por ela que voto, autoria e frente se amarram.

A cota parlamentar vem de outro host, `camara.leg.br/cotas/Ano-AAAA.csv.zip`.

## Senado Federal — legislativo

API JSON em `legis.senado.leg.br/dadosabertos`, com OpenAPI em
`/v3/api-docs` (157 endpoints). Não há download em lote: tudo é uma chamada por
ano, por legislatura ou por parlamentar.

**Duas gerações vivas ao mesmo tempo, e a antiga está vencida.** Os endpoints
clássicos — `/materia/pesquisa/lista`, `/plenario/lista/votacao`,
`/senador/{cod}/votacoes` — trazem no corpo da resposta um aviso de
descontinuação com `DataDesativacaoCompleta` em **2026-02-01**, data já
passada: respondem por tolerância, não por contrato. Os substitutos indicados
pelo próprio portal são `/processo` e `/votacao`, que devolvem JSON plano em vez
do envelope herdado do XML.

A geração antiga embrulha a resposta em camadas (`ListaLegislatura` →
`Legislaturas` → `Legislatura`) e, quando há um único registro, devolve objeto
em vez de lista de um. A ingestão desembrulha os três casos.

`/votacao?ano=N` traz as votações **com o voto de cada senador embutido** — os
votos viram conjunto próprio na ingestão, senão ficariam presos num campo de
texto dentro da votação.

## Judiciário — STF, STJ, TSE

### O que o STF não dá

| Tentativa | Resultado |
| --- | --- |
| `portal.stf.jus.br/dadosabertos` | aplicação de página única; não serve JSON para fora |
| `transparencia.stf.jus.br` (Corte Aberta) | painel Qlik Sense; números só por engine websocket |
| `jurisprudencia.stf.jus.br/api/search/search` | não aceita GET (405) |
| `dadosabertos.stf.jus.br` | host não existe |

Raspar qualquer um dos três daria um pipeline que quebra no próximo deploy do
tribunal.

### A via: DataJud

`api-publica.datajud.cnj.jus.br/api_publica_{tribunal}/_search` — Base Nacional
de Processos Judiciais do CNJ, que recebe os dados dos próprios tribunais por
obrigação normativa. Interface Elasticsearch, paginação por `search_after`.

**Exige chave pessoal.** A chave pública compartilhada que circulava no tutorial
do CNJ de 2023 foi desativada e hoje responde 401.

## Executivo federal

| Fonte | Situação |
| --- | --- |
| Portal da Transparência (`api.portaldatransparencia.gov.br`) | 401 sem chave; cadastro gratuito |
| `dados.gov.br` (CKAN) | 401 sem chave — passou a exigir credencial |
| SICONFI / Tesouro (`apidatalake.tesouro.gov.br/ords/siconfi`) | **aberto**; dados fiscais de União, estados e municípios |
| Diário Oficial (`in.gov.br`) | só HTML; não há API estruturada |
| LexML (`lexml.gov.br/busca/SRU`) | atrás de verificação de segurança |
| Legislação federal | o Senado publica normas em `/legislacao/lista`, que a ingestão do Senado cobre |

## Indicadores

**Ipeadata** (`ipeadata.gov.br/api/odata4`): 4.135 séries, uma requisição cada.
É **agregador, não fonte primária** — cada série traz `FNTSIGLA` e `FNTURL`
apontando quem produziu o dado. O catálogo entra na base junto com as séries
para o portal citar a fonte original, e não "Ipeadata". Série regional vem com
código territorial **do IBGE**, não do TSE.

**IBGE** (`servicodados.ibge.gov.br`): API v1 de localidades (os 5.570
municípios com o código oficial) e v3 do SIDRA. O SIDRA tem mais de mil
agregados; a ingestão usa uma lista explícita, cada entrada justificada no
código.

**Banco Central** (`api.bcb.gov.br/dados/serie`): o SGS tem mais de vinte mil
séries e **não publica catálogo por API** — o que existe é busca web. As séries
entram por lista explícita; varrer o espaço de códigos seria chute.

## O que a sondagem ensinou sobre operação

- **Download que não confere tamanho mente.** Um arquivo da Câmara chegou
  cortado e passou como bom: 16 mil votos a menos, e o CSV pareceu defeituoso
  na origem quando o problema era local. A causa só apareceu porque a segunda
  tentativa trouxe mais linhas. Hoje o download confere o `Content-Length`.
- **Os portais caem.** A API da Câmara responde 503 em rajadas; o Senado estoura
  o tempo de leitura com frequência. Toda requisição tem retry com espera
  crescente, e os conjuntos longos gravam em lotes para uma falha tardia não
  jogar fora a coleta inteira.
- **404 não é falha de rede.** Na Câmara ele significa "esse ano não existe", e
  repetir não ajuda. O fim de uma série se descobre assim — ou, no Senado, por
  resposta 200 com lista vazia.
- **A memória da máquina entra na conta.** O teto de memória do DuckDB se adapta
  à RAM livre: pedir 6 GB com 2 GB livres não faz ele economizar, faz ele
  aceitar e falhar na primeira alocação grande.
