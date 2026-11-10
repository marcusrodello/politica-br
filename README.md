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
ingestao/<fonte>/      baixa o dado aberto e grava Parquet
transformacao/<fonte>/ monta as tabelas no DuckDB e documenta o catálogo
dados/                 Parquet e banco (não versionado; se regera dos scripts)
docs/                  brief, dicionários de dados e notas por módulo
```

Uma pasta por fonte, dentro de `ingestao/` e `transformacao/`. Só `tse/`
existe hoje. Banco único em `dados/politica_br.duckdb`.

## Estado atual

| Fonte | Situação |
| --- | --- |
| TSE — boletins de urna 2026 | carregado; 9,0 milhões de linhas, 94.709 locais de votação |
| Câmara, Senado, STF, IBGE, Ipea | não iniciado |

Detalhe do módulo do TSE, com as armadilhas dos dados e os limites do que a
base permite afirmar: [`docs/tse-2026-migracao-votos.md`](docs/tse-2026-migracao-votos.md).
Dicionário de dados: [`docs/dicionario-tse-2026.md`](docs/dicionario-tse-2026.md),
gerado do catálogo do banco.

## Como reconstruir a base

```
python ingestao/tse/boletins_urna.py       # baixa os 56 pacotes do TSE e grava Parquet
python transformacao/tse/monta_banco.py    # monta as tabelas e roda as conferências
python transformacao/tse/documenta_banco.py # grava as descrições no banco e regera o dicionário
```

`boletins_urna.py` é retomável: reexecutar pula o que já tem Parquet válido.
Ele confere se o Parquet abre antes de pular, porque uma execução interrompida
deixa arquivo truncado que só acusa erro muito depois, na leitura.

Nada em `dados/` ou `_tmp/` está versionado.

## Próximos passos

1. estimativa dos fluxos de 2026 por local de votação e o infográfico
2. separar as tabelas por fonte em schemas do DuckDB (`tse.bu`, `camara.…`) —
   hoje tudo vive em `main` e os nomes genéricos (`bu`, `secao`, `local`) vão
   colidir quando entrar a segunda fonte
3. ingestão da Câmara e do Senado, e a padronização de identidade de político
   entre as bases, que é o maior desafio do projeto
4. site estático com perfil de político e página de eleição
