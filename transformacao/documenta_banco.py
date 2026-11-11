"""Grava a descricao de cada objeto no proprio banco e regera o dicionario.

O banco e a fonte unica da descricao: os COMMENT abaixo sao a origem, e
docs/dicionario.md e gerado do catalogo (duckdb_tables / duckdb_columns), nunca
escrito a mao. Toda descricao foi conferida no dado ou no arquivo de origem.

COBERTURA POR SCHEMA, e nao tudo ou nada. Os schemas em CURADOS tem de estar
100% documentados e o script sai com erro se faltar uma coluna; os demais
entram no dicionario com as descricoes que existem e o relatorio diz quanto
falta. A alternativa seria exigir 400 descricoes de uma vez para as tabelas que
acabaram de entrar, o que na pratica levaria a escrever frase vazia para
cumprir a regra - pior que admitir a lacuna.
"""
import os
import sys

import duckdb

# raiz do repositorio, derivada do proprio arquivo: transformacao/ -> uma acima
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANCO = os.path.join(BASE, "dados", "politica_br.duckdb")
DOC = os.path.join(BASE, "docs", "dicionario.md")

# schemas que nao admitem coluna sem descricao
CURADOS = {"main", "tse", "camara", "senado"}

# descricao das tabelas por schema, porque o nome da tabela repete entre fontes:
# camara.votacao e senado.votacao sao coisas diferentes
TABELAS_POR_SCHEMA = {
    # ------------------------------- Camara -------------------------------
    ("camara", "legislatura"):
        "As 58 legislaturas da Camara, de 1826 a 2031, com o ano da eleicao "
        "que formou cada uma. Uma linha por legislatura.",
    ("camara", "partido"):
        "Partidos com registro na Camara. Uma linha por partido. Nao tem "
        "data: e o cadastro atual, nao o historico de criacao e extincao.",
    ("camara", "deputado"):
        "Toda pessoa que exerceu mandato de deputado federal. Uma linha por "
        "pessoa, 7.890 no total. O CPF vem vazio em todas: a chave para "
        "cruzar com outras bases tem de ser nome civil, nascimento e UF.",
    ("camara", "ocupacao"):
        "Ocupacao declarada pelo deputado fora da politica, com entidade e "
        "periodo. Uma linha por ocupacao declarada; a mesma pessoa tem varias.",
    ("camara", "profissao"):
        "Profissao declarada pelo deputado. Uma linha por declaracao.",
    ("camara", "orgao"):
        "Comissoes, mesa diretora, plenario e demais orgaos da Camara, com "
        "periodo de vigencia. Uma linha por orgao.",
    ("camara", "orgao_deputado"):
        "Quem ocupou qual cargo em qual orgao, por legislatura. Uma linha por "
        "passagem de um deputado por um orgao, com cargo e periodo.",
    ("camara", "frente"):
        "Frentes parlamentares, com data de criacao e coordenador. Uma linha "
        "por frente.",
    ("camara", "frente_deputado"):
        "Composicao das frentes parlamentares. Uma linha por deputado em cada "
        "frente. E a tabela que mostra adesao tematica fora do partido.",
    ("camara", "proposicao"):
        "Projetos, emendas, requerimentos e pareceres apresentados na Camara, "
        "de 1945 a 2026. Uma linha por proposicao. 39% nao tem ano proprio - "
        "pareceres e substitutivos -, e nessas o campo ano e NULL.",
    ("camara", "proposicao_autor"):
        "Autoria das proposicoes: liga proposicao a deputado, orgao ou Poder. "
        "Uma linha por assinatura, com a ordem e a marca de proponente - "
        "coautor que so assinou nao e o mesmo que quem propos.",
    ("camara", "proposicao_tema"):
        "Classificacao tematica das proposicoes, atribuida pela Camara. Uma "
        "linha por tema de cada proposicao; uma proposicao tem varios temas.",
    ("camara", "votacao"):
        "Votacoes realizadas na Camara, de 1988 a 2026, com o placar "
        "declarado. Uma linha por votacao.",
    ("camara", "voto"):
        "O voto de cada deputado em cada votacao, de 2001 a 2026 - antes "
        "disso o Congresso votava nominal, mas o registro aberto nao existe. "
        "Uma linha por deputado por votacao. Conferido: o placar declarado "
        "bate com esta contagem em 6.045 das 6.058 votacoes com voto nominal.",
    ("camara", "votacao_objeto"):
        "O que foi efetivamente votado em cada votacao, ligando a votacao a "
        "proposicao. Uma linha por objeto votado.",
    ("camara", "evento"):
        "Sessoes e reunioes da Camara, de 1991 a 2026, com local e pauta. "
        "Uma linha por evento.",
    ("camara", "despesa"):
        "Cota para exercicio da atividade parlamentar, de 2008 a 2026: cada "
        "documento fiscal ressarcido a um deputado. Uma linha por documento, "
        "5,2 milhoes no total. CUIDADO COM A CHAVE: o id de deputado aqui e o "
        "da cota, que nao e o id do resto da base. Valores em real corrente "
        "da data, sem correcao pela inflacao.",

    # ------------------------------- Senado -------------------------------
    ("senado", "legislatura"):
        "As 59 legislaturas do Senado, de 1826 a 2035. Uma linha por "
        "legislatura. O mandato de senador dura oito anos e atravessa duas.",
    ("senado", "partido"):
        "Partidos conhecidos pelo Senado, com data de criacao e de extincao. "
        "Uma linha por partido.",
    ("senado", "senador_legislatura"):
        "Quem exerceu mandato em cada legislatura. Uma linha por senador E "
        "legislatura - contar linhas aqui nao conta pessoas. A legislatura vem "
        "do nome do arquivo de origem, nao de dentro dele.",
    ("senado", "senador"):
        "A pessoa, consolidada de senador_legislatura: 2.052 senadores, com a "
        "primeira e a ultima legislatura em que aparecem. Uma linha por "
        "pessoa.",
    ("senado", "mandato"):
        "Mandatos de senador, com UF, partido, titularidade e suplentes. Uma "
        "linha por mandato, nao por pessoa.",
    ("senado", "filiacao"):
        "Historico de filiacao partidaria dos senadores. Uma linha por "
        "filiacao. E a materia-prima para acompanhar troca de partido: dos "
        "2.052 senadores, 657 tem mais de uma filiacao, e o maior numero de "
        "filiacoes de uma mesma pessoa e 8.",
    ("senado", "colegiado"):
        "Comissoes e demais colegiados em atividade no Senado e no Congresso. "
        "Uma linha por colegiado.",
    ("senado", "votacao"):
        "Votacoes nominais de plenario, de 1991 a 2026. Uma linha por "
        "votacao. O PLACAR SO VEM NAS SECRETAS: nas 1.772 votacoes abertas os "
        "campos de total estao vazios e o placar tem de ser contado de "
        "senado.voto.",
    ("senado", "voto"):
        "O voto de cada senador em cada votacao, de 1991 a 2026. Uma linha "
        "por senador por votacao. Nas votacoes secretas o voto aparece como "
        "'Votou', sem revelar o sentido - o registro existe, a escolha nao e "
        "publicada.",
    ("senado", "processo"):
        "Processos legislativos em tramitacao ou tramitados no Senado, de "
        "1946 a 2026 - o que a API antiga chamava de materia. Uma linha por "
        "processo.",
    ("senado", "norma"):
        "Normas juridicas federais, de 1826 a 2026: leis, decretos, medidas "
        "provisorias e emendas. Uma linha por norma, 243 mil no total. E a "
        "serie mais longa da base.",
}

