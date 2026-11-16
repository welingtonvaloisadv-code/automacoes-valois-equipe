"""
Regra de tratamento automatico de publicacoes - Welington Valois Advogados Associados.

Define COMO O ESCRITORIO TRATA cada publicacao: que tarefa nasce no ADVBOX, para quem,
se a IA minuta peca e se o suporte avisa o cliente. Base: POP 09 (controladoria de prazos)
e o historico de tarefas do ADVBOX (tipos de tarefa realmente usados pela equipe).

Para mudar o tratamento de um tipo de publicacao, edite TRATAMENTOS aqui - o pipeline
(OPERACIONAL/tratamento_publicacoes.py) so le esta tabela.

IDs de usuario: ADVBOX > Usuarios (conferidos em 06/11/2026 via GET /settings).
"""

# ------------------------------------------------------------------
# Pessoas (ADVBOX user id)
# ------------------------------------------------------------------
USUARIOS = {
    'WELINGTON': 201250, 'PRISCILA': 201269, 'DERLIRA': 201357, 'GISELE': 243231,
    'HELIEZER': 201390, 'GUILHERME': 301180, 'KESIA': 243062, 'KAUA': 201353,
    'MARIANA': 201646, 'MARESSA': 270322, 'EDMUNDO': 281411, 'JOAO PEDRO': 257524,
}

NOMES = {
    'WELINGTON': 'Dr. Welington Dias Valois', 'PRISCILA': 'Dra. Priscila Araujo de Matos',
    'DERLIRA': 'Dra. Derlira Garcia Pimentel Soares', 'GISELE': 'Dra. Gisele Teófilo de Avila',
    'HELIEZER': 'Dr. Heliézer de Medeiros Pontes', 'GUILHERME': 'Dr. Guilherme Mota Lopes Costa',
    'KESIA': 'Kesia Reder', 'KAUA': 'Kauã Moreira Valois', 'MARIANA': 'Mariana Oliveira',
    'MARESSA': 'Maressa Teodoro', 'EDMUNDO': 'Edmundo Oliveira', 'JOAO PEDRO': 'João Pedro',
}

OAB = {
    'WELINGTON': 'OAB/ES 34.912', 'PRISCILA': 'OAB/ES 39.600', 'DERLIRA': 'OAB/ES 27.296',
    'GISELE': 'OAB/ES 23.868', 'HELIEZER': 'OAB/ES 38.904', 'GUILHERME': 'OAB/ES 44.599',
}

# Area -> advogado que faz/revisa a peca, controller do prazo (POP 09 item 2), suporte que fala
# com o cliente. Inventario/sucessoes: controller Kaua (POP 09); familia: Gisele.
AREAS = {
    'PREVIDENCIARIO':      {'advogado': 'PRISCILA',  'controller': 'MARESSA', 'suporte': 'EDMUNDO'},
    'CRIMINAL':            {'advogado': 'GUILHERME', 'controller': 'KAUA',    'suporte': 'KESIA'},
    'FAMILIA E SUCESSOES': {'advogado': 'DERLIRA',   'controller': 'GISELE',  'suporte': 'KESIA'},
    'BANCARIO':            {'advogado': 'HELIEZER',  'controller': 'GISELE',  'suporte': 'KESIA'},
    'CIVEL E CONSUMIDOR':  {'advogado': 'GISELE',    'controller': 'GISELE',  'suporte': 'KESIA'},
}
CONTROLLER_SUCESSOES = 'KAUA'   # inventario, arrolamento, partilha, regularizacao de imovel

# Agente juridico do repositorio usado como "manual" da area na minuta.
AGENTE_DA_AREA = {
    'PREVIDENCIARIO': 'valois-previdenciario', 'CRIMINAL': 'valois-criminal',
    'FAMILIA E SUCESSOES': 'valois-familia-sucessoes', 'BANCARIO': 'valois-bancario',
    'CIVEL E CONSUMIDOR': 'valois-civel-consumidor',
}

