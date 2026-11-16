"""
KPIs do ADVBOX - Welington Valois Advogados Associados

Indicadores pedidos na reuniao de 14/09/2026: processos ativos e encerrados,
tempo medio de processo e ticket medio. SO LEITURA - nao altera nada no ADVBOX.

  python OPERACIONAL/kpis_advbox.py

Saida: SAIDA/kpis/AAAA-MM-DD/ (gitignored - contem nome de cliente)
  - KPIS.md            resumo para o escritorio
  - processos.csv      base usada no calculo (para conferir)
"""
import sys, os, io, csv, statistics
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
RAIZ = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RAIZ, 'INTEGRACOES'))

from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, 'config', '.env'))

from advbox_integration import _request, listar_transacoes, _sem_acento

# ATENCAO: 'status_closure' NAO e encerramento do processo. Conferido em 22/09/2026: processos com
# esse campo estao em "ACAO PROTOCOLADA", "COM JUIZ(A)"... (parece ser o fechamento do contrato).
# Encerrado = processo numa fase de encerramento. A API nao informa QUANDO entrou na fase, entao
# o tempo total de processo so sera calculavel quando o escritorio registrar o encerramento.
FASES_ENCERRAMENTO = ('ARQUIV', 'TRANSITO', 'NAO DISTRIBU', 'FINALIZ', 'ENCERRAD')


def encerrado(p):
    fase = _sem_acento(p.get('stage'))
    return any(f in fase for f in FASES_ENCERRAMENTO)


def _data(txt):
    if not txt:
        return None
    try:
        return datetime.strptime(str(txt)[:10], '%Y-%m-%d')
    except ValueError:
        return None


def _inicio(p):
    return _data(p.get('process_date')) or _data(p.get('created_at'))


def listar_processos():
    todos, offset = [], 0
    while True:
        data = _request('GET', '/lawsuits', params={'limit': 100, 'offset': offset})
        registros = data.get('data', [])
        todos.extend(registros)
        print(f'  Processos ADVBOX: {len(todos)}/{data.get("totalCount", 0)}')
        if len(todos) >= data.get('totalCount', 0) or not registros:
            return todos
        offset += 100


def _brl(v):
    return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _dias(v):
    return f'{v:.0f} dias (~{v / 30.4:.1f} meses)'


def _media(vals, fmt):
    return fmt(statistics.mean(vals)) if vals else '-'


def calcular(processos, transacoes):
    hoje = datetime.now()
    recebido = defaultdict(float)
    for t in transacoes:
        if t.get('entry_type') == 'income' and t.get('date_payment') and t.get('lawsuit_id'):
            recebido[t['lawsuit_id']] += float(t.get('amount') or 0)

    for p in processos:
        ini = _inicio(p)
        p['_encerrado'] = encerrado(p)
        p['_recebido'] = recebido.get(p['id'], 0.0)
        # Idade: ha quanto tempo o processo existe (so faz sentido para os ativos)
        p['_idade'] = (hoje - ini).days if ini and not p['_encerrado'] else None
        # Tempo de producao: inicio -> 'saida da producao' (exit_production), quando preenchido
        saida = _data(p.get('exit_production'))
        p['_producao'] = (saida - ini).days if ini and saida and saida >= ini else None


def tabela_area(processos):
    L = ['| Area | Total | Ativos | Encerrados | Idade media dos ativos | Recebido | Ticket medio |',
         '|---|---|---|---|---|---|---|']
    g = defaultdict(list)
    for p in processos:
        g[p.get('group') or '(sem)'].append(p)
    for nome, ps in sorted(g.items(), key=lambda kv: -len(kv[1])):
        enc = sum(p['_encerrado'] for p in ps)
        idades = [p['_idade'] for p in ps if p['_idade'] is not None]
        pagos = [p['_recebido'] for p in ps if p['_recebido'] > 0]
        L.append(f'| {nome} | {len(ps)} | {len(ps) - enc} | {enc} | '
                 f'{_media(idades, lambda v: f"{v:.0f} d")} | {_brl(sum(pagos))} | {_media(pagos, _brl)} |')
    return L