TABELAS = {
    "coleta": "Registro de procedencia: uma linha por arquivo que entrou na "
              "base, com a URL de origem, o instante do download, o tamanho, "
              "as linhas e o sha256. E o que sustenta a promessa de que cada "
              "numero do portal volta a fonte oficial e a data da coleta. "
              "Gravada por ingestao/comum.py; conferida contra os portais por "
              "ingestao/confere_coleta.py.",
    "bu": "Boletins de urna de 2026 (Presidente e Governador, 1o e 2o turno) "
          "como vieram do TSE. Uma linha por secao, cargo e votavel. Origem: "
          "CSV bweb do Portal de Dados Abertos, gravado pelo TSE; carregado "
          "por ingestao/tse/boletins_urna.py.",
    "secao": "Eleitorado de cada secao em cada cargo. Uma linha por turno, "
             "cargo e secao. Derivada de bu. A chave inclui o cargo porque "
             "aptos e comparecimento divergem entre Presidente e Governador "
             "em 19.776 secoes: o eleitor em transito vota so para Presidente.",
    "local": "Eleitorado agregado por local de votacao e cargo. Uma linha por "
             "turno, cargo e local. Derivada de secao. O local e a unidade de "
             "comparacao entre turnos porque os agrupamentos de secoes "
             "agregadas mudam de um turno para o outro.",
    "votos_local": "Votos somados por local de votacao, cargo e votavel. Uma "
                   "linha por turno, cargo, local e rotulo. Derivada de bu.",
    "fluxo_insumo": "Insumo do infografico de fluxo: cada rotulo disputado "
                    "mais a abstencao, com a fracao sobre os aptos. Uma linha "
                    "por turno, cargo, local e rotulo. A soma de votos por "
                    "turno e cargo fecha exatamente no total de aptos "
                    "(conferido: diferenca zero nos quatro cortes).",
    "fluxo_estimado": "Matriz de fluxo de votos do 1o para o 2o turno, "
                      "ESTIMADA por regressao ecologica no nivel do local de "
                      "votacao, por transformacao/tse/estima_fluxo.py. Uma "
                      "linha por cargo, escopo, origem e destino. NAO e "
                      "migracao medida: o voto e secreto e o dado e agregado, "
                      "entao movimentos opostos dentro do mesmo local se "
                      "cancelam (falacia ecologica) e o que sai aqui e o fluxo "
                      "LIQUIDO - a lealdade de um candidato e um teto e a "
                      "troca entre candidatos um piso. Cada celula vem com "
                      "faixa de 95% por bootstrap de municipios; faixa larga "
                      "significa que o dado nao decide aquela celula.",
}

