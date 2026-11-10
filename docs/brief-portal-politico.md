# Portal Político: dados oficiais para o cidadão

brief para iniciar o projeto no Claude Code. objetivo: portal público e gratuito que reúne dados políticos oficiais do Brasil num só lugar, para o cidadão comparar governos, políticos e partidos e tirar as próprias conclusões, funcionando como porto seguro contra desinformação.

## visão

- portal público, gratuito, voltado à população
- reúne dado oficial espalhado por muitas fontes num só lugar, com a pergunta já respondida em gráfico
- diferencial: fonte oficial rastreável mais uma camada histórica que dá contexto, não número solto
- nunca seria descontinuado; um eventual produto pago para empresas seria separado, só para custear o portal

## princípios (inegociáveis)

- não inventar dados: servir o dado como ele existe, completo ou parcial
- quando documentos oficiais se contradizem, exibir os dois e deixar o usuário concluir
- cada número rastreável até a fonte oficial e à data da coleta
- neutralidade: o portal mostra fato, não opinião. a leitura é do cidadão

## fontes de dados

- TSE (dadosabertos.tse.jus.br): resultados de eleição, candidatos, eleitorado, prestação de contas. ponto de partida, já em andamento
- Câmara dos Deputados (dadosabertos.camara.leg.br): deputados, proposições, votações nominais
- Senado Federal (dados abertos legislativos): senadores, matérias, votações
- STF: decisões e jurisprudência, fonte menos estruturada, tratar com cuidado
- indicadores sociais e econômicos: IBGE e Ipeadata (PIB, IDH, séries históricas)

os endpoints exatos o Claude Code confirma na hora; aqui ficam os portais de onde puxar.

## arquitetura (mesma espinha do F1 by Lap)

1. **ingestão**: scripts Python, um por fonte, baixando os dados abertos com cache e registro da data de coleta
2. **armazenamento**: Parquet por fonte e ano, mais DuckDB para consulta
3. **transformação**: camada SQL (dbt) padronizando nome de político, partido e cargo entre as fontes. esse é o maior desafio do projeto: a mesma pessoa aparece escrita diferente em cada base
4. **orquestração**: GitHub Actions agendado, cadência por fonte (legislativo semanal, indicadores quando saem)
5. **site**: gerador estático de dashboards (Evidence.dev ou Observable Framework)
6. **hospedagem**: Cloudflare Pages, deploy automático
7. **dados abertos**: Parquet disponível para download, para outros usarem e citarem o portal

## funcionalidades

v1 (fundação factual, baixo risco):

- perfil do político: partido, cargos ao longo do tempo, histórico de votação
- comparador de governos e partidos por indicadores oficiais
- página de eleição: resultados por cargo, região e ano, a partir do TSE

futuras:

- linha do tempo histórica (barra horizontal com partido e cargo de cada político no período, cruzada com PIB, IDH e fatos marcantes)
- apuração de eleição em tempo real (modelo de projeção no espírito da cobertura do Estadão de 2026)
- termômetro político (posição num eixo pelas ações efetivas, não pelo discurso)

## dois pontos de design que mudam o resultado

- **apuração em tempo real** é a única parte que foge do "estático e grátis": em dia de eleição exige atualização de minuto em minuto. saída sem custo fixo: um workflow que roda em intervalo curto só no dia da eleição, lendo o boletim do TSE, em vez de servidor ligado o ano inteiro
- **termômetro político** é o módulo mais arriscado do projeto: qualquer classificação esquerda e direita vira acusação de viés e pode contaminar a credibilidade do portal factual inteiro. proposta: deixar para uma fase madura, com critério totalmente explícito e auditável (cada ponto no eixo rastreável a um voto ou ação específica) e separado visualmente do dado cru, para o leitor ver como a nota foi montada e poder discordar com base em fato

## roadmap

- **fase 0 (em andamento)**: explorar o layout dos dados do TSE da última eleição
- **fase 1**: repositório, Docker, ingestão do TSE para Parquet mais DuckDB
- **fase 2**: adicionar Câmara e Senado; resolver a padronização de identidade de político entre as bases (dbt)
- **fase 3**: site estático com perfil de político e página de eleição
- **fase 4**: indicadores (IBGE e Ipea) e comparador de governos
- **fase 5**: linha do tempo histórica
- **fase 6 (madura)**: apuração em tempo real e termômetro político

## estimativa de custo

| item | ferramenta | custo |
| --- | --- | --- |
| dados oficiais | TSE, Câmara, Senado, IBGE, Ipea | grátis |
| código e automação | GitHub mais GitHub Actions (repo público) | grátis |
| banco | DuckDB mais Parquet | grátis |
| transformação | dbt-core | grátis |
| site | Evidence.dev ou Observable Framework | grátis |
| hospedagem | Cloudflare Pages | grátis |
| domínio | no Registro.br | cerca de R$ 40 por ano |
| **total** |  | **cerca de R$ 40 por ano** |

ressalva honesta de custo, diferente do F1: o volume de dado do TSE é muito maior (resultado por seção eleitoral do país inteiro são gigabytes). se os arquivos passarem da franquia grátis de hospedagem, a saída é guardar só o dado agregado no site e o bruto no Cloudflare R2 (centavos por GB). ainda assim fica na casa de poucos reais por mês.

