# Dicionário de dados

Gerado por `transformacao/documenta_banco.py` a partir do catálogo do banco.
Não editar à mão: a descrição vive no banco.

Uma fonte por schema; `main` guarda o que atravessa fontes.

# Schema `camara`

## `camara.deputado` (tabela)

Toda pessoa que exerceu mandato de deputado federal. Uma linha por pessoa, 7.890 no total. O CPF vem vazio em todas: a chave para cruzar com outras bases tem de ser nome civil, nascimento e UF.

Linhas: 7.890

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `nome` | VARCHAR | Nome de tratamento, como a pessoa e conhecida. |
| `nome_civil` | VARCHAR | Nome civil completo. Esta preenchido em todas as 7.890 linhas e e hoje a melhor chave disponivel para cruzar com outras bases, porque o CPF vem vazio. |
| `cpf` | VARCHAR | VEM VAZIO EM TODAS AS LINHAS. A coluna existe no arquivo da Camara e nao esta preenchida em nenhuma das 7.890. Mantida para o dia em que mudar, e para ninguem supor que a ingestao a perdeu. |
| `sexo` | VARCHAR | Sexo declarado, 'M' ou 'F'. Vem de siglaSexo. |
| `data_nascimento` | DATE | Data de nascimento. Preenchida em 7.006 das 7.890 linhas; ausente sobretudo nos deputados mais antigos. |
| `data_falecimento` | DATE | Data de falecimento, quando aplicavel. |
| `uf_nascimento` | VARCHAR | UF de nascimento. |
| `municipio_nascimento` | VARCHAR | Municipio de nascimento. |
| `legislatura_inicial` | INTEGER | Primeira legislatura em que a pessoa exerceu mandato na Camara. |
| `legislatura_final` | INTEGER | Ultima legislatura em que exerceu mandato. |
| `url_site` | VARCHAR | Site pessoal declarado. |
| `url_rede_social` | VARCHAR | Rede social declarada. |

## `camara.despesa` (tabela)

Cota para exercicio da atividade parlamentar, de 2008 a 2026: cada documento fiscal ressarcido a um deputado. Uma linha por documento, 5,2 milhoes no total. CUIDADO COM A CHAVE: o id de deputado aqui e o da cota, que nao e o id do resto da base. Valores em real corrente da data, sem correcao pela inflacao.

Linhas: 5.238.372

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_deputado_cota` | BIGINT | Id do deputado no sistema da cota parlamentar, que NAO e o mesmo id do resto da base - a cota tem numeracao propria. Cruzar por ele com camara.deputado produz resultado errado. |
| `nome_parlamentar` | VARCHAR | Nome do parlamentar na folha da cota. |
| `cpf` | VARCHAR | VEM VAZIO EM TODAS AS LINHAS. A coluna existe no arquivo da Camara e nao esta preenchida em nenhuma das 7.890. Mantida para o dia em que mudar, e para ninguem supor que a ingestao a perdeu. |
| `id_cadastro` | BIGINT | Id de cadastro do parlamentar na cota. |
| `uf` | VARCHAR | Sigla da UF pela qual foi eleito ou registrado. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro - do voto, da autoria, do cargo. Nao e a filiacao atual: o mesmo deputado aparece com siglas diferentes ao longo do tempo, e e isso que permite acompanhar troca de partido. |
| `legislatura` | INTEGER | Legislatura a que a despesa se refere. |
| `ano` | INTEGER | Ano da proposicao. NULL quando ela nao tem ano proprio - parecer, substitutivo e afins, 39% do total: a Camara grava zero nesses casos e a carga converte para NULL, porque zero como ano envenena qualquer agregacao por tempo. |
| `mes` | INTEGER | Mes de competencia da despesa, de 1 a 12. |
| `categoria` | VARCHAR | Categoria da despesa na cota: passagem, combustivel, divulgacao, consultoria e outras. |
| `subcategoria` | VARCHAR | Especificacao dentro da categoria. |
| `fornecedor` | VARCHAR | Nome do fornecedor do servico ou produto. |
| `fornecedor_doc` | VARCHAR | CNPJ ou CPF do fornecedor. |
| `emitido_em` | TIMESTAMP | Data de emissao do documento fiscal. |
| `valor_documento` | DOUBLE | Valor de face do documento fiscal. Unidade: real corrente da data, nao corrigido pela inflacao. |
| `valor_glosa` | DOUBLE | Parte do valor rejeitada na analise. Unidade: real corrente. |
| `valor_liquido` | DOUBLE | Valor efetivamente ressarcido: documento menos glosa. E este que soma o gasto de um deputado. Unidade: real corrente. |
| `passageiro` | VARCHAR | Nome do passageiro, nas despesas de passagem. |
| `trecho` | VARCHAR | Trecho da viagem, nas despesas de passagem. |
| `url_documento` | VARCHAR | URL do documento fiscal da despesa. |

## `camara.evento` (tabela)

Sessoes e reunioes da Camara, de 1991 a 2026, com local e pauta. Uma linha por evento.

Linhas: 62.732

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_evento` | BIGINT | Id da sessao ou reuniao em que a votacao ocorreu. |
| `inicio` | TIMESTAMP | Inicio do evento. |
| `fim` | TIMESTAMP | Fim do evento. |
| `situacao` | VARCHAR | Situacao do objeto no ultimo registro conhecido. |
| `descricao` | VARCHAR | Texto descritivo publicado pela Camara. |
| `tipo` | VARCHAR | Descricao do tipo, por extenso. |
| `local_externo` | VARCHAR | Local fora da Camara, quando o evento ocorreu fora. |
| `local_camara` | VARCHAR | Nome do local dentro da Camara. |
| `url_pauta` | VARCHAR | URL do documento de pauta do evento. |

## `camara.frente` (tabela)

Frentes parlamentares, com data de criacao e coordenador. Uma linha por frente.