# descricao valida em qualquer tabela que tenha a coluna
COMUNS = {
    "turno": "1 = primeiro turno (04/10/2026), 2 = segundo turno (25/10/2026). "
             "Vem de NR_TURNO do bweb.",
    "cargo": "Cargo disputado: 'Presidente' ou 'Governador'. Vem de "
             "DS_CARGO_PERGUNTA. Governador tem 2o turno em apenas 6 UFs: "
             "AC, AM, DF, ES, RN e TO.",
    "uf": "Sigla da unidade federativa; 'ZZ' identifica as secoes do exterior. "
          "Vem de SG_UF.",
    "cd_municipio": "Codigo do municipio na Justica Eleitoral, que nao e o "
                    "codigo do IBGE. Vem de CD_MUNICIPIO.",
    "municipio": "Nome do municipio. Vem de NM_MUNICIPIO.",
    "zona": "Numero da zona eleitoral dentro da UF. Vem de NR_ZONA.",
    "secao": "Numero da secao eleitoral dentro da zona. Vem de NR_SECAO. "
             "Corresponde a uma urna.",
    "local_votacao": "Numero do local de votacao (o predio) dentro da zona. "
                     "Vem de NR_LOCAL_VOTACAO. E a unidade de comparacao "
                     "entre turnos.",
    "nr_partido": "Numero do partido do candidato. Vem de NR_PARTIDO.",
    "sg_partido": "Sigla do partido. Vem de SG_PARTIDO; vale '#NULO#' nas "
                  "linhas de branco e nulo.",
    "tipo_votavel": "Natureza do voto: Nominal, Legenda, Branco ou Nulo. Vem "
                    "de DS_TIPO_VOTAVEL.",
    "nr_votavel": "Numero digitado na urna. Vem de NR_VOTAVEL; 95 identifica "
                  "branco e 96 identifica nulo.",
    "nm_votavel": "Nome do candidato como aparece na urna. Vem de NM_VOTAVEL; "
                  "vale 'Branco' ou 'Nulo' nas linhas correspondentes.",
    "votos": "Votos apurados. Vem de QT_VOTOS. Unidade: voto.",
    "aptos": "Eleitores aptos naquele cargo. Vem de QT_APTOS. Unidade: eleitor.",
    "comparecimento": "Eleitores que compareceram. Vem de QT_COMPARECIMENTO. "
                      "Unidade: eleitor.",
    "abstencoes": "Aptos que nao compareceram. Vem de QT_ABSTENCOES. "
                  "Unidade: eleitor.",
    "secoes_agregadas": "Secoes cujo eleitorado foi somado nesta. '#NULO#' "
                        "quando nao houve agregacao. Vem de "
                        "DS_SECOES_AGREGADAS. O conteudo muda entre turnos, "
                        "por isso a comparacao e feita por local.",
    "dt_abertura": "Instante em que a urna ficou pronta para receber votos, no "
                   "horario LOCAL da urna, nao no de Brasilia. Vem de "
                   "DT_ABERTURA.",
    "dt_encerramento": "Instante do encerramento, tambem no horario local da "
                       "urna. Vem de DT_ENCERRAMENTO.",
    "nr_urna": "Numero de serie da urna que gerou o boletim. Vem de "
               "NR_URNA_EFETIVADA.",
    "biom_sem_habilitacao": "Eleitores da secao sem habilitacao biometrica. "
                            "Vem de QT_ELEI_BIOM_SEM_HABILITACAO. Unidade: "
                            "eleitor.",
    "rotulo": "Identidade do destino do voto: nome do candidato quando "
              "nominal, 'LEGENDA <sigla>' no voto de legenda, ou BRANCO / "
              "NULO. Normalizado em maiusculas.",
    "qt_secoes": "Secoes somadas neste local naquele cargo. Unidade: secao.",
    "secoes_com_agregacao": "Quantas dessas secoes agregam eleitorado de "
                            "outra. Serve para medir o ruido da comparacao "
                            "entre turnos. Unidade: secao.",
    "fracao_aptos": "votos / aptos. Fracao entre 0 e 1, nao percentual.",
    "escopo": "Recorte em que a regressao rodou: 'UF' para a matriz estimada "
              "dentro de um estado, 'BRASIL' para a media das 27 matrizes "
              "estaduais ponderada pelos eleitores de cada origem - esse e o "
              "numero publicado - e 'BRASIL_DIRETO' para uma unica regressao "
              "no pais inteiro, que fica gravada so como contraste: ela supoe "
              "comportamento igual em todo o territorio e por isso crava 0% ou "
              "100% em 27 das 50 celulas, contra 2 na estimativa por UF.",
    "origem": "Rotulo escolhido no 1o turno: candidato, BRANCO, NULO, "
              "ABSTENCAO, ou OUTROS para o conjunto dos candidatos com menos "
              "de 0,2% dos aptos, cuja coluna de regressao e quase constante "
              "entre locais e nao identifica coeficiente proprio.",
    "destino": "Rotulo escolhido no 2o turno, nos mesmos termos de origem.",
    "eleitores_origem": "Eleitores que escolheram a origem no 1o turno, dentro "
                        "do escopo. E o denominador de fracao. Unidade: eleitor.",
    "fracao": "Parcela da origem estimada como tendo ido para o destino. "
              "Fracao entre 0 e 1, nao percentual. Por construcao, as fracoes "
              "de uma mesma origem somam 1.",
    "fracao_min": "Limite inferior da faixa de 95% de fracao, percentil 2,5 de "
                  "150 replicas de bootstrap que reamostram os MUNICIPIOS do "
                  "escopo - nao os locais, que dentro de um municipio se "
                  "parecem e estreitariam a faixa artificialmente.",
    "fracao_max": "Limite superior da faixa de 95% de fracao, percentil 97,5 "
                  "das mesmas replicas.",
    "eleitores": "fracao x eleitores_origem: eleitores estimados nesse fluxo. "
                 "Unidade: eleitor.",
    "eleitores_min": "fracao_min x eleitores_origem. Unidade: eleitor.",
    "eleitores_max": "fracao_max x eleitores_origem. Unidade: eleitor.",
    "locais": "Locais de votacao que sustentaram a regressao do escopo, ja "
              "descontado o local sem par entre os turnos. Unidade: local.",
    "municipios": "Municipios presentes no escopo. Unidade: municipio.",
    # --- registro de coleta (ingestao/comum.py) --------------------------
    "fonte": "Orgao de origem do arquivo: 'tse', 'camara', 'senado' e assim "
             "por diante. Define a pasta em dados/parquet e, no banco, o "
             "schema da fonte.",
    "conjunto": "Conjunto de dados dentro da fonte, no nome que o proprio "
                "portal usa: 'votacoesVotos', 'proposicoes', 'bu_2026'.",
    "arquivo": "Nome do Parquet gravado em dados/parquet/<fonte>/<conjunto>/.",
    "url": "URL exata de onde o arquivo foi baixado, para qualquer pessoa "
           "refazer o caminho ate a fonte oficial.",
    "baixado_em": "Instante do download, no horario local da maquina que "
                  "rodou a ingestao. E a 'data da coleta' que o portal cita "
                  "ao lado de cada numero.",
    "bytes": "Tamanho do arquivo baixado da origem, em bytes, conferido "
             "contra o Content-Length declarado pelo portal - download "
             "incompleto falha em vez de entrar na base.",
    "linhas": "Linhas gravadas no Parquet resultante.",
    "sha256": "Hash do conteudo baixado, para detectar que a origem mudou "
              "entre duas coletas.",
    "observacao": "Vazio quando a carga foi limpa. Quando o CSV de origem "
                  "nao obedece ao padrao, guarda quantas linhas e de que "
                  "tipo foi o defeito, e como o leitor foi relaxado - para o "
                  "caminho diferente nao ficar invisivel depois.",
}