# ------------------------------------------------------------------
# Catalogo de tratamentos
#   tarefa  = tipo de tarefa do ADVBOX (nome exato em settings['tasks'])
#   peca    = tipo de peca que a IA minuta (None = so tarefa, sem minuta)
#   suporte = tarefa extra para o suporte avisar/pedir algo ao cliente (None = nao)
#   para    = 'advogado' (advogado + controller) | 'controller' (so o controller)
#   urgente = prazo interno no mesmo dia e tarefa urgente (POP 09 item 4.2)
# ------------------------------------------------------------------
TRATAMENTOS = {
    'ciencia_favoravel': dict(
        quando='decisao/sentenca/acordao favoravel ao cliente, sem nada a recorrer; so ciencia e acompanhar transito',
        tarefa='CIENTE SENTENÇA, AUD. E OUTROS.', peca=None, para='controller',
        suporte='INFORMAR O CLIENTE DA DECISÃO'),
    'acompanhar': dict(
        quando='despacho de mero expediente, ato ordinatorio ou intimacao sem providencia nossa',
        tarefa='ACOMPANHAR DECISÃO/DESPACHO', peca=None, para='controller', suporte=None),
    'embargos_declaracao': dict(
        quando='decisao com omissao, contradicao, obscuridade ou erro material que prejudica o cliente',
        tarefa='EMBARGOS DE DECLARAÇÃO', peca='EMBARGOS DE DECLARAÇÃO', para='advogado', suporte=None),
    'apelacao': dict(
        quando='sentenca desfavoravel ou parcialmente desfavoravel (apelacao; no JEC/JEF, recurso inominado)',
        tarefa='RECURSO DE APELAÇÃO/INOMINADO', peca='RECURSO DE APELAÇÃO / RECURSO INOMINADO',
        para='advogado', suporte='INFORMAR O CLIENTE DA DECISÃO'),
    'contrarrazoes': dict(
        quando='intimacao para contrarrazoes ao recurso da parte contraria (ex.: apelacao do INSS)',
        tarefa='ELABORAR CONTRARRAZÕES', peca='CONTRARRAZÕES', para='advogado', suporte=None),
    'agravo_instrumento': dict(
        quando='decisao interlocutoria desfavoravel agravavel (art. 1.015 CPC) ou tutela negada',
        tarefa='AGRAVO DE INSTRUMENTO', peca='AGRAVO DE INSTRUMENTO', para='advogado', suporte=None),
    'replica': dict(
        quando='intimacao para replica/impugnacao a contestacao',
        tarefa='RÉPLICA/IMPUGNAÇÃO À CONTESTAÇÃO', peca='RÉPLICA / IMPUGNAÇÃO À CONTESTAÇÃO',
        para='advogado', suporte=None),
    'manifestacao_laudo': dict(
        quando='intimacao para manifestar sobre laudo pericial, estudo social ou calculo',
        tarefa='MANIFESTAÇÃO COMPLEXA', peca='MANIFESTAÇÃO SOBRE LAUDO / ESTUDO SOCIAL',
        para='advogado', suporte=None),
    'manifestacao_simples': dict(
        quando='manifestacao curta: especificar provas, ciencia com requerimento, juntada, endereco, rol de testemunhas',
        tarefa='MANIFESTAÇÃO SIMPLES', peca='MANIFESTAÇÃO', para='advogado', suporte=None),
    'manifestacao_complexa': dict(
        quando='manifestacao de merito, impugnacao, resposta a documento novo ou questao relevante',
        tarefa='MANIFESTAÇÃO COMPLEXA', peca='MANIFESTAÇÃO', para='advogado', suporte=None),
    'emenda_inicial': dict(
        quando='determinacao de emenda da inicial ou juntada de documento sob pena de indeferimento',
        tarefa='EMENDA À INICIAL', peca='EMENDA À INICIAL', para='advogado',
        suporte='SOLICITAR DOCUMENTOS'),
    'quesitos': dict(
        quando='pericia designada com prazo para quesitos e assistente tecnico',
        tarefa='ELABORAR QUESITOS', peca='QUESITOS E INDICAÇÃO DE ASSISTENTE TÉCNICO',
        para='advogado', suporte='AVISAR CLIENTE DA PERÍCIA'),
    'pericia_designada': dict(
        quando='pericia ja designada (data/local), quesitos ja apresentados ou sem prazo de quesitos',
        tarefa='ACOMPANHAR PERÍCIA', peca=None, para='controller', suporte='AVISAR CLIENTE DA PERÍCIA'),
    'audiencia_designada': dict(
        quando='audiencia designada (conciliacao, instrucao, justificacao, custodia)',
        tarefa='AUDIÊNCIA DE INSTRUÇÃO/JULGAMENTO', peca=None, para='advogado',
        suporte='AVISAR CLIENTE DA AUDIÊNCIA'),
    'cumprimento_sentenca': dict(
        quando='transito em julgado favoravel / intimacao para iniciar cumprimento ou apresentar calculos',
        tarefa='ELABORAR PETIÇÃO DE CUMPRIMENTO DE SENTENÇA', peca='CUMPRIMENTO DE SENTENÇA',
        para='advogado', suporte='INFORMAR O CLIENTE DA DECISÃO'),
    'conferir_calculo': dict(
        quando='calculo do INSS/contadoria/parte contraria para conferir',
        tarefa='CONFERIR CÁLCULO DO PERITO/DA PARTE', peca=None, para='advogado', suporte=None),
    'implantacao_beneficio': dict(
        quando='ordem de implantacao do beneficio pelo INSS / tutela concedida para implantar',
        tarefa='INTIMAÇÃO INSS PARA IMPLANTAR BENEFÍCIO', peca=None, para='controller',
        suporte='INFORMAR O CLIENTE DA DECISÃO'),
    'levantamento_valores': dict(
        quando='RPV/precatorio/alvara expedido ou valor liberado',
        tarefa='LEVANTAMENTO DE RPV', peca=None, para='controller', suporte='INFORMAR O CLIENTE DA DECISÃO'),
    'resposta_acusacao': dict(
        quando='citacao/intimacao do reu para resposta a acusacao (art. 396 CPP)',
        tarefa='RESPOSTA À ACUSAÇÃO', peca='RESPOSTA À ACUSAÇÃO', para='advogado', suporte=None),
    'alegacoes_finais': dict(
        quando='intimacao para alegacoes finais/memoriais',
        tarefa='ALEGAÇÕES FINAIS COMPLEXAS', peca='ALEGAÇÕES FINAIS / MEMORIAIS', para='advogado', suporte=None),
    'revogacao_prisao': dict(
        quando='reu preso: preventiva decretada/mantida, flagrante, pedido de liberdade cabivel',
        tarefa='PEDIDO DE REVOGAÇÃO DA PRISÃO', peca='PEDIDO DE REVOGAÇÃO DA PRISÃO PREVENTIVA',
        para='advogado', suporte=None, urgente=True),
    'habeas_corpus': dict(
        quando='constrangimento ilegal que exige habeas corpus (com ou sem liminar)',
        tarefa='HABEAS CORPUS', peca='HABEAS CORPUS', para='advogado', suporte=None, urgente=True),
    'recurso_tribunal_superior': dict(
        quando='acordao desfavoravel: avaliar REsp/RE/agravo interno (so analise de cabimento, sem minuta)',
        tarefa='ACOMPANHAR DECISÃO/ACÓRDÃO', peca=None, para='advogado', suporte='INFORMAR O CLIENTE DA DECISÃO'),
    'sem_providencia': dict(
        quando='publicacao que nao exige nada do escritorio (escritorio nao atua, homonimo, ja cumprida)',
        tarefa=None, peca=None, para=None, suporte=None),
}

# POP 09 item 4: prazo interno = 3 dias uteis antes do fatal.
DIAS_UTEIS_PRAZO_INTERNO = 3
# Tarefa de suporte vence em ate 2 dias uteis (aviso ao cliente).
DIAS_UTEIS_SUPORTE = 2
# Publicacoes capturadas antes deste dia nao sao tratadas automaticamente (so aparecem no painel).
# Vazio = data da primeira execucao (gravada no estado).
MARCO_INICIAL = ''