Linhas: 1.443

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_frente` | BIGINT | Id da frente parlamentar. |
| `titulo` | VARCHAR | Titulo do objeto: da frente, da ocupacao, do cargo. |
| `data_criacao` | DATE | Data de criacao da frente parlamentar. |
| `id_legislatura` | INTEGER | Numero da legislatura, o periodo de quatro anos do mandato da Camara. A 57a vai de 2023 a 2027; a 1a comeca em 1826. |
| `situacao` | VARCHAR | Situacao do objeto no ultimo registro conhecido. |
| `palavras_chave` | VARCHAR | Palavras-chave atribuidas pela Camara. Texto livre, separadas por virgula; servem para busca, nao como classificacao fechada. |
| `id_coordenador` | BIGINT | Id do deputado que coordena a frente. |
| `nome_coordenador` | VARCHAR | Nome do coordenador da frente. |
| `partido_coordenador` | VARCHAR | Partido do coordenador. |
| `uf_coordenador` | VARCHAR | UF do coordenador. |

## `camara.frente_deputado` (tabela)

Composicao das frentes parlamentares. Uma linha por deputado em cada frente. E a tabela que mostra adesao tematica fora do partido.

Linhas: 262.271

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_frente` | BIGINT | Id da frente parlamentar. |
| `titulo` | VARCHAR | Titulo do objeto: da frente, da ocupacao, do cargo. |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `nome_deputado` | VARCHAR | Nome do deputado como consta no registro. |
| `uf` | VARCHAR | Sigla da UF pela qual foi eleito ou registrado. |
| `id_legislatura` | INTEGER | Numero da legislatura, o periodo de quatro anos do mandato da Camara. A 57a vai de 2023 a 2027; a 1a comeca em 1826. |
| `titulo_participacao` | VARCHAR | Papel do deputado na frente: titular, coordenador e afins. |
| `data_inicio` | DATE | Inicio da vigencia ou do periodo. |
| `data_fim` | DATE | Fim da vigencia ou do periodo. NULL quando segue em vigor. |

## `camara.legislatura` (tabela)

As 58 legislaturas da Camara, de 1826 a 2031, com o ano da eleicao que formou cada uma. Uma linha por legislatura.

Linhas: 58

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_legislatura` | INTEGER | Numero da legislatura, o periodo de quatro anos do mandato da Camara. A 57a vai de 2023 a 2027; a 1a comeca em 1826. |
| `data_inicio` | DATE | Inicio da vigencia ou do periodo. |
| `data_fim` | DATE | Fim da vigencia ou do periodo. NULL quando segue em vigor. |
| `ano_eleicao` | INTEGER | Ano da eleicao que formou a legislatura. |

## `camara.ocupacao` (tabela)

Ocupacao declarada pelo deputado fora da politica, com entidade e periodo. Uma linha por ocupacao declarada; a mesma pessoa tem varias.

Linhas: 37.763

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `titulo` | VARCHAR | Titulo do objeto: da frente, da ocupacao, do cargo. |
| `entidade` | VARCHAR | Entidade em que a ocupacao foi exercida. |
| `entidade_uf` | VARCHAR | UF da entidade. |
| `entidade_pais` | VARCHAR | Pais da entidade. |
| `ano_inicio` | INTEGER | Ano de inicio da ocupacao. |
| `ano_fim` | INTEGER | Ano de fim da ocupacao. |

## `camara.orgao` (tabela)

Comissoes, mesa diretora, plenario e demais orgaos da Camara, com periodo de vigencia. Uma linha por orgao.

Linhas: 3.888

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_orgao` | BIGINT | Id do orgao - comissao, mesa, plenario -, do fim da URI de origem. |
| `sigla` | VARCHAR | Sigla do objeto: do partido ou do orgao. |
| `nome` | VARCHAR | Nome de tratamento, como a pessoa e conhecida. |
| `apelido` | VARCHAR | Nome curto pelo qual o orgao e conhecido. |
| `tipo` | VARCHAR | Descricao do tipo, por extenso. |
| `cod_tipo` | INTEGER | Codigo numerico do tipo, como a Camara o publica. |
| `situacao` | VARCHAR | Situacao do objeto no ultimo registro conhecido. |
| `casa` | VARCHAR | Casa a que o orgao pertence. |
| `data_inicio` | DATE | Inicio da vigencia ou do periodo. |
| `data_instalacao` | DATE | Data em que o orgao foi instalado. |
| `data_fim` | DATE | Fim da vigencia ou do periodo. NULL quando segue em vigor. |

## `camara.orgao_deputado` (tabela)

Quem ocupou qual cargo em qual orgao, por legislatura. Uma linha por passagem de um deputado por um orgao, com cargo e periodo.

Linhas: 85.857

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_orgao` | BIGINT | Id do orgao - comissao, mesa, plenario -, do fim da URI de origem. |
| `sigla_orgao` | VARCHAR | Sigla do orgao em que a votacao ocorreu. |
| `nome_orgao` | VARCHAR | Nome do orgao por extenso. |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `nome_deputado` | VARCHAR | Nome do deputado como consta no registro. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro - do voto, da autoria, do cargo. Nao e a filiacao atual: o mesmo deputado aparece com siglas diferentes ao longo do tempo, e e isso que permite acompanhar troca de partido. |
| `uf` | VARCHAR | Sigla da UF pela qual foi eleito ou registrado. |
| `cargo` | VARCHAR | Cargo ocupado no orgao: presidente, relator, membro. |
| `data_inicio` | DATE | Inicio da vigencia ou do periodo. |
| `data_fim` | DATE | Fim da vigencia ou do periodo. NULL quando segue em vigor. |

## `camara.partido` (tabela)

Partidos com registro na Camara. Uma linha por partido. Nao tem data: e o cadastro atual, nao o historico de criacao e extincao.

Linhas: 104

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_partido` | INTEGER | Id do partido na Camara. |
| `sigla` | VARCHAR | Sigla do objeto: do partido ou do orgao. |
| `nome` | VARCHAR | Nome de tratamento, como a pessoa e conhecida. |

## `camara.profissao` (tabela)

Profissao declarada pelo deputado. Uma linha por declaracao.

Linhas: 12.692

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `titulo` | VARCHAR | Titulo do objeto: da frente, da ocupacao, do cargo. |
| `cod_tipo` | INTEGER | Codigo numerico do tipo, como a Camara o publica. |
| `registrado_em` | TIMESTAMP | Instante do registro da profissao. |

## `camara.proposicao` (tabela)

Projetos, emendas, requerimentos e pareceres apresentados na Camara, de 1945 a 2026. Uma linha por proposicao. 39% nao tem ano proprio - pareceres e substitutivos -, e nessas o campo ano e NULL.