# descricao por schema, para nome que muda de sentido entre fontes: `numero` e
# `codigo` querem dizer coisas diferentes na Camara e no Senado. Tem precedencia
# sobre COMUNS e cede a ESPECIFICAS.
POR_SCHEMA = {
    # ------------------------------- Camara -------------------------------
    ("camara", "id_deputado"):
        "Id do deputado na Camara. Vem do fim da URI do arquivo de origem "
        "(.../deputados/204382), porque o arquivo de deputados nao tem coluna "
        "de id. E a chave que liga voto, autoria, frente e cargo em orgao.",
    ("camara", "id_proposicao"): "Id da proposicao na Camara.",
    ("camara", "id_votacao"):
        "Id da votacao na Camara, no formato '<idProposicao>-<sequencia>' "
        "(exemplo: 257161-367). Nao e numerico, de proposito: o segundo termo "
        "distingue votacoes do mesmo item na mesma sessao.",
    ("camara", "id_orgao"):
        "Id do orgao - comissao, mesa, plenario -, do fim da URI de origem.",
    ("camara", "id_evento"): "Id da sessao ou reuniao em que a votacao ocorreu.",
    ("camara", "id_frente"): "Id da frente parlamentar.",
    ("camara", "id_legislatura"):
        "Numero da legislatura, o periodo de quatro anos do mandato da Camara. "
        "A 57a vai de 2023 a 2027; a 1a comeca em 1826.",
    ("camara", "id_partido"): "Id do partido na Camara.",
    ("camara", "nome"): "Nome de tratamento, como a pessoa e conhecida.",
    ("camara", "nome_deputado"): "Nome do deputado como consta no registro.",
    ("camara", "nome_civil"):
        "Nome civil completo. Esta preenchido em todas as 7.890 linhas e e "
        "hoje a melhor chave disponivel para cruzar com outras bases, porque o "
        "CPF vem vazio.",
    ("camara", "cpf"):
        "VEM VAZIO EM TODAS AS LINHAS. A coluna existe no arquivo da Camara e "
        "nao esta preenchida em nenhuma das 7.890. Mantida para o dia em que "
        "mudar, e para ninguem supor que a ingestao a perdeu.",
    ("camara", "sexo"): "Sexo declarado, 'M' ou 'F'. Vem de siglaSexo.",
    ("camara", "sigla"): "Sigla do objeto: do partido ou do orgao.",
    ("camara", "sigla_orgao"): "Sigla do orgao em que a votacao ocorreu.",
    ("camara", "sigla_partido"):
        "Sigla do partido no momento do registro - do voto, da autoria, do "
        "cargo. Nao e a filiacao atual: o mesmo deputado aparece com siglas "
        "diferentes ao longo do tempo, e e isso que permite acompanhar troca "
        "de partido.",
    ("camara", "sigla_tipo"):
        "Sigla do tipo da proposicao: PL, PEC, MPV, PAR, SBT e outras.",
    ("camara", "tipo"): "Descricao do tipo, por extenso.",
    ("camara", "cod_tipo"): "Codigo numerico do tipo, como a Camara o publica.",
    ("camara", "numero"):
        "Numero da proposicao dentro do tipo e do ano. Com o tipo e o ano, "
        "forma a identificacao publica (PL 1234/2023).",
    ("camara", "ano"):
        "Ano da proposicao. NULL quando ela nao tem ano proprio - parecer, "
        "substitutivo e afins, 39% do total: a Camara grava zero nesses casos "
        "e a carga converte para NULL, porque zero como ano envenena qualquer "
        "agregacao por tempo.",
    ("camara", "titulo"): "Titulo do objeto: da frente, da ocupacao, do cargo.",
    ("camara", "apelido"): "Nome curto pelo qual o orgao e conhecido.",
    ("camara", "descricao"): "Texto descritivo publicado pela Camara.",
    ("camara", "ementa"): "Ementa oficial da proposicao, como registrada.",
    ("camara", "ementa_detalhada"): "Versao longa da ementa, quando existe.",
    ("camara", "palavras_chave"):
        "Palavras-chave atribuidas pela Camara. Texto livre, separadas por "
        "virgula; servem para busca, nao como classificacao fechada.",
    ("camara", "situacao"): "Situacao do objeto no ultimo registro conhecido.",
    ("camara", "tramitacao"): "Descricao do ultimo passo de tramitacao.",
    ("camara", "apreciacao"):
        "Regime de apreciacao: se a proposicao e decidida em plenario ou "
        "conclusivamente nas comissoes.",
    ("camara", "orgao_atual"): "Sigla do orgao onde a proposicao estava.",
    ("camara", "status_em"): "Instante do ultimo registro de status.",
    ("camara", "apresentada_em"): "Instante de apresentacao da proposicao.",
    ("camara", "data"): "Data do registro.",
    ("camara", "registrada_em"): "Instante em que a votacao foi registrada.",
    ("camara", "votado_em"): "Instante do voto do deputado.",
    ("camara", "data_inicio"): "Inicio da vigencia ou do periodo.",
    ("camara", "data_fim"):
        "Fim da vigencia ou do periodo. NULL quando segue em vigor.",
    ("camara", "data_criacao"): "Data de criacao da frente parlamentar.",
    ("camara", "data_instalacao"): "Data em que o orgao foi instalado.",
    ("camara", "data_nascimento"):
        "Data de nascimento. Preenchida em 7.006 das 7.890 linhas; ausente "
        "sobretudo nos deputados mais antigos.",
    ("camara", "data_falecimento"): "Data de falecimento, quando aplicavel.",
    ("camara", "legislatura_inicial"):
        "Primeira legislatura em que a pessoa exerceu mandato na Camara.",
    ("camara", "legislatura_final"):
        "Ultima legislatura em que exerceu mandato.",
    ("camara", "uf"): "Sigla da UF pela qual foi eleito ou registrado.",
    ("camara", "uf_nascimento"): "UF de nascimento.",
    ("camara", "municipio_nascimento"): "Municipio de nascimento.",
    ("camara", "url_site"): "Site pessoal declarado.",
    ("camara", "url_rede_social"): "Rede social declarada.",
    ("camara", "url_inteiro_teor"): "URL do texto integral da proposicao.",
    ("camara", "url_pauta"): "URL do documento de pauta do evento.",
    ("camara", "url_documento"): "URL do documento fiscal da despesa.",
    ("camara", "casa"): "Casa a que o orgao pertence.",
    ("camara", "aprovacao"):
        "1 quando a materia foi aprovada na votacao, 0 quando rejeitada.",
    ("camara", "votos_sim"): "Votos favoraveis declarados. Unidade: voto.",
    ("camara", "votos_nao"): "Votos contrarios declarados. Unidade: voto.",
    ("camara", "votos_outros"):
        "Abstencoes e demais registros que nao sao sim nem nao. Unidade: voto.",
    ("camara", "voto"):
        "Voto do deputado como texto: 'Sim', 'Não', 'Abstenção', "
        "'Obstrução', 'Artigo 17'.",
    ("camara", "proposicao_descricao"):
        "Identificacao da proposicao em texto, como a Camara a exibe.",
    ("camara", "nome_autor"): "Nome do autor como registrado na proposicao.",
    ("camara", "tipo_autor"):
        "Natureza do autor: deputado, orgao, Poder Executivo, cidadao.",
    ("camara", "ordem_assinatura"):
        "Posicao da assinatura na proposicao. 1 e o primeiro signatario.",
    ("camara", "proponente"):
        "1 marca quem propos, distinguindo-o dos coautores que apenas "
        "assinaram.",
    ("camara", "cod_tema"): "Codigo do tema atribuido pela Camara.",
    ("camara", "tema"): "Tema da proposicao, por extenso.",
    ("camara", "relevancia"):
        "Peso do tema na proposicao, atribuido pela Camara.",
    ("camara", "id_coordenador"): "Id do deputado que coordena a frente.",
    ("camara", "nome_coordenador"): "Nome do coordenador da frente.",
    ("camara", "partido_coordenador"): "Partido do coordenador.",
    ("camara", "uf_coordenador"): "UF do coordenador.",
    ("camara", "titulo_participacao"):
        "Papel do deputado na frente: titular, coordenador e afins.",
    ("camara", "nome_orgao"): "Nome do orgao por extenso.",
    ("camara", "cargo"): "Cargo ocupado no orgao: presidente, relator, membro.",
    ("camara", "entidade"): "Entidade em que a ocupacao foi exercida.",
    ("camara", "entidade_uf"): "UF da entidade.",
    ("camara", "entidade_pais"): "Pais da entidade.",
    ("camara", "ano_inicio"): "Ano de inicio da ocupacao.",
    ("camara", "ano_fim"): "Ano de fim da ocupacao.",
    ("camara", "ano_eleicao"): "Ano da eleicao que formou a legislatura.",
    ("camara", "registrado_em"): "Instante do registro da profissao.",
    ("camara", "inicio"): "Inicio do evento.",
    ("camara", "fim"): "Fim do evento.",
    ("camara", "local_externo"): "Local fora da Camara, quando o evento ocorreu fora.",
    ("camara", "local_camara"): "Nome do local dentro da Camara.",
    ("camara", "id_deputado_cota"):
        "Id do deputado no sistema da cota parlamentar, que NAO e o mesmo id "
        "do resto da base - a cota tem numeracao propria. Cruzar por ele com "
        "camara.deputado produz resultado errado.",
    ("camara", "nome_parlamentar"): "Nome do parlamentar na folha da cota.",
    ("camara", "id_cadastro"): "Id de cadastro do parlamentar na cota.",
    ("camara", "legislatura"): "Legislatura a que a despesa se refere.",
    ("camara", "mes"): "Mes de competencia da despesa, de 1 a 12.",
    ("camara", "categoria"):
        "Categoria da despesa na cota: passagem, combustivel, divulgacao, "
        "consultoria e outras.",
    ("camara", "subcategoria"): "Especificacao dentro da categoria.",
    ("camara", "fornecedor"): "Nome do fornecedor do servico ou produto.",
    ("camara", "fornecedor_doc"): "CNPJ ou CPF do fornecedor.",
    ("camara", "emitido_em"): "Data de emissao do documento fiscal.",
    ("camara", "valor_documento"):
        "Valor de face do documento fiscal. Unidade: real corrente da data, "
        "nao corrigido pela inflacao.",
    ("camara", "valor_glosa"):
        "Parte do valor rejeitada na analise. Unidade: real corrente.",
    ("camara", "valor_liquido"):
        "Valor efetivamente ressarcido: documento menos glosa. E este que soma "
        "o gasto de um deputado. Unidade: real corrente.",
    ("camara", "passageiro"): "Nome do passageiro, nas despesas de passagem.",
    ("camara", "trecho"): "Trecho da viagem, nas despesas de passagem.",

    # ------------------------------- Senado -------------------------------
    ("senado", "codigo_parlamentar"):
        "Codigo do senador no Senado. E a chave que liga voto, mandato e "
        "filiacao; nao tem relacao com o id de deputado da Camara.",
    ("senado", "codigo"): "Codigo do objeto no Senado: do partido ou do colegiado.",
    ("senado", "codigo_partido"): "Codigo do partido no Senado.",
    ("senado", "codigo_mandato"): "Codigo do mandato, unico por mandato.",
    ("senado", "codigo_materia"): "Codigo da materia legislativa.",
    ("senado", "codigo_votacao"):
        "Codigo da votacao (codigoSessaoVotacao). E a chave da votacao SOZINHO: "
        "sequencial parece compor a chave mas e nulo na maioria das linhas.",
    ("senado", "codigo_sessao"): "Codigo da sessao plenaria.",
    ("senado", "codigo_tipo"): "Codigo do tipo de colegiado.",
    ("senado", "codigo_titular"):
        "Codigo do senador titular, quando a linha e de suplente.",
    ("senado", "id_processo"): "Id do processo legislativo.",
    ("senado", "id_norma"): "Id da norma juridica.",
    ("senado", "sequencial"):
        "Sequencial da votacao na sessao. NULO em 2.719 das 3.626 votacoes e "
        "em 214 mil dos 287 mil votos - nao serve como parte de chave, porque "
        "NULL nao casa com NULL e a juncao descarta as linhas em silencio.",
    ("senado", "numero"):
        "Numero da legislatura, na tabela legislatura; numero da materia, nas "
        "demais.",
    ("senado", "numero_legislatura"):
        "Numero da legislatura do Senado. Atencao: o mandato de senador dura "
        "oito anos e atravessa DUAS legislaturas, ao contrario do de deputado.",
    ("senado", "numero_materia"): "Numero da materia dentro do tipo e do ano.",
    ("senado", "numero_sessao"): "Numero da sessao plenaria no ano.",
    ("senado", "primeira_legislatura"):
        "Primeira legislatura coberta - do mandato, ou em que o senador "
        "apareceu.",
    ("senado", "segunda_legislatura"):
        "Segunda legislatura do mandato de oito anos.",
    ("senado", "ultima_legislatura"):
        "Ultima legislatura em que o senador aparece na base.",
    ("senado", "legislaturas"):
        "Em quantas legislaturas o senador aparece. Unidade: legislatura.",
    ("senado", "nome"): "Nome parlamentar, como a pessoa e conhecida.",
    ("senado", "nome_completo"): "Nome civil completo.",
    ("senado", "nome_partido"): "Nome do partido por extenso.",
    ("senado", "nome_titular"): "Nome do senador titular da vaga.",
    ("senado", "sigla"): "Sigla do partido ou do colegiado.",
    ("senado", "sigla_partido"):
        "Sigla do partido no momento do registro, nao a filiacao atual.",
    ("senado", "sigla_materia"): "Sigla do tipo da materia: PL, PEC, PDL, MSF.",
    ("senado", "sigla_tipo"): "Sigla do tipo de colegiado.",
    ("senado", "tipo"): "Tipo do objeto, por extenso.",
    ("senado", "tipo_descricao"): "Descricao do tipo de norma.",
    ("senado", "tipo_documento"): "Tipo do documento que originou o processo.",
    ("senado", "tipo_conteudo"): "Natureza do conteudo do processo.",
    ("senado", "tipo_deliberacao"): "Sigla do tipo da ultima deliberacao.",
    ("senado", "tipo_sessao"): "Sigla do tipo de sessao plenaria.",
    ("senado", "tratamento"): "Forma de tratamento: 'Senador' ou 'Senadora'.",
    ("senado", "sexo"): "Sexo declarado, por extenso.",
    ("senado", "uf"): "Sigla da UF representada.",
    ("senado", "casa"): "Casa do registro: SF (Senado) ou CN (Congresso).",
    ("senado", "participacao"):
        "Se o senador ocupa a vaga como Titular ou como Suplente.",
    ("senado", "email"): "Endereco de correio eletronico oficial.",
    ("senado", "url_pagina"): "Pagina oficial do senador.",
    ("senado", "url_foto"): "Foto oficial do senador.",
    ("senado", "url_documento"): "URL do documento do processo.",
    ("senado", "data_inicio"): "Inicio do periodo.",
    ("senado", "data_fim"): "Fim do periodo. NULL quando segue em vigor.",
    ("senado", "data_eleicao"): "Data da eleicao que formou a legislatura.",
    ("senado", "data_criacao"): "Data de criacao do partido.",
    ("senado", "data_extincao"): "Data de extincao do partido, quando houve.",
    ("senado", "data_sessao"): "Data da sessao em que a votacao ocorreu.",
    ("senado", "data_filiacao"): "Data de filiacao ao partido.",
    ("senado", "data_desfiliacao"):
        "Data de desfiliacao. NULL quando a filiacao segue valendo.",
    ("senado", "ano_filiacao"):
        "Ano de filiacao. Preenchido em 546 das 3.312 linhas - a serie com ano "
        "e muito menor que a serie com data.",
    ("senado", "ano_desfiliacao"): "Ano de desfiliacao, quando informado.",
    ("senado", "ano_materia"): "Ano da materia votada.",
    ("senado", "ano_assinatura"): "Ano de assinatura da norma.",
    ("senado", "assinada_em"): "Data de assinatura da norma.",
    ("senado", "apresentado_em"): "Data de apresentacao do processo.",
    ("senado", "situacao_em"): "Data da situacao atual do processo.",
    ("senado", "deliberado_em"): "Data da ultima deliberacao.",
    ("senado", "atualizado_em"): "Instante da ultima atualizacao no portal.",
    ("senado", "materia"):
        "Identificacao da materia em texto, como o Senado a exibe "
        "(exemplo: PDL 995/2026).",
    ("senado", "identificacao"): "Identificacao publica do processo.",
    ("senado", "apelido"): "Nome pelo qual a materia ou norma e conhecida.",
    ("senado", "ementa"): "Ementa oficial.",
    ("senado", "autoria"): "Autoria da materia, em texto livre.",
    ("senado", "objetivo"): "Objetivo declarado do processo.",
    ("senado", "situacao"): "Situacao atual do processo.",
    ("senado", "tramitando"): "Verdadeiro quando o processo segue em tramitacao.",
    ("senado", "norma_gerada"): "Norma que resultou do processo, quando houve.",
    ("senado", "norma"): "Identificacao curta da norma.",
    ("senado", "norma_nome"): "Nome da norma por extenso.",
    ("senado", "letra"): "Letra que acompanha o numero da norma, quando ha.",
    ("senado", "complemento"): "Complemento da identificacao da norma.",
    ("senado", "reedicao"): "Numero da reedicao, nas medidas provisorias.",
    ("senado", "sequencia"): "Sequencia da norma dentro do tipo e ano.",
    ("senado", "descricao"): "Texto descritivo publicado pelo Senado.",
    ("senado", "resultado"): "Resultado da votacao, por extenso.",
    ("senado", "secreta"):
        "'S' quando a votacao foi secreta, 'N' quando aberta. ATENCAO AO QUE "
        "ISSO IMPLICA NOS DADOS: na secreta o total declarado vem preenchido e "
        "cada voto individual aparece como 'Votou', sem revelar; na aberta o "
        "total vem VAZIO e o placar tem de ser contado dos votos nominais.",
    ("senado", "votos_sim"):
        "Total de votos favoraveis declarado. Preenchido SO nas votacoes "
        "secretas. Unidade: voto.",
    ("senado", "votos_nao"):
        "Total de votos contrarios declarado, so nas secretas. Unidade: voto.",
    ("senado", "votos_abstencao"):
        "Total de abstencoes declarado, so nas secretas. Unidade: voto.",
    ("senado", "voto"):
        "Voto do senador: 'Sim', 'Não', 'Abstenção' nas votacoes abertas; "
        "'Votou' nas secretas, em que o sentido do voto nao e publicado; e os "
        "codigos de ausencia (P-NRV, AP, LS, NCom, MIS, LP, REP).",
    ("senado", "voto_descricao"):
        "O codigo de voto por extenso, quando existe - 'Presente – Não "
        "registrou voto', 'Licença saúde' e os demais motivos de ausencia.",
    ("senado", "colegiado"): "Sigla do colegiado em que a votacao ocorreu.",
    ("senado", "publica"): "Marca se o colegiado tem atividade publica.",
    ("senado", "finalidade"): "Finalidade declarada do colegiado.",
    ("senado", "ente"): "Ente que identificou o processo.",
    ("senado", "mandatos_json"):
        "Mandatos do senador como vieram da API, em JSON de texto. A ingestao "
        "serializa a sublista em vez de descartar; a tabela mandato traz o "
        "mesmo conteudo em linhas.",
    ("senado", "sessoes_json"):
        "Sessoes legislativas da legislatura, em JSON de texto.",
    ("senado", "suplentes_json"):
        "Suplentes do mandato, em JSON de texto.",
    ("senado", "exercicios_json"):
        "Periodos de exercicio efetivo do mandato, em JSON de texto - e por "
        "aqui que se ve afastamento e reassuncao.",
}