def main():
    print('KPIs ADVBOX - somente leitura')
    processos = listar_processos()
    transacoes = listar_transacoes()
    calcular(processos, transacoes)

    ativos = [p for p in processos if not p['_encerrado']]
    encerrados = [p for p in processos if p['_encerrado']]
    idades = [p['_idade'] for p in ativos if p['_idade'] is not None]
    producao = [p['_producao'] for p in processos if p['_producao'] is not None]
    pagos = [p['_recebido'] for p in processos if p['_recebido'] > 0]

    L = [f'# KPIs ADVBOX - {datetime.now():%d/%m/%Y}\n',
         'Fonte: API ADVBOX (somente leitura). Numeros para conferencia do escritorio.\n',
         '## Visao geral\n', '| Indicador | Valor |', '|---|---|',
         f'| Processos cadastrados | {len(processos)} |',
         f'| Ativos | {len(ativos)} |',
         f'| Encerrados (em fase de arquivamento/nao distribuido) | {len(encerrados)} |',
         f'| Tempo medio de processo (inicio -> fim) | **nao calculavel** - ver observacao 1 |',
         f'| Idade media dos ativos | {_media(idades, _dias)} |',
         f'| Idade mediana dos ativos | {_dias(statistics.median(idades)) if idades else "-"} |',
         f'| Tempo ate sair da producao ({len(producao)} processos) | {_media(producao, _dias)} |',
         f'| Honorarios recebidos vinculados a processo | {_brl(sum(pagos))} |',
         f'| Ticket medio (recebido por processo que pagou) | {_media(pagos, _brl)} |',
         f'| Ticket mediano | {_brl(statistics.median(pagos)) if pagos else "-"} |',
         f'| Processos com algum recebimento | {len(pagos)} de {len(processos)} |',
         '\n## Por area (grupo do tipo de acao)\n']
    L += tabela_area(processos)

    L += ['\n## Por responsavel\n', '| Responsavel | Ativos | Encerrados |', '|---|---|---|']
    g = defaultdict(list)
    for p in processos:
        g[p.get('responsible') or '(sem)'].append(p)
    for nome, ps in sorted(g.items(), key=lambda kv: -len(kv[1])):
        enc = sum(p['_encerrado'] for p in ps)
        L.append(f'| {nome} | {len(ps) - enc} | {enc} |')

    L += ['\n## Ativos por fase\n', '| Fase | Qtde |', '|---|---|']
    g = defaultdict(int)
    for p in ativos:
        g[p.get('stage') or '(sem)'] += 1
    for nome, n in sorted(g.items(), key=lambda kv: -kv[1]):
        L.append(f'| {nome} | {n} |')

    L += ['\n## Observacoes para o escritorio\n',
          '1. **Tempo medio de processo nao sai do ADVBOX hoje.** Nenhum processo esta em fase de '
          'arquivado/transito em julgado, e a API nao informa a data em que o processo mudou de fase. '
          'Para este KPI existir, o fim do processo precisa ser registrado (mover para "ARQUIVADO/ENCERRADO" '
          'ou "TRANSITO EM JULGADO" e preencher a data de saida). Ate la, "ativos" inclui processos ja findos.',
          '2. O campo de "encerramento" do ADVBOX esta preenchido em processos que seguem em andamento '
          '(ex.: "COM JUIZ(A) PARA ANALISE"); por isso NAO foi usado como fim de processo.',
          '3. **Ticket medio** considera so receita PAGA e vinculada a processo. Receita lancada sem '
          'processo nao entra; processos sem nenhum recebimento (ex.: previdenciario ainda sem exito) '
          'ficam fora da media.',
          '4. "Tempo ate sair da producao" usa o campo "saida da producao" (exit_production), preenchido '
          f'em apenas {len(producao)} processos - confirmar com o escritorio o que esse campo significa no uso de voces.']

    pasta = os.path.join(RAIZ, 'SAIDA', 'kpis', f'{datetime.now():%Y-%m-%d}')
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, 'KPIS.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    with open(os.path.join(pasta, 'processos.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['id', 'numero', 'cliente', 'area', 'tipo', 'responsavel', 'fase', 'situacao',
                    'data_processo', 'idade_dias', 'recebido'])
        for p in processos:
            cli = ', '.join(c.get('name', '') for c in p.get('customers') or [])
            w.writerow([p['id'], p.get('process_number') or '', cli, p.get('group'), p.get('type'),
                        p.get('responsible'), p.get('stage'),
                        'ENCERRADO' if p['_encerrado'] else 'ATIVO', p.get('process_date') or '',
                        p['_idade'] if p['_idade'] is not None else '',
                        f'{p["_recebido"]:.2f}'.replace('.', ',')])
    print('\n'.join(L))
    print(f'\nSalvo em {os.path.normpath(pasta)}')


if __name__ == '__main__':
    main()