Linhas: 993.049

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_proposicao` | BIGINT | Id da proposicao na Camara. |
| `sigla_tipo` | VARCHAR | Sigla do tipo da proposicao: PL, PEC, MPV, PAR, SBT e outras. |
| `tipo` | VARCHAR | Descricao do tipo, por extenso. |
| `numero` | INTEGER | Numero da proposicao dentro do tipo e do ano. Com o tipo e o ano, forma a identificacao publica (PL 1234/2023). |
| `ano` | INTEGER | Ano da proposicao. NULL quando ela nao tem ano proprio - parecer, substitutivo e afins, 39% do total: a Camara grava zero nesses casos e a carga converte para NULL, porque zero como ano envenena qualquer agregacao por tempo. |
| `apresentada_em` | TIMESTAMP | Instante de apresentacao da proposicao. |
| `ementa` | VARCHAR | Ementa oficial da proposicao, como registrada. |
| `ementa_detalhada` | VARCHAR | Versao longa da ementa, quando existe. |
| `palavras_chave` | VARCHAR | Palavras-chave atribuidas pela Camara. Texto livre, separadas por virgula; servem para busca, nao como classificacao fechada. |
| `situacao` | VARCHAR | Situacao do objeto no ultimo registro conhecido. |
| `tramitacao` | VARCHAR | Descricao do ultimo passo de tramitacao. |
| `orgao_atual` | VARCHAR | Sigla do orgao onde a proposicao estava. |
| `apreciacao` | VARCHAR | Regime de apreciacao: se a proposicao e decidida em plenario ou conclusivamente nas comissoes. |
| `status_em` | TIMESTAMP | Instante do ultimo registro de status. |
| `url_inteiro_teor` | VARCHAR | URL do texto integral da proposicao. |

## `camara.proposicao_autor` (tabela)

Autoria das proposicoes: liga proposicao a deputado, orgao ou Poder. Uma linha por assinatura, com a ordem e a marca de proponente - coautor que so assinou nao e o mesmo que quem propos.

Linhas: 1.919.153

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_proposicao` | BIGINT | Id da proposicao na Camara. |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `nome_autor` | VARCHAR | Nome do autor como registrado na proposicao. |
| `tipo_autor` | VARCHAR | Natureza do autor: deputado, orgao, Poder Executivo, cidadao. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro - do voto, da autoria, do cargo. Nao e a filiacao atual: o mesmo deputado aparece com siglas diferentes ao longo do tempo, e e isso que permite acompanhar troca de partido. |
| `uf` | VARCHAR | Sigla da UF pela qual foi eleito ou registrado. |
| `ordem_assinatura` | INTEGER | Posicao da assinatura na proposicao. 1 e o primeiro signatario. |
| `proponente` | INTEGER | 1 marca quem propos, distinguindo-o dos coautores que apenas assinaram. |

## `camara.proposicao_tema` (tabela)

Classificacao tematica das proposicoes, atribuida pela Camara. Uma linha por tema de cada proposicao; uma proposicao tem varios temas.

Linhas: 338.408

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_proposicao` | BIGINT | Id da proposicao na Camara. |
| `sigla_tipo` | VARCHAR | Sigla do tipo da proposicao: PL, PEC, MPV, PAR, SBT e outras. |
| `numero` | INTEGER | Numero da proposicao dentro do tipo e do ano. Com o tipo e o ano, forma a identificacao publica (PL 1234/2023). |
| `ano` | INTEGER | Ano da proposicao. NULL quando ela nao tem ano proprio - parecer, substitutivo e afins, 39% do total: a Camara grava zero nesses casos e a carga converte para NULL, porque zero como ano envenena qualquer agregacao por tempo. |
| `cod_tema` | INTEGER | Codigo do tema atribuido pela Camara. |
| `tema` | VARCHAR | Tema da proposicao, por extenso. |
| `relevancia` | INTEGER | Peso do tema na proposicao, atribuido pela Camara. |

## `camara.votacao` (tabela)

Votacoes realizadas na Camara, de 1988 a 2026, com o placar declarado. Uma linha por votacao.

Linhas: 194.412

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_votacao` | VARCHAR | Id da votacao na Camara, no formato '<idProposicao>-<sequencia>' (exemplo: 257161-367). Nao e numerico, de proposito: o segundo termo distingue votacoes do mesmo item na mesma sessao. |
| `data` | DATE | Data do registro. |
| `registrada_em` | TIMESTAMP | Instante em que a votacao foi registrada. |
| `id_orgao` | BIGINT | Id do orgao - comissao, mesa, plenario -, do fim da URI de origem. |
| `sigla_orgao` | VARCHAR | Sigla do orgao em que a votacao ocorreu. |
| `id_evento` | BIGINT | Id da sessao ou reuniao em que a votacao ocorreu. |
| `aprovacao` | VARCHAR | 1 quando a materia foi aprovada na votacao, 0 quando rejeitada. |
| `descricao` | VARCHAR | Texto descritivo publicado pela Camara. |
| `votos_sim` | INTEGER | Votos favoraveis declarados. Unidade: voto. |
| `votos_nao` | INTEGER | Votos contrarios declarados. Unidade: voto. |
| `votos_outros` | INTEGER | Abstencoes e demais registros que nao sao sim nem nao. Unidade: voto. |
| `id_proposicao` | BIGINT | Id da proposicao na Camara. |
| `proposicao_descricao` | VARCHAR | Identificacao da proposicao em texto, como a Camara a exibe. |

## `camara.votacao_objeto` (tabela)

O que foi efetivamente votado em cada votacao, ligando a votacao a proposicao. Uma linha por objeto votado.

Linhas: 825.484

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_votacao` | VARCHAR | Id da votacao na Camara, no formato '<idProposicao>-<sequencia>' (exemplo: 257161-367). Nao e numerico, de proposito: o segundo termo distingue votacoes do mesmo item na mesma sessao. |
| `data` | DATE | Data do registro. |
| `descricao` | VARCHAR | Texto descritivo publicado pela Camara. |
| `id_proposicao` | BIGINT | Id da proposicao na Camara. |
| `sigla_tipo` | VARCHAR | Sigla do tipo da proposicao: PL, PEC, MPV, PAR, SBT e outras. |
| `numero` | INTEGER | Numero da proposicao dentro do tipo e do ano. Com o tipo e o ano, forma a identificacao publica (PL 1234/2023). |
| `ano` | INTEGER | Ano da proposicao. NULL quando ela nao tem ano proprio - parecer, substitutivo e afins, 39% do total: a Camara grava zero nesses casos e a carga converte para NULL, porque zero como ano envenena qualquer agregacao por tempo. |
| `ementa` | VARCHAR | Ementa oficial da proposicao, como registrada. |
| `titulo` | VARCHAR | Titulo do objeto: da frente, da ocupacao, do cargo. |

## `camara.voto` (tabela)

O voto de cada deputado em cada votacao, de 2001 a 2026 - antes disso o Congresso votava nominal, mas o registro aberto nao existe. Uma linha por deputado por votacao. Conferido: o placar declarado bate com esta contagem em 6.045 das 6.058 votacoes com voto nominal.

Linhas: 1.927.219

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_votacao` | VARCHAR | Id da votacao na Camara, no formato '<idProposicao>-<sequencia>' (exemplo: 257161-367). Nao e numerico, de proposito: o segundo termo distingue votacoes do mesmo item na mesma sessao. |
| `votado_em` | TIMESTAMP | Instante do voto do deputado. |
| `voto` | VARCHAR | Voto do deputado como texto: 'Sim', 'Não', 'Abstenção', 'Obstrução', 'Artigo 17'. |
| `id_deputado` | BIGINT | Id do deputado na Camara. Vem do fim da URI do arquivo de origem (.../deputados/204382), porque o arquivo de deputados nao tem coluna de id. E a chave que liga voto, autoria, frente e cargo em orgao. |
| `nome_deputado` | VARCHAR | Nome do deputado como consta no registro. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro - do voto, da autoria, do cargo. Nao e a filiacao atual: o mesmo deputado aparece com siglas diferentes ao longo do tempo, e e isso que permite acompanhar troca de partido. |
| `uf` | VARCHAR | Sigla da UF pela qual foi eleito ou registrado. |
| `id_legislatura` | INTEGER | Numero da legislatura, o periodo de quatro anos do mandato da Camara. A 57a vai de 2023 a 2027; a 1a comeca em 1826. |

