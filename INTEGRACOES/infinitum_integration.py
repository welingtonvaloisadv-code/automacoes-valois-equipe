"""
Integracao com a Infinitum (gestao de POPs / kanban do escritorio).

A Infinitum organiza o trabalho em POPs (funis) -> fases (colunas) -> cards.
POPs ja montados na organizacao "Welington Valois Advogados Associados":
CRM Comercial, Ativacao do cliente, Producao juridica inicial,
Protocolo / Distribuicao e Peticionamento.

Ela expoe um servidor MCP (JSON-RPC sobre HTTP) com ~70 ferramentas (cards,
cadastros/clientes, tarefas, agenda, automacoes, Asaas, analytics). Este modulo
chama essas ferramentas direto do Python; no Claude Code o mesmo servidor esta
em .mcp.json (infinitum). Ha tambem uma API REST publica (Swagger em
https://public.infinitum.app.br/swagger/), mais limitada - usamos o MCP.

Funcoes disponiveis:
  Baixo nivel:
    chamar(ferramenta, **argumentos) -> dict | str | None
    listar_ferramentas() -> list
    organizacao_id() -> str   (INFINITUM_ORG_ID do .env ou a 1a organizacao)

  Consulta (nao altera nada):
    organizacoes()
    pops()
    fases(pop_id)
    campos(pop_id, phase_id=None)
    cards(pop_id=None, phase_id=None, limit=50, cursor=None)
    card(card_id)
    historico_card(card_id)
    tarefas(status=None)
    usuarios()
    cadastros()
    registros(database_id, page=1, limit=50)
    agenda(time_min, time_max)
    movimentacoes(pop_id, de, ate)

Ferramentas que ALTERAM a conta (infinitum_cards_create/update/move/delete,
infinitum_tasks_*, infinitum_database_records_*, infinitum_agenda_events_*,
infinitum_automations_*, infinitum_pops_create, infinitum_fields_*,
infinitum_asaas_*, infinitum_finance_*_create...) so via chamar(), e so com
autorizacao explicita - mesma regra do ADVBOX. Cobranca Asaas pela Infinitum
gera cobranca REAL ao cliente.

Auth: public token INFINITUM_PUBLIC_TOKEN (.env), enviado como Bearer.

Uso (linha de comando):
  python INTEGRACOES/infinitum_integration.py pops
  python INTEGRACOES/infinitum_integration.py fases <pop_id>
  python INTEGRACOES/infinitum_integration.py cards [pop_id]
  python INTEGRACOES/infinitum_integration.py card <card_id>
  python INTEGRACOES/infinitum_integration.py tarefas
  python INTEGRACOES/infinitum_integration.py usuarios
  python INTEGRACOES/infinitum_integration.py cadastros
  python INTEGRACOES/infinitum_integration.py ferramentas
"""
import os
import json
import logging
import itertools
import requests

log = logging.getLogger('integracoes.infinitum')

MCP_URL = 'https://public.infinitum.app.br/mcp'
_ids = itertools.count(1)
_org_cache = None


# ============================================================
# BAIXO NIVEL
# ============================================================

def get_headers():
    """Retorna headers Bearer. None se token ausente."""
    token = os.getenv('INFINITUM_PUBLIC_TOKEN')
    if not token:
        log.warning('INFINITUM_PUBLIC_TOKEN ausente no .env')
        return None
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
    }


