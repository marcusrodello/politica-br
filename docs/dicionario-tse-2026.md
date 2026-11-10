# Dicionário de dados — TSE, eleição de 2026

Gerado por `transformacao/tse/documenta_banco.py` a partir do catálogo do banco.
Não editar à mão: a descrição vive no banco.

## `bu` (view)

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

## `fluxo_insumo` (tabela)

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

## `local` (tabela)

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

## `secao` (tabela)

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

## `votos_local` (tabela)

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
