"""
Regras financeiras configuraveis - Welington Valois Advogados Associados.

Este modulo concentra TODAS as regras de negocio financeiras que variam de
escritorio para escritorio. O codigo das automacoes (fechamento, conciliacao,
classificacao de extrato) le APENAS deste arquivo - nada de regra hardcoded.

>>> TODO (onboarding): o escritorio deve cadastrar aqui as proprias regras de
>>> comissao e exececoes. Os valores abaixo vem VAZIOS de proposito. Enquanto
>>> nao forem preenchidos, nenhuma comissao e calculada e nenhuma excecao se
>>> aplica - o pipeline roda de forma neutra/segura.

------------------------------------------------------------------------------
COMISSOES (estrutura, vazia por padrao)
------------------------------------------------------------------------------
Cada comissionado e identificado por uma CHAVE (codigo curto, ex.: 'COMISS_1')
que tambem e usada como SUFIXO opcional na descricao da cobranca no Asaas
(ex.: "Cobranca recebida ... CLIENTE _COMISS_1"). Estrutura de cada entrada:

    "COMISS_1": {
        "rotulo": "Nome do comissionado",      # como aparece nos relatorios
        "sufixos": ["_C1"],                      # sufixos na descricao Asaas -> esta comissao
        "percentual": 0.10,                       # fracao do faturamento (ex.: 0.10 = 10%)
        "advbox_customers_id": None,              # ID no ADVBOX p/ lancar a comissao
        "exclusoes": [],                          # clientes que NAO geram comissao p/ este
        "lista_fechada": [],                      # se preenchida, SO estes clientes geram comissao
    }

Exemplo (NAO ativo - apenas ilustrativo, deixe vazio ate o onboarding):

    COMISSOES = {
        "COMISS_1": {"rotulo": "Comissionado A", "sufixos": ["_A"],
                     "percentual": 0.10, "advbox_customers_id": None,
                     "exclusoes": [], "lista_fechada": []},
    }
"""

# Tabela de comissoes do escritorio. VAZIA por padrao (cadastrar no onboarding).
COMISSOES = {}

# Honorarios padrao por area, usados para preencher o contrato na contratacao (INTAKE).
# VAZIO por padrao: o contrato sai com [PREENCHER] e o advogado completa na revisao.
# Chaves aceitas por area (todas texto, como devem aparecer no contrato):
#   'honorarios_valor'      ex.: "3 (tres) parcelas mensais de R$ 1.518,00"
#   'honorarios_pagamento'  ex.: "a primeira em ate 30 dias da implantacao do beneficio"
# Ex.: HONORARIOS_PADRAO = {"PREVIDENCIARIO": {"honorarios_valor": "...", "honorarios_pagamento": "..."}}
# TODO (onboarding): o escritorio define os valores de cada area.
HONORARIOS_PADRAO = {}

# Banco/centro de custo/categoria usados ao lancar comissoes no ADVBOX.
# Preencher no onboarding com os IDs do escritorio (None = nao lancar).
ADVBOX_FINANCEIRO = {
    "banco_principal": None,     # debit_account
    "centro_custo": None,        # cost_centers_id
    "categoria_comissao": None,  # categories_id
}

# Clientes que NAO contam como receita do escritorio (excluir do faturamento).
# VAZIA por padrao - o escritorio adiciona aqui os casos dele, se houver.
# TODO (onboarding): cadastrar nomes (MAIUSCULO) a excluir do faturamento.
EXCLUIR_FATURAMENTO = []

# Percentual de provisao/destino sobre o lucro liquido (ex.: reserva, doacao).
# 0 = desativado. O escritorio define se/quanto usar.
# TODO (onboarding): definir, se aplicavel.
PERCENTUAL_PROVISAO_LUCRO = 0.0
ROTULO_PROVISAO_LUCRO = "Provisao s/ lucro"

# Categorias do ADVBOX consideradas "distribuicao de lucros" (nao sao despesa
# operacional). Mantido configuravel - palavras-chave em MAIUSCULO.
# TODO (onboarding): ajustar conforme o plano de contas do escritorio.
CATEGORIAS_DISTRIBUICAO = ["DISTRIBUI"]

# Palavras-chave para agrupar despesas no relatorio de resultado (configuravel).
PALAVRAS_COMISSOES = ["PARCEIRO", "ASSOCIADO"]
PALAVRAS_TAXAS = ["TAXAS", "INSS", "SIMPLES", "IMPOSTOS"]
PALAVRAS_SAZONAIS = ["MARKETING", "BRANDING", "CURSOS", "PASSAGEN",
                     "HOSPEDAGEM", "SEGURO DE RESP", "EQUIPAMENTO", "DESPESAS COM"]

