"""
Equipe / usuarios do escritorio - Welington Valois Advogados Associados.

Centraliza os IDs de usuario do ADVBOX e os papeis funcionais.
NUNCA hardcode IDs no codigo das automacoes: leia sempre deste arquivo.

TODO (onboarding): o escritorio usa ADVBOX (so lancamento de atividades, sem kanban),
mas ainda nao se confirmou se o plano tem API liberada. Enquanto os IDs estiverem None,
as automacoes que dependem deles ficam inativas/seguras.
"""
import os

# IDs de usuario no ADVBOX (painel ADVBOX > Usuarios). Podem vir do .env (recomendado).
USUARIOS_ADVBOX = {
    "RESPONSAVEL": os.getenv("ADVBOX_USER_RESPONSAVEL") or None,   # Dr. Welington Dias Valois (gestor principal)
    "OPERACIONAL": os.getenv("ADVBOX_USER_OPERACIONAL") or None,   # quem recebe tarefas operacionais
    "FINANCEIRO": os.getenv("ADVBOX_USER_FINANCEIRO") or None,     # quem lanca transacoes financeiras (secretaria)
}

# Papeis funcionais do escritorio (informados no briefing de 16/09/2026).
# Servem de referencia para roteamento de tarefas por area; IDs ADVBOX vem do .env.
EQUIPE = {
    "GESTOR_PRINCIPAL": "Welington Dias Valois (OAB/ES 34.912)",
    "GESTOR_IUNA": "Kauã Moreira Valois",
    "GESTORA_IBATIBA": "Gisele Teófilo de Avila (OAB/ES 23.868)",
    "GESTORA_PREVIDENCIARIO": "Priscila Araujo de Matos (OAB/ES 39.600)",
    "AREAS": {
        "PREVIDENCIARIO": "Priscila Araujo de Matos",
        "FAMILIA_SUCESSOES": "Derlira Garcia Pimentel Soares (OAB/ES 27.296)",
        "BANCARIO": "Heliézer de Medeiros Pontes (OAB/ES 38.904)",
        "CIVEL_CONSUMIDOR": "Gisele Teófilo de Avila (OAB/ES 23.868)",
        "CRIMINAL": "Welington Dias Valois e Guilherme Mota Lopes Costa (OAB/ES 44.599)",
    },
    "SECRETARIA": "Kesia Reder (agenda, WhatsApp e financeiro)",
}

# Advogados (briefing de 16/09/2026). Usado pela contratacao (INTAKE): quem recebe os
# poderes na procuracao e quem responde pela revisao de cada area.
ADVOGADOS = {
    "WELINGTON": {"nome": "Welington Dias Valois", "oab": "OAB/ES 34.912 e OAB/MG 249.303", "genero": "M"},
    "PRISCILA": {"nome": "Priscila Araujo de Matos", "oab": "OAB/ES 39.600", "genero": "F"},
    "DERLIRA": {"nome": "Derlira Garcia Pimentel Soares", "oab": "OAB/ES 27.296", "genero": "F"},
    "HELIEZER": {"nome": "Heliézer de Medeiros Pontes", "oab": "OAB/ES 38.904", "genero": "M"},
    "GISELE": {"nome": "Gisele Teófilo de Avila", "oab": "OAB/ES 23.868", "genero": "F"},
    "GUILHERME": {"nome": "Guilherme Mota Lopes Costa", "oab": "OAB/ES 44.599", "genero": "M"},
}

# Area (mesmas chaves de INTEGRACOES/google_integration.AREAS) -> advogados da area.
# O primeiro da lista e o responsavel pela revisao. O Dr. Welington entra em todas as
# procuracoes como socio (ver contratacao.outorgados()).
ADVOGADOS_POR_AREA = {
    "PREVIDENCIARIO": ["PRISCILA"],
    "CRIMINAL": ["WELINGTON", "GUILHERME"],
    "FAMILIA E SUCESSOES": ["DERLIRA"],
    "BANCARIO": ["HELIEZER"],
    "CIVEL E CONSUMIDOR": ["GISELE"],
}

# Colaboradores para calculo da folha (ver config/regras_financeiras.py).
# 'responsavel' = recebe a participacao da area; 'na_folha' = esta na folha hoje.
# Nomes conforme aparecem nos lancamentos do ADVBOX, para conciliar.
# TODO (onboarding): confirmar quem entra na folha. Heliezer, Guilherme e Joao
# Pedro nao aparecem em nenhum lancamento de pessoal em 2026 - por isso
# na_folha=False, para nao inflar o total sem o escritorio confirmar.
COLABORADORES_FOLHA = [
    {"nome": "Priscila Araujo de Matos",       "area": "PREVIDENCIARIO",      "papel": "advogada",   "responsavel": True,  "na_folha": True},
    {"nome": "Derlira Garcia Pimentel Soares", "area": "FAMILIA E SUCESSOES", "papel": "advogada",   "responsavel": True,  "na_folha": True},
    {"nome": "Gisele Teofilo de Avila",        "area": "CIVEL E CONSUMIDOR",  "papel": "advogada",   "responsavel": True,  "na_folha": True},
    {"nome": "Heliezer de Medeiros Pontes",    "area": "BANCARIO",            "papel": "advogado",   "responsavel": True,  "na_folha": False},
    {"nome": "Guilherme Mota Lopes Costa",     "area": "CRIMINAL",            "papel": "advogado",   "responsavel": True,  "na_folha": False},
    {"nome": "Mariana Oliveira",               "area": "PREVIDENCIARIO",      "papel": "estagiaria", "responsavel": False, "na_folha": True},
    {"nome": "Maressa Teodoro",                "area": "PREVIDENCIARIO",      "papel": "estagiaria", "responsavel": False, "na_folha": True},
    {"nome": "Edmundo Godoi",                  "area": "PREVIDENCIARIO",      "papel": "estagiario", "responsavel": False, "na_folha": True},
    {"nome": "Kaua Moreira Valois",            "area": "FAMILIA E SUCESSOES", "papel": "estagiario", "responsavel": False, "na_folha": True},
    {"nome": "Joao Pedro",                     "area": "CIVEL E CONSUMIDOR",  "papel": "estagiario", "responsavel": False, "na_folha": False},
    {"nome": "Kesia Reder",                    "area": None,                  "papel": "secretaria", "responsavel": False, "na_folha": True},
]


def colaboradores_na_folha():
    """Colaboradores que entram no calculo da folha do mes."""
    return [c for c in COLABORADORES_FOLHA if c.get("na_folha")]


# Unidades do escritorio: cidade usada no local/data e no foro do contrato.
UNIDADES = {
    "IUNA": {"cidade": "Iúna/ES", "endereco": "Rua Galaor Rios, 289, Centro, Iúna/ES, CEP 29387-250"},
    "IBATIBA": {"cidade": "Ibatiba/ES", "endereco": "Rua Américo Gomes Pereira, s/n, Novo Horizonte, Ibatiba/ES, CEP 29395-000"},
    "IRUPI": {"cidade": "Irupi/ES", "endereco": "Rua João Purcino de Almeida, 168, Centro, Irupi/ES, CEP 29398-052"},
}
UNIDADE_PADRAO = "IUNA"

# Papel usado no campo 'from' das tarefas (/posts).
USUARIO_PADRAO_TAREFAS = "RESPONSAVEL"


def id_usuario(papel):
    """Retorna o ID ADVBOX do papel informado (ou None se nao configurado)."""
    valor = USUARIOS_ADVBOX.get(papel)
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return valor