# sobrescreve quando o sentido muda na tabela
ESPECIFICAS = {
    ("fluxo_insumo", "rotulo"):
        "Mesmos rotulos de votos_local, mais ABSTENCAO, que entra como destino "
        "para o fluxo fechar em 100% dos aptos.",
    ("fluxo_insumo", "votos"):
        "Votos do rotulo, ou eleitores que se abstiveram quando o rotulo e "
        "ABSTENCAO. Unidade: voto, exceto nessa linha, em que e eleitor.",
    ("fluxo_insumo", "aptos"):
        "Aptos do local naquele cargo e turno, usado como denominador de "
        "fracao_aptos. Unidade: eleitor.",
    ("fluxo_estimado", "uf"):
        "Sigla da UF quando escopo = 'UF'; NULL nos escopos nacionais. O "
        "exterior ('ZZ') nao entra: sao poucos locais para a regressao.",
    ("fluxo_estimado", "cargo"):
        "'Presidente' tem matriz por UF e matriz nacional. 'Governador' so tem "
        "matriz por UF, e apenas nas 6 que tiveram 2o turno (AC, AM, DF, ES, "
        "RN, TO): cada estado disputou entre candidatos proprios, e uma matriz "
        "nacional misturaria nomes que nunca estiveram na mesma urna.",
    ("fluxo_estimado", "fracao_min"):
        "Limite inferior da faixa de 95% de fracao, percentil 2,5 de 150 "
        "replicas de bootstrap que reamostram os MUNICIPIOS do escopo - nao os "
        "locais, que dentro de um municipio se parecem e estreitariam a faixa "
        "artificialmente. No DF, onde o municipio e unico, a reamostragem "
        "desce para a zona eleitoral.",
}