# Schema `main`

## `main.coleta` (tabela)

Registro de procedencia: uma linha por arquivo que entrou na base, com a URL de origem, o instante do download, o tamanho, as linhas e o sha256. E o que sustenta a promessa de que cada numero do portal volta a fonte oficial e a data da coleta. Gravada por ingestao/comum.py; conferida contra os portais por ingestao/confere_coleta.py.

Linhas: 843

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `fonte` | VARCHAR | Orgao de origem do arquivo: 'tse', 'camara', 'senado' e assim por diante. Define a pasta em dados/parquet e, no banco, o schema da fonte. |
| `conjunto` | VARCHAR | Conjunto de dados dentro da fonte, no nome que o proprio portal usa: 'votacoesVotos', 'proposicoes', 'bu_2026'. |
| `arquivo` | VARCHAR | Nome do Parquet gravado em dados/parquet/<fonte>/<conjunto>/. |
| `url` | VARCHAR | URL exata de onde o arquivo foi baixado, para qualquer pessoa refazer o caminho ate a fonte oficial. |
| `baixado_em` | TIMESTAMP | Instante do download, no horario local da maquina que rodou a ingestao. E a 'data da coleta' que o portal cita ao lado de cada numero. |
| `bytes` | BIGINT | Tamanho do arquivo baixado da origem, em bytes, conferido contra o Content-Length declarado pelo portal - download incompleto falha em vez de entrar na base. |
| `linhas` | BIGINT | Linhas gravadas no Parquet resultante. |
| `sha256` | VARCHAR | Hash do conteudo baixado, para detectar que a origem mudou entre duas coletas. |
| `observacao` | VARCHAR | Vazio quando a carga foi limpa. Quando o CSV de origem nao obedece ao padrao, guarda quantas linhas e de que tipo foi o defeito, e como o leitor foi relaxado - para o caminho diferente nao ficar invisivel depois. |

# Schema `senado`

## `senado.colegiado` (tabela)

Comissoes e demais colegiados em atividade no Senado e no Congresso. Uma linha por colegiado.

Linhas: 213

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo` | INTEGER | Codigo do objeto no Senado: do partido ou do colegiado. |
| `sigla` | VARCHAR | Sigla do partido ou do colegiado. |
| `nome` | VARCHAR | Nome parlamentar, como a pessoa e conhecida. |
| `casa` | VARCHAR | Casa do registro: SF (Senado) ou CN (Congresso). |
| `sigla_tipo` | VARCHAR | Sigla do tipo de colegiado. |
| `tipo` | VARCHAR | Tipo do objeto, por extenso. |
| `codigo_tipo` | INTEGER | Codigo do tipo de colegiado. |
| `data_inicio` | DATE | Inicio do periodo. |
| `publica` | VARCHAR | Marca se o colegiado tem atividade publica. |
| `finalidade` | VARCHAR | Finalidade declarada do colegiado. |

## `senado.filiacao` (tabela)

Historico de filiacao partidaria dos senadores. Uma linha por filiacao. E a materia-prima para acompanhar troca de partido: dos 2.052 senadores, 657 tem mais de uma filiacao, e o maior numero de filiacoes de uma mesma pessoa e 8.

Linhas: 3.312

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo_parlamentar` | BIGINT | Codigo do senador no Senado. E a chave que liga voto, mandato e filiacao; nao tem relacao com o id de deputado da Camara. |
| `codigo_partido` | INTEGER | Codigo do partido no Senado. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro, nao a filiacao atual. |
| `nome_partido` | VARCHAR | Nome do partido por extenso. |
| `data_filiacao` | DATE | Data de filiacao ao partido. |
| `data_desfiliacao` | DATE | Data de desfiliacao. NULL quando a filiacao segue valendo. |
| `ano_filiacao` | INTEGER | Ano de filiacao. Preenchido em 546 das 3.312 linhas - a serie com ano e muito menor que a serie com data. |
| `ano_desfiliacao` | INTEGER | Ano de desfiliacao, quando informado. |

## `senado.legislatura` (tabela)

As 59 legislaturas do Senado, de 1826 a 2035. Uma linha por legislatura. O mandato de senador dura oito anos e atravessa duas.

Linhas: 59

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `numero` | INTEGER | Numero da legislatura, na tabela legislatura; numero da materia, nas demais. |
| `data_inicio` | DATE | Inicio do periodo. |
| `data_fim` | DATE | Fim do periodo. NULL quando segue em vigor. |
| `data_eleicao` | DATE | Data da eleicao que formou a legislatura. |
| `sessoes_json` | VARCHAR | Sessoes legislativas da legislatura, em JSON de texto. |

## `senado.mandato` (tabela)

Mandatos de senador, com UF, partido, titularidade e suplentes. Uma linha por mandato, nao por pessoa.

