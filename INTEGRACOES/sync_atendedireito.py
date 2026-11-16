"""
Integracao com o Sync - Atende Direito (monitoramento de processos PDPJ/DJEN).

O Sync expoe um servidor MCP (JSON-RPC sobre HTTP). Este modulo chama as
ferramentas dele direto do Python, para os scripts do escritorio. No Claude Code
o mesmo servidor esta em .mcp.json (atendedireito-sync).

Funcoes disponiveis:
  Baixo nivel:
    chamar(ferramenta, **argumentos) -> dict | str | None
    listar_ferramentas() -> list

  Consulta (nao altera nada):
    painel_do_dia()
    prazos_a_vencer()
    intimacoes(status=None, dias=0, com_prazo=None, pagina=1, itens=50)
    listar_processos(pagina=1, itens=50, busca=None)
    ver_processo(numero)
    buscar_processos(tipo, valor)

Ferramentas que ALTERAM a conta (tratar_intimacao, registrar_processo,
criar_monitor, criar_mineracao, excluir_processo...) so via chamar(), e so com
autorizacao explicita - mesma regra do ADVBOX.

Auth: Bearer token ATENDEDIREITO_SYNC_TOKEN (.env).

Uso (linha de comando):
  python INTEGRACOES/sync_atendedireito.py painel
  python INTEGRACOES/sync_atendedireito.py prazos
  python INTEGRACOES/sync_atendedireito.py intimacoes
  python INTEGRACOES/sync_atendedireito.py processo <CNJ>
  python INTEGRACOES/sync_atendedireito.py ferramentas
"""
import os
import json
import logging
import itertools
import requests

log = logging.getLogger('integracoes.sync_atendedireito')

MCP_URL = 'https://api.sync.atendedireito.app/mcp'
_ids = itertools.count(1)


# ============================================================
# BAIXO NIVEL
# ============================================================

def get_headers():
    """Retorna headers Bearer. None se token ausente."""
    token = os.getenv('ATENDEDIREITO_SYNC_TOKEN')
    if not token:
        log.warning('ATENDEDIREITO_SYNC_TOKEN ausente no .env')
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
        log.error('Sync %s falhou: %s', metodo, e)
        return None
    r.encoding = 'utf-8'  # SSE vem sem charset; sem isto o requests decodifica como latin-1
    if r.headers.get('Content-Type', '').startswith('text/event-stream'):
        # resposta em SSE: pega a ultima linha 'data:'
        dados = [l[5:].strip() for l in r.text.splitlines() if l.startswith('data:')]
        resp = json.loads(dados[-1]) if dados else {}
    else:
        resp = r.json()
    if 'error' in resp:
        log.error('Sync %s erro: %s', metodo, resp['error'])
        return None
    return resp.get('result')


def listar_ferramentas():
    res = _rpc('tools/list') or {}
    return res.get('tools', [])


def chamar(ferramenta, **argumentos):
    """Chama uma ferramenta do Sync. Devolve o JSON decodificado (ou o texto)."""
    args = {k: v for k, v in argumentos.items() if v is not None}
    res = _rpc('tools/call', {'name': ferramenta, 'arguments': args})
    if res is None:
        return None
    if res.get('structuredContent') is not None:
        return res['structuredContent']
    texto = '\n'.join(c.get('text', '') for c in res.get('content', [])
                      if c.get('type') == 'text')
    if res.get('isError'):
        log.error('Sync %s: %s', ferramenta, texto)
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return texto


# ============================================================
# CONSULTA
# ============================================================

def painel_do_dia():
    return chamar('painel_do_dia')


def prazos_a_vencer():
    return chamar('prazos_a_vencer')


def intimacoes(status=None, dias=0, com_prazo=None, pagina=1, itens=50):
    return chamar('intimacoes', status=status, dias=dias, com_prazo=com_prazo,
                  pagina=pagina, itens=itens)


def listar_processos(pagina=1, itens=50, busca=None):
    return chamar('listar_processos', pagina=pagina, itens=itens, busca=busca)


def ver_processo(numero):
    return chamar('ver_processo', numero=numero)


def buscar_processos(tipo, valor):
    return chamar('buscar_processos', tipo=tipo, valor=valor)


if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    sys.stdout.reconfigure(encoding='utf-8')

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'painel'
    if cmd == 'ferramentas':
        for t in listar_ferramentas():
            print(f"{t['name']:24} {t.get('description', '')[:90]}")
        sys.exit(0)
    acoes = {
        'painel': painel_do_dia,
        'prazos': prazos_a_vencer,
        'intimacoes': intimacoes,
        'processo': lambda: ver_processo(sys.argv[2]),
    }
    if cmd not in acoes:
        print(__doc__)
        sys.exit(1)
    saida = acoes[cmd]()
    print(json.dumps(saida, ensure_ascii=False, indent=2)
          if not isinstance(saida, str) else saida)