def lit(texto):
    """COMMENT ON nao aceita parametro vinculado; a string vai literal."""
    return "'" + texto.replace("'", "''") + "'"


con = duckdb.connect(BANCO)

# o catalogo cobre todos os schemas de fonte - cada fonte vive no seu (tse,
# camara, senado...) - mais main, que guarda o que atravessa fontes.
#
# main entra por nome, nao pelo filtro: o DuckDB marca o schema main como
# internal = true, e um `WHERE NOT internal` ingenuo deixa de fora justamente a
# tabela coleta, que e o registro de procedencia do projeto. Ela ficou invisivel
# no dicionario por uma versao inteira por causa disso.
SCHEMAS = sorted({"main"} | {s[0] for s in con.execute("""
    SELECT schema_name FROM duckdb_schemas()
    WHERE NOT internal AND database_name = 'politica_br'
""").fetchall()})

# par (schema, tabela), nao dicionario por nome: camara.votacao e
# senado.votacao tem o mesmo nome e um dicionario por nome perderia uma delas
EXISTENTES = {(s, t) for s, t in con.execute("""
    SELECT schema_name, table_name FROM duckdb_tables()
    UNION ALL SELECT schema_name, view_name FROM duckdb_views()
    WHERE NOT internal
""").fetchall()}