Linhas: 3.827

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo_mandato` | BIGINT | Codigo do mandato, unico por mandato. |
| `codigo_parlamentar` | BIGINT | Codigo do senador no Senado. E a chave que liga voto, mandato e filiacao; nao tem relacao com o id de deputado da Camara. |
| `uf` | VARCHAR | Sigla da UF representada. |
| `participacao` | VARCHAR | Se o senador ocupa a vaga como Titular ou como Suplente. |
| `primeira_legislatura` | INTEGER | Primeira legislatura coberta - do mandato, ou em que o senador apareceu. |
| `segunda_legislatura` | INTEGER | Segunda legislatura do mandato de oito anos. |
| `data_inicio` | DATE | Inicio do periodo. |
| `data_fim` | DATE | Fim do periodo. NULL quando segue em vigor. |
| `codigo_partido` | INTEGER | Codigo do partido no Senado. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro, nao a filiacao atual. |
| `nome_partido` | VARCHAR | Nome do partido por extenso. |
| `codigo_titular` | BIGINT | Codigo do senador titular, quando a linha e de suplente. |
| `nome_titular` | VARCHAR | Nome do senador titular da vaga. |
| `suplentes_json` | VARCHAR | Suplentes do mandato, em JSON de texto. |
| `exercicios_json` | VARCHAR | Periodos de exercicio efetivo do mandato, em JSON de texto - e por aqui que se ve afastamento e reassuncao. |

## `senado.norma` (tabela)

Normas juridicas federais, de 1826 a 2026: leis, decretos, medidas provisorias e emendas. Uma linha por norma, 243 mil no total. E a serie mais longa da base.

Linhas: 243.091

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_norma` | BIGINT | Id da norma juridica. |
| `tipo` | VARCHAR | Tipo do objeto, por extenso. |
| `tipo_descricao` | VARCHAR | Descricao do tipo de norma. |
| `norma` | VARCHAR | Identificacao curta da norma. |
| `norma_nome` | VARCHAR | Nome da norma por extenso. |
| `apelido` | VARCHAR | Nome pelo qual a materia ou norma e conhecida. |
| `numero` | VARCHAR | Numero da legislatura, na tabela legislatura; numero da materia, nas demais. |
| `letra` | VARCHAR | Letra que acompanha o numero da norma, quando ha. |
| `complemento` | VARCHAR | Complemento da identificacao da norma. |
| `reedicao` | INTEGER | Numero da reedicao, nas medidas provisorias. |
| `sequencia` | INTEGER | Sequencia da norma dentro do tipo e ano. |
| `ementa` | VARCHAR | Ementa oficial. |
| `assinada_em` | DATE | Data de assinatura da norma. |
| `ano_assinatura` | INTEGER | Ano de assinatura da norma. |

## `senado.partido` (tabela)

Partidos conhecidos pelo Senado, com data de criacao e de extincao. Uma linha por partido.

Linhas: 108

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo` | INTEGER | Codigo do objeto no Senado: do partido ou do colegiado. |
| `sigla` | VARCHAR | Sigla do partido ou do colegiado. |
| `nome` | VARCHAR | Nome parlamentar, como a pessoa e conhecida. |
| `data_criacao` | DATE | Data de criacao do partido. |
| `data_extincao` | DATE | Data de extincao do partido, quando houve. |

## `senado.processo` (tabela)

Processos legislativos em tramitacao ou tramitados no Senado, de 1946 a 2026 - o que a API antiga chamava de materia. Uma linha por processo.

Linhas: 163.279

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `id_processo` | BIGINT | Id do processo legislativo. |
| `codigo_materia` | BIGINT | Codigo da materia legislativa. |
| `identificacao` | VARCHAR | Identificacao publica do processo. |
| `apelido` | VARCHAR | Nome pelo qual a materia ou norma e conhecida. |
| `tipo_documento` | VARCHAR | Tipo do documento que originou o processo. |
| `tipo_conteudo` | VARCHAR | Natureza do conteudo do processo. |
| `casa` | VARCHAR | Casa do registro: SF (Senado) ou CN (Congresso). |
| `ente` | VARCHAR | Ente que identificou o processo. |
| `autoria` | VARCHAR | Autoria da materia, em texto livre. |
| `ementa` | VARCHAR | Ementa oficial. |
| `objetivo` | VARCHAR | Objetivo declarado do processo. |
| `situacao` | VARCHAR | Situacao atual do processo. |
| `tramitando` | BOOLEAN | Verdadeiro quando o processo segue em tramitacao. |
| `norma_gerada` | VARCHAR | Norma que resultou do processo, quando houve. |
| `apresentado_em` | DATE | Data de apresentacao do processo. |
| `situacao_em` | DATE | Data da situacao atual do processo. |
| `deliberado_em` | DATE | Data da ultima deliberacao. |
| `tipo_deliberacao` | VARCHAR | Sigla do tipo da ultima deliberacao. |
| `atualizado_em` | TIMESTAMP | Instante da ultima atualizacao no portal. |
| `url_documento` | VARCHAR | URL do documento do processo. |

## `senado.senador` (tabela)

A pessoa, consolidada de senador_legislatura: 2.052 senadores, com a primeira e a ultima legislatura em que aparecem. Uma linha por pessoa.

Linhas: 2.052

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo_parlamentar` | BIGINT | Codigo do senador no Senado. E a chave que liga voto, mandato e filiacao; nao tem relacao com o id de deputado da Camara. |
| `nome` | VARCHAR | Nome parlamentar, como a pessoa e conhecida. |
| `nome_completo` | VARCHAR | Nome civil completo. |
| `sexo` | VARCHAR | Sexo declarado, por extenso. |
| `tratamento` | VARCHAR | Forma de tratamento: 'Senador' ou 'Senadora'. |
| `ultima_legislatura` | INTEGER | Ultima legislatura em que o senador aparece na base. |
| `primeira_legislatura` | INTEGER | Primeira legislatura coberta - do mandato, ou em que o senador apareceu. |
| `legislaturas` | BIGINT | Em quantas legislaturas o senador aparece. Unidade: legislatura. |
| `url_pagina` | VARCHAR | Pagina oficial do senador. |
| `url_foto` | VARCHAR | Foto oficial do senador. |

## `senado.senador_legislatura` (tabela)

Quem exerceu mandato em cada legislatura. Uma linha por senador E legislatura - contar linhas aqui nao conta pessoas. A legislatura vem do nome do arquivo de origem, nao de dentro dele.

Linhas: 5.716

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `numero_legislatura` | INTEGER | Numero da legislatura do Senado. Atencao: o mandato de senador dura oito anos e atravessa DUAS legislaturas, ao contrario do de deputado. |
| `codigo_parlamentar` | BIGINT | Codigo do senador no Senado. E a chave que liga voto, mandato e filiacao; nao tem relacao com o id de deputado da Camara. |
| `nome` | VARCHAR | Nome parlamentar, como a pessoa e conhecida. |
| `nome_completo` | VARCHAR | Nome civil completo. |
| `sexo` | VARCHAR | Sexo declarado, por extenso. |
| `tratamento` | VARCHAR | Forma de tratamento: 'Senador' ou 'Senadora'. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro, nao a filiacao atual. |
| `uf` | VARCHAR | Sigla da UF representada. |
| `email` | VARCHAR | Endereco de correio eletronico oficial. |
| `url_pagina` | VARCHAR | Pagina oficial do senador. |
| `url_foto` | VARCHAR | Foto oficial do senador. |
| `mandatos_json` | VARCHAR | Mandatos do senador como vieram da API, em JSON de texto. A ingestao serializa a sublista em vez de descartar; a tabela mandato traz o mesmo conteudo em linhas. |