def _rpc(metodo, params=None, timeout=60):
    """Requisicao JSON-RPC ao servidor MCP. Devolve o 'result' ou None."""
    headers = get_headers()
    if not headers:
        return None
    corpo = {'jsonrpc': '2.0', 'id': next(_ids), 'method': metodo}
    if params is not None:
        corpo['params'] = params
    try:
        r = requests.post(MCP_URL, headers=headers, json=corpo, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        log.error('Infinitum %s falhou: %s', metodo, e)
        return None
    r.encoding = 'utf-8'  # SSE vem sem charset; sem isto o requests decodifica como latin-1
    if r.headers.get('Content-Type', '').startswith('text/event-stream'):
        dados = [l[5:].strip() for l in r.text.splitlines() if l.startswith('data:')]
        resp = json.loads(dados[-1]) if dados else {}
    else:
        resp = r.json()
    if 'error' in resp:
        log.error('Infinitum %s erro: %s', metodo, resp['error'])
        return None
    return resp.get('result')


def listar_ferramentas():
    res = _rpc('tools/list') or {}
    return res.get('tools', [])


def chamar(ferramenta, **argumentos):
    """Chama uma ferramenta da Infinitum. Devolve o JSON decodificado (ou o texto)."""
    args = {k: v for k, v in argumentos.items() if v is not None}
    res = _rpc('tools/call', {'name': ferramenta, 'arguments': args})
    if res is None:
        return None
    if res.get('structuredContent') is not None:
        return res['structuredContent']
    texto = '\n'.join(c.get('text', '') for c in res.get('content', [])
                      if c.get('type') == 'text')
    if res.get('isError'):
        log.error('Infinitum %s: %s', ferramenta, texto)
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return texto


def organizacao_id():
    """ID da organizacao: INFINITUM_ORG_ID do .env, senao a primeira do token."""
    global _org_cache
    if _org_cache:
        return _org_cache
    _org_cache = os.getenv('INFINITUM_ORG_ID')
    if not _org_cache:
        res = organizacoes() or {}
        lista = res.get('data') if isinstance(res, dict) else res
        if lista:
            _org_cache = lista[0]['id']
    return _org_cache


# ============================================================
# CONSULTA
# ============================================================

def organizacoes():
    return chamar('infinitum_organizations_list')


def pops():
    return chamar('infinitum_pops_list', organization_id=organizacao_id(), limit=100)


def fases(pop_id):
    return chamar('infinitum_phases_list', pop_id=pop_id)


def campos(pop_id, phase_id=None):
    return chamar('infinitum_fields_list', pop_id=pop_id, phase_id=phase_id, limit=100)


def cards(pop_id=None, phase_id=None, limit=50, cursor=None):
    return chamar('infinitum_cards_list', organization_id=organizacao_id(),
                  pop_id=pop_id, phase_id=phase_id, limit=limit, cursor=cursor)


def card(card_id):
    return chamar('infinitum_cards_get', id=card_id)


def historico_card(card_id):
    return chamar('infinitum_cards_history', id=card_id)


def tarefas(status=None):
    return chamar('infinitum_tasks_list', organization_id=organizacao_id(), status=status)


def usuarios():
    return chamar('infinitum_organization_users_list', organization_id=organizacao_id())


def cadastros():
    return chamar('infinitum_databases_list', organization_id=organizacao_id())


def registros(database_id, page=1, limit=50):
    return chamar('infinitum_database_records_list', database_id=database_id,
                  page=page, limit=limit)


def agenda(time_min, time_max):
    """time_min/time_max em RFC3339 UTC (ex.: 2026-11-01T00:00:00Z)."""
    return chamar('infinitum_agenda_events_list', organization_id=organizacao_id(),
                  time_min=time_min, time_max=time_max)


def movimentacoes(pop_id, de=None, ate=None):
    return chamar('infinitum_pops_movements', pop_id=pop_id, **{'from': de, 'to': ate})


if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    sys.stdout.reconfigure(encoding='utf-8')

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'pops'
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if cmd == 'ferramentas':
        for t in listar_ferramentas():
            print(f"{t['name']:44} {t.get('description', '')[:80]}")
        sys.exit(0)
    acoes = {
        'pops': pops,
        'fases': lambda: fases(arg),
        'cards': lambda: cards(pop_id=arg),
        'card': lambda: card(arg),
        'tarefas': tarefas,
        'usuarios': usuarios,
        'cadastros': cadastros,
    }
    if cmd not in acoes or (cmd in ('fases', 'card') and not arg):
        print(__doc__)
        sys.exit(1)
    saida = acoes[cmd]()
    print(json.dumps(saida, ensure_ascii=False, indent=2)
          if not isinstance(saida, str) else saida)