# -----------------------------------------------------------------------------
# REMUNERACAO DA EQUIPE (regra geral do escritorio, informada em 01/10/2026)
# -----------------------------------------------------------------------------
# O que cada colaborador recebe = SALARIO_BASE_COLABORADOR
#                               + participacao da area (so o responsavel da area)
# Esta regra vale para TODO lancamento de pagamento a equipe.

SALARIO_BASE_COLABORADOR = 2000.00

# Percentual por area. Chaves iguais as de config/equipe.ADVOGADOS_POR_AREA.
# Area ausente deste dicionario = nenhuma participacao e paga sobre ela.
PARTICIPACAO_POR_AREA = {
    "PREVIDENCIARIO": 0.15,
    "FAMILIA E SUCESSOES": 0.10,
    "CIVEL E CONSUMIDOR": 0.10,
    "CRIMINAL": 0.00,          # nao incide, por decisao do escritorio
}

# Base de calculo da participacao: "LUCRO" (receita - despesas) ou "RECEITA".
BASE_PARTICIPACAO = "LUCRO"

# Quem recebe a participacao da area: "RESPONSAVEL_AREA" (o primeiro de
# ADVOGADOS_POR_AREA) ou "RATEIO" (dividida entre os colaboradores da area).
PARTICIPACAO_DESTINO = "RESPONSAVEL_AREA"

# Areas que geram receita mas para as quais o escritorio NAO definiu percentual.
# Enquanto estiverem aqui, o calculo avisa em vez de assumir zero em silencio.
# TODO: o escritorio deve definir o percentual (ou confirmar que e zero).
AREAS_SEM_PERCENTUAL_DEFINIDO = ["TRABALHISTA", "CONSULTORIA"]

# Palavras-chave da categoria ADVBOX -> area. A primeira que casar vence, por
# isso CIVEL E CONSUMIDOR vem antes de termos mais genericos.
CATEGORIA_RECEITA_PARA_AREA = [
    ("PREVIDENC", "PREVIDENCIARIO"),
    ("CRIMINAL", "CRIMINAL"),
    ("SUCESS", "FAMILIA E SUCESSOES"),
    ("FAMILIA", "FAMILIA E SUCESSOES"),
    ("FAMÍLIA", "FAMILIA E SUCESSOES"),
    ("CONSUMIDOR", "CIVEL E CONSUMIDOR"),
    ("CIVEL", "CIVEL E CONSUMIDOR"),
    ("CÍVEL", "CIVEL E CONSUMIDOR"),
    ("BANCARIO", "BANCARIO"),
    ("BANCÁRIO", "BANCARIO"),
    ("TRABALH", "TRABALHISTA"),
    ("CONSULTORIA", "CONSULTORIA"),
]

# Categorias de entrada que NAO sao receita do escritorio (nao entram na base).
CATEGORIAS_NAO_RECEITA = ["REEMBOLSO"]


def classificar_comissao(descricao):
    """
    Classifica a cobranca em uma chave de comissao com base nos sufixos
    cadastrados em COMISSOES. Retorna a CHAVE da comissao ou None (escritorio).

    Como COMISSOES vem vazia por padrao, esta funcao retorna None ate o
    onboarding cadastrar as regras.
    """
    desc = str(descricao)
    parte = desc.split('fatura nr.')[-1] if 'fatura nr.' in desc else desc
    for chave, regra in COMISSOES.items():
        for suf in regra.get("sufixos", []):
            if suf and suf in parte:
                return chave
    return None


def comissionado_recebe(chave, nome_cliente):
    """
    Indica se o comissionado 'chave' deve receber comissao deste cliente,
    respeitando 'exclusoes' e 'lista_fechada' cadastradas no onboarding.
    """
    regra = COMISSOES.get(chave)
    if not regra:
        return False
    nome = (nome_cliente or "").upper()
    if any(ex.upper() in nome for ex in regra.get("exclusoes", [])):
        return False
    fechada = regra.get("lista_fechada") or []
    if fechada:
        return any(item.upper() in nome or nome in item.upper() for item in fechada)
    return True


def eh_distribuicao(categoria):
    """True se a categoria ADVBOX representa distribuicao de lucros."""
    cat = (categoria or "").upper()
    return any(p in cat for p in CATEGORIAS_DISTRIBUICAO)


def excluir_do_faturamento(nome):
    """True se o cliente nao deve contar como receita do escritorio."""
    n = (nome or "").upper()
    return any(ex.upper() in n for ex in EXCLUIR_FATURAMENTO)