# TABELAS e por nome porque cobre main e tse, onde nao ha repeticao
for schema, tabela in sorted(EXISTENTES):
    desc = TABELAS_POR_SCHEMA.get((schema, tabela)) or TABELAS.get(tabela)
    if not desc:
        continue
    alvo = "VIEW" if tabela == "bu" else "TABLE"
    con.execute(f"COMMENT ON {alvo} {schema}.{tabela} IS {lit(desc)}")

sem_desc_tabela = [
    f"{s}.{t}" for s, t in sorted(EXISTENTES)
    if s in CURADOS and (s, t) not in TABELAS_POR_SCHEMA and t not in TABELAS]

colunas = con.execute(f"""
    SELECT schema_name, table_name, column_name FROM duckdb_columns()
    WHERE schema_name IN ({','.join("'" + s + "'" for s in SCHEMAS)})
      AND NOT internal
    ORDER BY schema_name, table_name, column_index
""").fetchall()

sem_descricao = []
for schema, tabela, coluna in colunas:
    # a ordem e do mais especifico ao mais geral: a tabela sobrepoe o schema,
    # que sobrepoe o nome solto
    desc = (ESPECIFICAS.get((tabela, coluna))
            or POR_SCHEMA.get((schema, coluna))
            or COMUNS.get(coluna))
    if desc is None:
        sem_descricao.append(f"{schema}.{tabela}.{coluna}")
        continue
    con.execute(f'COMMENT ON COLUMN {schema}.{tabela}."{coluna}" IS {lit(desc)}')