## `senado.votacao` (tabela)

Votacoes nominais de plenario, de 1991 a 2026. Uma linha por votacao. O PLACAR SO VEM NAS SECRETAS: nas 1.772 votacoes abertas os campos de total estao vazios e o placar tem de ser contado de senado.voto.

Linhas: 3.626

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo_votacao` | BIGINT | Codigo da votacao (codigoSessaoVotacao). E a chave da votacao SOZINHO: sequencial parece compor a chave mas e nulo na maioria das linhas. |
| `sequencial` | INTEGER | Sequencial da votacao na sessao. NULO em 2.719 das 3.626 votacoes e em 214 mil dos 287 mil votos - nao serve como parte de chave, porque NULL nao casa com NULL e a juncao descarta as linhas em silencio. |
| `codigo_sessao` | BIGINT | Codigo da sessao plenaria. |
| `data_sessao` | DATE | Data da sessao em que a votacao ocorreu. |
| `casa` | VARCHAR | Casa do registro: SF (Senado) ou CN (Congresso). |
| `tipo_sessao` | VARCHAR | Sigla do tipo de sessao plenaria. |
| `numero_sessao` | INTEGER | Numero da sessao plenaria no ano. |
| `materia` | VARCHAR | Identificacao da materia em texto, como o Senado a exibe (exemplo: PDL 995/2026). |
| `sigla_materia` | VARCHAR | Sigla do tipo da materia: PL, PEC, PDL, MSF. |
| `numero_materia` | INTEGER | Numero da materia dentro do tipo e do ano. |
| `ano_materia` | INTEGER | Ano da materia votada. |
| `codigo_materia` | BIGINT | Codigo da materia legislativa. |
| `id_processo` | BIGINT | Id do processo legislativo. |
| `descricao` | VARCHAR | Texto descritivo publicado pelo Senado. |
| `ementa` | VARCHAR | Ementa oficial. |
| `resultado` | VARCHAR | Resultado da votacao, por extenso. |
| `secreta` | VARCHAR | 'S' quando a votacao foi secreta, 'N' quando aberta. ATENCAO AO QUE ISSO IMPLICA NOS DADOS: na secreta o total declarado vem preenchido e cada voto individual aparece como 'Votou', sem revelar; na aberta o total vem VAZIO e o placar tem de ser contado dos votos nominais. |
| `votos_sim` | INTEGER | Total de votos favoraveis declarado. Preenchido SO nas votacoes secretas. Unidade: voto. |
| `votos_nao` | INTEGER | Total de votos contrarios declarado, so nas secretas. Unidade: voto. |
| `votos_abstencao` | INTEGER | Total de abstencoes declarado, so nas secretas. Unidade: voto. |
| `colegiado` | VARCHAR | Sigla do colegiado em que a votacao ocorreu. |

## `senado.voto` (tabela)

O voto de cada senador em cada votacao, de 1991 a 2026. Uma linha por senador por votacao. Nas votacoes secretas o voto aparece como 'Votou', sem revelar o sentido - o registro existe, a escolha nao e publicada.

Linhas: 287.754

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `codigo_votacao` | BIGINT | Codigo da votacao (codigoSessaoVotacao). E a chave da votacao SOZINHO: sequencial parece compor a chave mas e nulo na maioria das linhas. |
| `sequencial` | INTEGER | Sequencial da votacao na sessao. NULO em 2.719 das 3.626 votacoes e em 214 mil dos 287 mil votos - nao serve como parte de chave, porque NULL nao casa com NULL e a juncao descarta as linhas em silencio. |
| `codigo_parlamentar` | BIGINT | Codigo do senador no Senado. E a chave que liga voto, mandato e filiacao; nao tem relacao com o id de deputado da Camara. |
| `nome` | VARCHAR | Nome parlamentar, como a pessoa e conhecida. |
| `sexo` | VARCHAR | Sexo declarado, por extenso. |
| `sigla_partido` | VARCHAR | Sigla do partido no momento do registro, nao a filiacao atual. |
| `uf` | VARCHAR | Sigla da UF representada. |
| `voto` | VARCHAR | Voto do senador: 'Sim', 'Não', 'Abstenção' nas votacoes abertas; 'Votou' nas secretas, em que o sentido do voto nao e publicado; e os codigos de ausencia (P-NRV, AP, LS, NCom, MIS, LP, REP). |
| `voto_descricao` | VARCHAR | O codigo de voto por extenso, quando existe - 'Presente – Não registrou voto', 'Licença saúde' e os demais motivos de ausencia. |
| `data_sessao` | DATE | Data da sessao em que a votacao ocorreu. |
| `materia` | VARCHAR | Identificacao da materia em texto, como o Senado a exibe (exemplo: PDL 995/2026). |

# Schema `tse`

## `tse.bu` (view)

Boletins de urna de 2026 (Presidente e Governador, 1o e 2o turno) como vieram do TSE. Uma linha por secao, cargo e votavel. Origem: CSV bweb do Portal de Dados Abertos, gravado pelo TSE; carregado por ingestao/tse/boletins_urna.py.

Linhas: 9.042.567

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `turno` | SMALLINT | 1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). Vem de NR_TURNO do bweb. |
| `uf` | VARCHAR | Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. Vem de SG_UF. |
| `cd_municipio` | INTEGER | Codigo do municipio na Justica Eleitoral, que nao e o codigo do IBGE. Vem de CD_MUNICIPIO. |
| `municipio` | VARCHAR | Nome do municipio. Vem de NM_MUNICIPIO. |
| `zona` | INTEGER | Numero da zona eleitoral dentro da UF. Vem de NR_ZONA. |
| `secao` | INTEGER | Numero da secao eleitoral dentro da zona. Vem de NR_SECAO. Corresponde a uma urna. |
| `local_votacao` | INTEGER | Numero do local de votacao (o predio) dentro da zona. Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao entre turnos. |
| `cargo` | VARCHAR | Cargo disputado: 'Presidente' ou 'Governador'. Vem de DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: AC, AM, DF, ES, RN e TO. |
| `nr_partido` | INTEGER | Numero do partido do candidato. Vem de NR_PARTIDO. |
| `sg_partido` | VARCHAR | Sigla do partido. Vem de SG_PARTIDO; vale '#NULO#' nas linhas de branco e nulo. |
| `tipo_votavel` | VARCHAR | Natureza do voto: Nominal, Legenda, Branco ou Nulo. Vem de DS_TIPO_VOTAVEL. |
| `nr_votavel` | BIGINT | Numero digitado na urna. Vem de NR_VOTAVEL; 95 identifica branco e 96 identifica nulo. |
| `nm_votavel` | VARCHAR | Nome do candidato como aparece na urna. Vem de NM_VOTAVEL; vale 'Branco' ou 'Nulo' nas linhas correspondentes. |
| `votos` | INTEGER | Votos apurados. Vem de QT_VOTOS. Unidade: voto. |
| `aptos` | INTEGER | Eleitores aptos naquele cargo. Vem de QT_APTOS. Unidade: eleitor. |
| `comparecimento` | INTEGER | Eleitores que compareceram. Vem de QT_COMPARECIMENTO. Unidade: eleitor. |
| `abstencoes` | INTEGER | Aptos que nao compareceram. Vem de QT_ABSTENCOES. Unidade: eleitor. |
| `secoes_agregadas` | VARCHAR | Secoes cujo eleitorado foi somado nesta. '#NULO#' quando nao houve agregacao. Vem de DS_SECOES_AGREGADAS. O conteudo muda entre turnos, por isso a comparacao e feita por local. |
| `dt_abertura` | TIMESTAMP | Instante em que a urna ficou pronta para receber votos, no horario LOCAL da urna, nao no de Brasilia. Vem de DT_ABERTURA. |
| `dt_encerramento` | TIMESTAMP | Instante do encerramento, tambem no horario local da urna. Vem de DT_ENCERRAMENTO. |
| `nr_urna` | BIGINT | Numero de serie da urna que gerou o boletim. Vem de NR_URNA_EFETIVADA. |
| `biom_sem_habilitacao` | BIGINT | Eleitores da secao sem habilitacao biometrica. Vem de QT_ELEI_BIOM_SEM_HABILITACAO. Unidade: eleitor. |

## `tse.fluxo_estimado` (tabela)

Matriz de fluxo de votos do 1o para o 2o turno, ESTIMADA por regressao ecologica no nivel do local de votacao, por transformacao/tse/estima_fluxo.py. Uma linha por cargo, escopo, origem e destino. NAO e migracao medida: o voto e secreto e o dado e agregado, entao movimentos opostos dentro do mesmo local se cancelam (falacia ecologica) e o que sai aqui e o fluxo LIQUIDO - a lealdade de um candidato e um teto e a troca entre candidatos um piso. Cada celula vem com faixa de 95% por bootstrap de municipios; faixa larga significa que o dado nao decide aquela celula.

Linhas: 1.760

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `cargo` | VARCHAR | 'Presidente' tem matriz por UF e matriz nacional. 'Governador' so tem matriz por UF, e apenas nas 6 que tiveram 2o turno (AC, AM, DF, ES, RN, TO): cada estado disputou entre candidatos proprios, e uma matriz nacional misturaria nomes que nunca estiveram na mesma urna. |
| `escopo` | VARCHAR | Recorte em que a regressao rodou: 'UF' para a matriz estimada dentro de um estado, 'BRASIL' para a media das 27 matrizes estaduais ponderada pelos eleitores de cada origem - esse e o numero publicado - e 'BRASIL_DIRETO' para uma unica regressao no pais inteiro, que fica gravada so como contraste: ela supoe comportamento igual em todo o territorio e por isso crava 0% ou 100% em 27 das 50 celulas, contra 2 na estimativa por UF. |
| `uf` | VARCHAR | Sigla da UF quando escopo = 'UF'; NULL nos escopos nacionais. O exterior ('ZZ') nao entra: sao poucos locais para a regressao. |
| `origem` | VARCHAR | Rotulo escolhido no 1o turno: candidato, BRANCO, NULO, ABSTENCAO, ou OUTROS para o conjunto dos candidatos com menos de 0,2% dos aptos, cuja coluna de regressao e quase constante entre locais e nao identifica coeficiente proprio. |
| `destino` | VARCHAR | Rotulo escolhido no 2o turno, nos mesmos termos de origem. |
| `eleitores_origem` | HUGEINT | Eleitores que escolheram a origem no 1o turno, dentro do escopo. E o denominador de fracao. Unidade: eleitor. |
| `fracao` | DOUBLE | Parcela da origem estimada como tendo ido para o destino. Fracao entre 0 e 1, nao percentual. Por construcao, as fracoes de uma mesma origem somam 1. |
| `fracao_min` | DOUBLE | Limite inferior da faixa de 95% de fracao, percentil 2,5 de 150 replicas de bootstrap que reamostram os MUNICIPIOS do escopo - nao os locais, que dentro de um municipio se parecem e estreitariam a faixa artificialmente. No DF, onde o municipio e unico, a reamostragem desce para a zona eleitoral. |
| `fracao_max` | DOUBLE | Limite superior da faixa de 95% de fracao, percentil 97,5 das mesmas replicas. |
| `eleitores` | HUGEINT | fracao x eleitores_origem: eleitores estimados nesse fluxo. Unidade: eleitor. |
| `eleitores_min` | HUGEINT | fracao_min x eleitores_origem. Unidade: eleitor. |
| `eleitores_max` | HUGEINT | fracao_max x eleitores_origem. Unidade: eleitor. |
| `locais` | BIGINT | Locais de votacao que sustentaram a regressao do escopo, ja descontado o local sem par entre os turnos. Unidade: local. |
| `municipios` | BIGINT | Municipios presentes no escopo. Unidade: municipio. |

## `tse.fluxo_insumo` (tabela)

Insumo do infografico de fluxo: cada rotulo disputado mais a abstencao, com a fracao sobre os aptos. Uma linha por turno, cargo, local e rotulo. A soma de votos por turno e cargo fecha exatamente no total de aptos (conferido: diferenca zero nos quatro cortes).

Linhas: 2.170.304

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `turno` | SMALLINT | 1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). Vem de NR_TURNO do bweb. |
| `cargo` | VARCHAR | Cargo disputado: 'Presidente' ou 'Governador'. Vem de DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: AC, AM, DF, ES, RN e TO. |
| `uf` | VARCHAR | Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. Vem de SG_UF. |
| `cd_municipio` | INTEGER | Codigo do municipio na Justica Eleitoral, que nao e o codigo do IBGE. Vem de CD_MUNICIPIO. |
| `municipio` | VARCHAR | Nome do municipio. Vem de NM_MUNICIPIO. |
| `zona` | INTEGER | Numero da zona eleitoral dentro da UF. Vem de NR_ZONA. |
| `local_votacao` | INTEGER | Numero do local de votacao (o predio) dentro da zona. Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao entre turnos. |
| `rotulo` | VARCHAR | Mesmos rotulos de votos_local, mais ABSTENCAO, que entra como destino para o fluxo fechar em 100% dos aptos. |
| `votos` | HUGEINT | Votos do rotulo, ou eleitores que se abstiveram quando o rotulo e ABSTENCAO. Unidade: voto, exceto nessa linha, em que e eleitor. |
| `aptos` | HUGEINT | Aptos do local naquele cargo e turno, usado como denominador de fracao_aptos. Unidade: eleitor. |
| `fracao_aptos` | DOUBLE | votos / aptos. Fracao entre 0 e 1, nao percentual. |

## `tse.local` (tabela)

Eleitorado agregado por local de votacao e cargo. Uma linha por turno, cargo e local. Derivada de secao. O local e a unidade de comparacao entre turnos porque os agrupamentos de secoes agregadas mudam de um turno para o outro.

Linhas: 291.143

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `turno` | SMALLINT | 1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). Vem de NR_TURNO do bweb. |
| `cargo` | VARCHAR | Cargo disputado: 'Presidente' ou 'Governador'. Vem de DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: AC, AM, DF, ES, RN e TO. |
| `uf` | VARCHAR | Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. Vem de SG_UF. |
| `cd_municipio` | INTEGER | Codigo do municipio na Justica Eleitoral, que nao e o codigo do IBGE. Vem de CD_MUNICIPIO. |
| `municipio` | VARCHAR | Nome do municipio. Vem de NM_MUNICIPIO. |
| `zona` | INTEGER | Numero da zona eleitoral dentro da UF. Vem de NR_ZONA. |
| `local_votacao` | INTEGER | Numero do local de votacao (o predio) dentro da zona. Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao entre turnos. |
| `qt_secoes` | BIGINT | Secoes somadas neste local naquele cargo. Unidade: secao. |
| `aptos` | HUGEINT | Eleitores aptos naquele cargo. Vem de QT_APTOS. Unidade: eleitor. |
| `comparecimento` | HUGEINT | Eleitores que compareceram. Vem de QT_COMPARECIMENTO. Unidade: eleitor. |
| `abstencoes` | HUGEINT | Aptos que nao compareceram. Vem de QT_ABSTENCOES. Unidade: eleitor. |
| `secoes_com_agregacao` | BIGINT | Quantas dessas secoes agregam eleitorado de outra. Serve para medir o ruido da comparacao entre turnos. Unidade: secao. |

## `tse.secao` (tabela)

Eleitorado de cada secao em cada cargo. Uma linha por turno, cargo e secao. Derivada de bu. A chave inclui o cargo porque aptos e comparecimento divergem entre Presidente e Governador em 19.776 secoes: o eleitor em transito vota so para Presidente.

Linhas: 1.536.047

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `turno` | SMALLINT | 1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). Vem de NR_TURNO do bweb. |
| `cargo` | VARCHAR | Cargo disputado: 'Presidente' ou 'Governador'. Vem de DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: AC, AM, DF, ES, RN e TO. |
| `uf` | VARCHAR | Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. Vem de SG_UF. |
| `cd_municipio` | INTEGER | Codigo do municipio na Justica Eleitoral, que nao e o codigo do IBGE. Vem de CD_MUNICIPIO. |
| `municipio` | VARCHAR | Nome do municipio. Vem de NM_MUNICIPIO. |
| `zona` | INTEGER | Numero da zona eleitoral dentro da UF. Vem de NR_ZONA. |
| `secao` | INTEGER | Numero da secao eleitoral dentro da zona. Vem de NR_SECAO. Corresponde a uma urna. |
| `local_votacao` | INTEGER | Numero do local de votacao (o predio) dentro da zona. Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao entre turnos. |
| `aptos` | INTEGER | Eleitores aptos naquele cargo. Vem de QT_APTOS. Unidade: eleitor. |
| `comparecimento` | INTEGER | Eleitores que compareceram. Vem de QT_COMPARECIMENTO. Unidade: eleitor. |
| `abstencoes` | INTEGER | Aptos que nao compareceram. Vem de QT_ABSTENCOES. Unidade: eleitor. |
| `secoes_agregadas` | VARCHAR | Secoes cujo eleitorado foi somado nesta. '#NULO#' quando nao houve agregacao. Vem de DS_SECOES_AGREGADAS. O conteudo muda entre turnos, por isso a comparacao e feita por local. |
| `dt_abertura` | TIMESTAMP | Instante em que a urna ficou pronta para receber votos, no horario LOCAL da urna, nao no de Brasilia. Vem de DT_ABERTURA. |
| `dt_encerramento` | TIMESTAMP | Instante do encerramento, tambem no horario local da urna. Vem de DT_ENCERRAMENTO. |

## `tse.votos_local` (tabela)

Votos somados por local de votacao, cargo e votavel. Uma linha por turno, cargo, local e rotulo. Derivada de bu.

Linhas: 1.879.161

| Coluna | Tipo | Descrição |
| --- | --- | --- |
| `turno` | SMALLINT | 1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). Vem de NR_TURNO do bweb. |
| `cargo` | VARCHAR | Cargo disputado: 'Presidente' ou 'Governador'. Vem de DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: AC, AM, DF, ES, RN e TO. |
| `uf` | VARCHAR | Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. Vem de SG_UF. |
| `cd_municipio` | INTEGER | Codigo do municipio na Justica Eleitoral, que nao e o codigo do IBGE. Vem de CD_MUNICIPIO. |
| `municipio` | VARCHAR | Nome do municipio. Vem de NM_MUNICIPIO. |
| `zona` | INTEGER | Numero da zona eleitoral dentro da UF. Vem de NR_ZONA. |
| `local_votacao` | INTEGER | Numero do local de votacao (o predio) dentro da zona. Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao entre turnos. |
| `rotulo` | VARCHAR | Identidade do destino do voto: nome do candidato quando nominal, 'LEGENDA <sigla>' no voto de legenda, ou BRANCO / NULO. Normalizado em maiusculas. |
| `tipo_votavel` | VARCHAR | Natureza do voto: Nominal, Legenda, Branco ou Nulo. Vem de DS_TIPO_VOTAVEL. |
| `nr_votavel` | BIGINT | Numero digitado na urna. Vem de NR_VOTAVEL; 95 identifica branco e 96 identifica nulo. |
| `votos` | HUGEINT | Votos apurados. Vem de QT_VOTOS. Unidade: voto. |