# -----------------------------------------------------------------------------
# Remuneracao da equipe
# -----------------------------------------------------------------------------

def eh_receita_do_escritorio(categoria):
    """False para entradas que nao sao receita (reembolso de custo, p.ex.)."""
    cat = (categoria or "").upper()
    return not any(p in cat for p in CATEGORIAS_NAO_RECEITA)


def area_da_categoria(categoria):
    """Area de atuacao a partir da categoria de receita do ADVBOX.

    As categorias do escritorio ja trazem a area no nome ('PREVIDENCIARIO -
    HONORARIOS POR MENSALIDADE', 'FAMILIA E SUCESSOES', 'CONSUMIDOR - CIVEL').
    Retorna a chave da area ou None se nao der para identificar.
    """
    cat = (categoria or "").upper()
    for chave, area in CATEGORIA_RECEITA_PARA_AREA:
        if chave in cat:
            return area
    return None


def receita_por_area(transacoes):
    """Soma a receita recebida por area.

    transacoes: lista de transacoes do ADVBOX ja filtradas pelo mes desejado
    (usar date_payment - o que entrou de fato, nao o previsto).

    Retorna (receita_por_area, nao_identificadas), onde o segundo item lista as
    categorias que nao casaram com nenhuma area, para conferencia humana.
    """
    por_area = {}
    nao_identificadas = []
    for t in transacoes:
        if t.get("entry_type") != "income":
            continue
        cat = t.get("category")
        if not eh_receita_do_escritorio(cat):
            continue
        area = area_da_categoria(cat)
        if area is None:
            nao_identificadas.append(cat)
            continue
        por_area[area] = por_area.get(area, 0.0) + (t.get("amount") or 0.0)
    return por_area, sorted(set(nao_identificadas))


def margem_do_escritorio(total_receita, total_despesa):
    """Margem global usada para estimar o lucro de cada area.

    O ADVBOX lanca toda despesa em centro de custo GERAL, sem alocacao por area,
    entao o lucro por area e estimado aplicando a margem global sobre a receita
    da area. Com BASE_PARTICIPACAO = 'RECEITA' a margem e 1.0 (nao se desconta
    despesa alguma).
    """
    if BASE_PARTICIPACAO == "RECEITA":
        return 1.0
    if not total_receita:
        return 0.0
    return (total_receita - total_despesa) / total_receita


def participacoes_por_area(por_area, margem):
    """Valor da participacao devida em cada area.

    Retorna (participacoes, areas_sem_regra). O segundo item traz as areas que
    geraram receita mas nao tem percentual definido - elas NAO viram zero em
    silencio, precisam de decisao do escritorio.
    """
    participacoes = {}
    areas_sem_regra = []
    for area, receita in por_area.items():
        if area in PARTICIPACAO_POR_AREA:
            pct = PARTICIPACAO_POR_AREA[area]
            participacoes[area] = round(receita * margem * pct, 2)
        elif receita:
            areas_sem_regra.append((area, round(receita, 2)))
    return participacoes, sorted(areas_sem_regra)


def folha_por_pessoa(colaboradores, participacoes):
    """Quanto cada colaborador recebe = salario base + participacao da area.

    colaboradores: lista de dicts {'nome', 'area', 'responsavel': bool}. So quem
    tem responsavel=True recebe a participacao da sua area (regra atual,
    PARTICIPACAO_DESTINO = 'RESPONSAVEL_AREA'); com 'RATEIO' a participacao da
    area e dividida entre todos os colaboradores dela.

    Os valores sao REMUNERACAO BRUTA - INSS e FGTS sao lancados a parte.
    """
    if PARTICIPACAO_DESTINO == "RATEIO":
        por_area_qtd = {}
        for c in colaboradores:
            if c.get("area"):
                por_area_qtd[c["area"]] = por_area_qtd.get(c["area"], 0) + 1

    linhas = []
    for c in colaboradores:
        area = c.get("area")
        if PARTICIPACAO_DESTINO == "RATEIO":
            qtd = por_area_qtd.get(area, 0)
            parte = round(participacoes.get(area, 0.0) / qtd, 2) if qtd else 0.0
        else:
            parte = participacoes.get(area, 0.0) if c.get("responsavel") else 0.0
        linhas.append({
            "nome": c["nome"],
            "area": area,
            "responsavel": bool(c.get("responsavel")),
            "salario_base": SALARIO_BASE_COLABORADOR,
            "participacao": parte,
            "total": round(SALARIO_BASE_COLABORADOR + parte, 2),
        })
    return linhas