# --- regera o dicionario a partir do catalogo -------------------------------
objetos = con.execute("""
SELECT schema_name, table_name, comment, 'tabela' AS tipo FROM duckdb_tables()
UNION ALL
SELECT schema_name, view_name, comment, 'view' FROM duckdb_views()
WHERE NOT internal
ORDER BY 1, 4 DESC, 2
""").fetchall()

linhas = ["# Dicionário de dados", "",
          "Gerado por `transformacao/documenta_banco.py` a partir do "
          "catálogo do banco.",
          "Não editar à mão: a descrição vive no banco.", "",
          "Uma fonte por schema; `main` guarda o que atravessa fontes.", ""]

schema_atual = None
for schema, nome, comentario, tipo in objetos:
    if schema != schema_atual:
        linhas += [f"# Schema `{schema}`", ""]
        schema_atual = schema
    cols = con.execute("""
        SELECT column_name, data_type, comment FROM duckdb_columns()
        WHERE table_name = ? AND schema_name = ?
        ORDER BY column_index
    """, [nome, schema]).fetchall()
    n = con.execute(f'SELECT COUNT(*) FROM {schema}."{nome}"').fetchall()[0][0]
    linhas += [f"## `{schema}.{nome}` ({tipo})", "",
               comentario or "_sem descrição_", "",
               f"Linhas: {n:,}".replace(",", "."), "",
               "| Coluna | Tipo | Descrição |", "| --- | --- | --- |"]
    for c, t, cd in cols:
        linhas.append(f"| `{c}` | {t} | {cd or ''} |")
    linhas.append("")

with open(DOC, "w", encoding="utf-8") as fh:
    fh.write("\n".join(linhas))

con.close()

# --- relatorio de cobertura, por schema ------------------------------------
por_schema = {}
for schema, tabela, coluna in colunas:
    d = por_schema.setdefault(schema, [0, 0])
    d[0] += 1
faltando = {}
for item in sem_descricao:
    schema = item.split(".", 1)[0]
    faltando.setdefault(schema, []).append(item)

print(f"\n{DOC} regerado")
print(f"{'schema':<10}{'colunas':>9}{'documentadas':>14}{'cobertura':>11}")
for schema in sorted(por_schema):
    total = por_schema[schema][0]
    falta = len(faltando.get(schema, []))
    marca = "  (curado)" if schema in CURADOS else ""
    print(f"{schema:<10}{total:>9}{total - falta:>14}"
          f"{100 * (total - falta) / total:>10.0f}%{marca}")

if sem_desc_tabela:
    print(f"\nFALTA descricao de tabela: {', '.join(sem_desc_tabela)}")

falha = {s: v for s, v in faltando.items() if s in CURADOS}
if falha:
    for schema, itens in falha.items():
        print(f"\nFALTA descricao de coluna em {schema}: "
              + ", ".join(itens[:25])
              + (" ..." if len(itens) > 25 else ""))
if falha or sem_desc_tabela:
    sys.exit(1)
