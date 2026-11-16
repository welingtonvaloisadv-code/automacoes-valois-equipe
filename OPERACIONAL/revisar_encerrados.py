"""
Lista de processos PROVAVELMENTE ENCERRADOS - Welington Valois Advogados Associados

O ADVBOX do escritorio nao registra o fim do processo (nenhum em fase de arquivado/transito),
entao "ativos" inclui processos ja findos. Isso distorce os KPIs e faria o relatorio mensal
(POP 05) sair para cliente de processo encerrado. Este script cruza tres fontes e aponta
os candidatos para a EQUIPE confirmar. SO LEITURA - nao altera nada no ADVBOX.

  python OPERACIONAL/revisar_encerrados.py

Sinais usados (cada um vira um motivo escrito na planilha):
  - fase atual (sentenca proferida, recurso julgado, concluido INSS, RPV...)
  - ultima movimentacao do tribunal (texto de arquivamento/baixa/transito, e ha quanto tempo)
  - tarefas da equipe (tarefa de desfecho concluida, pendencias abertas, ultima atividade)

Saida: SAIDA/revisao_encerrados/AAAA-MM-DD/ (gitignored - dado de cliente)
  - REVISAR_ENCERRADOS.csv   uma linha por processo; a equipe preenche as 3 ultimas colunas
  - RESUMO.md
"""
import sys, os, io, csv
from datetime import datetime
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding='utf-8')
RAIZ = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RAIZ, 'INTEGRACOES'))
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(RAIZ, 'config', '.env'))

from advbox_integration import _request, listar_ultimas_movimentacoes, _sem_acento
from kpis_advbox import listar_processos, encerrado, _data, _inicio

HOJE = datetime.now()

FASES_DE_DESFECHO = ('SENTENCA PROFERIDA', 'RECURSO JULGADO', 'DECISAO PROFERIDA', 'DECISAO DO RECURSO',
                     'CONCLUIDO INSS', 'RPV EMITIDO', 'AGUARDANDO PAGAMENTO', 'EXECUCAO JULGADA',
                     'NAO CABE MAIS RECURSO')
MOV_DE_ENCERRAMENTO = ('ARQUIV', 'BAIXA DEFINITIVA', 'BAIXADO', 'TRANSITO', 'TRANSITOU', 'TRANSITAD',
                       'EXTINC', 'EXTINTO', 'REMETIDOS OS AUTOS', 'DEFINITIVAMENTE')
TAREFAS_DE_DESFECHO = ('PROCESSO GANHO', 'PROCESSO PERDIDO', 'ARQUIVAR', 'LEVANTAMENTO DE RPV',
                       'LEVANTAMENTO DE ALVARA', 'IMPLANTAR BENEFICIO', 'ACOMPANHAR TRANSITO')

CORTE_ENCERRADO = 5
CORTE_VERIFICAR = 3


def listar_posts(**filtros):
    todos, offset = [], 0
    while True:
        data = _request('GET', '/posts', params={**filtros, 'limit': 100, 'offset': offset})
        registros = data.get('data', [])
        todos.extend(registros)
        total = data.get('totalCount', 0)
        print(f'  Tarefas ADVBOX: {len(todos)}/{total}', end='\r')
        if len(todos) >= total or not registros:
            print()
            return todos
        offset += len(registros)


def _concluida_em(post):
    datas = [_data(u.get('completed')) for u in post.get('users') or [] if u.get('completed')]
    return max(datas) if datas else None


def indexar_tarefas():
    fim = f'{HOJE.year + 1}-12-31'
    concluidas = listar_posts(completed_start='2015-01-01', completed_end=fim)
    pendentes = listar_posts()  # sem filtro de conclusao: a API devolve as pendentes
    por_proc = defaultdict(lambda: {'ultima': None, 'pendentes': 0, 'desfecho': set()})
    for post, pend in [(p, False) for p in concluidas] + [(p, True) for p in pendentes]:
        pid = post.get('lawsuits_id')
        if not pid:
            continue
        info = por_proc[pid]
        quando = _concluida_em(post) or _data(post.get('created_at')) or _data(post.get('date'))
        if quando and (not info['ultima'] or quando > info['ultima']):
            info['ultima'] = quando
        if pend and not _concluida_em(post):
            info['pendentes'] += 1
        nome = _sem_acento(post.get('task'))
        if not pend and any(t in nome for t in TAREFAS_DE_DESFECHO):
            info['desfecho'].add(post.get('task'))
    return por_proc


def avaliar(p, mov, tar):
    pontos, motivos = 0, []
    fase = _sem_acento(p.get('stage'))
    if any(f in fase for f in FASES_DE_DESFECHO):
        pontos += 2
        motivos.append(f'fase de desfecho: {p.get("stage")}')

    if mov:
        dias = (HOJE - _data(mov['date'])).days
        texto = _sem_acento(mov.get('title'))
        if any(k in texto for k in MOV_DE_ENCERRAMENTO):
            pontos += 3
            motivos.append(f'ultima mov. tribunal indica fim ({mov["date"]}): {mov["title"][:80]!s}'.replace('\n', ' '))
        if dias > 365:
            pontos += 2
            motivos.append(f'tribunal parado ha {dias} dias')
        elif dias > 180:
            pontos += 1
            motivos.append(f'tribunal parado ha {dias} dias')
        elif dias <= 90:
            pontos -= 3
            motivos.append(f'movimentou no tribunal ha {dias} dias')

    if tar['desfecho']:
        pontos += 3
        motivos.append('tarefa de desfecho concluida: ' + ', '.join(sorted(tar['desfecho'])))
    if tar['pendentes']:
        pontos -= 3
        motivos.append(f'{tar["pendentes"]} tarefa(s) pendente(s)')
    else:
        pontos += 1
        motivos.append('nenhuma tarefa pendente')
    if tar['ultima']:
        dias = (HOJE - tar['ultima']).days
        if dias > 365:
            pontos += 2
            motivos.append(f'sem atividade da equipe ha {dias} dias')
        elif dias > 180:
            pontos += 1
            motivos.append(f'sem atividade da equipe ha {dias} dias')
    else:
        pontos += 1
        motivos.append('nenhuma tarefa registrada no processo')

    # "Ativo" exige prova de andamento; ausencia de sinal de encerramento nao basta.
    andamento = (tar['pendentes'] > 0
                 or (mov and (HOJE - _data(mov['date'])).days <= 90)
                 or (tar['ultima'] and (HOJE - tar['ultima']).days <= 180))
    if pontos >= CORTE_ENCERRADO:
        classe = 'PROVAVEL ENCERRADO'
    elif pontos >= CORTE_VERIFICAR:
        classe = 'VERIFICAR'
    elif andamento:
        classe = 'PROVAVEL ATIVO'
    else:
        classe = 'SEM SINAL DE ANDAMENTO'
    return pontos, classe, motivos


def main():
    print('Revisao de encerrados - somente leitura')
    processos = [p for p in listar_processos() if not encerrado(p)]
    movs = {m['lawsuit_id']: m for m in listar_ultimas_movimentacoes()}
    tarefas = indexar_tarefas()
    vazio = {'ultima': None, 'pendentes': 0, 'desfecho': set()}

    linhas = []
    for p in processos:
        mov, tar = movs.get(p['id']), tarefas.get(p['id'], vazio)
        pontos, classe, motivos = avaliar(p, mov, tar)
        ini = _inicio(p)
        linhas.append({
            'classificacao': classe, 'pontos': pontos,
            'responsavel': p.get('responsible') or '',
            'cliente': ', '.join(c.get('name', '') for c in p.get('customers') or []),
            'area': p.get('group') or '', 'tipo': p.get('type') or '',
            'numero_processo': p.get('process_number') or p.get('protocol_number') or '',
            'fase_atual': p.get('stage') or '',
            'inicio': ini.strftime('%d/%m/%Y') if ini else '',
            'ultima_mov_tribunal': datetime.strptime(mov['date'], '%Y-%m-%d').strftime('%d/%m/%Y') if mov else '',
            'ultima_atividade_equipe': tar['ultima'].strftime('%d/%m/%Y') if tar['ultima'] else '',
            'motivos': ' | '.join(motivos),
            'id_advbox': p['id'],
            'situacao_confirmada (ENCERRADO/ATIVO)': '', 'fase_correta_no_advbox': '', 'revisado_por': '',
        })

    ordem = {'PROVAVEL ENCERRADO': 0, 'VERIFICAR': 1, 'SEM SINAL DE ANDAMENTO': 2, 'PROVAVEL ATIVO': 3}
    linhas.sort(key=lambda l: (ordem[l['classificacao']], l['responsavel'], -l['pontos']))

    pasta = os.path.join(RAIZ, 'SAIDA', 'revisao_encerrados', f'{HOJE:%Y-%m-%d}')
    os.makedirs(pasta, exist_ok=True)
    with open(os.path.join(pasta, 'REVISAR_ENCERRADOS.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=';')
        w.writeheader()
        w.writerows(linhas)

    classes = Counter(l['classificacao'] for l in linhas)
    por_resp = defaultdict(Counter)
    for l in linhas:
        por_resp[l['responsavel']][l['classificacao']] += 1
    R = [f'# Revisao de processos provavelmente encerrados - {HOJE:%d/%m/%Y}\n',
         f'{len(linhas)} processos hoje marcados como ativos no ADVBOX (os 22 ja em fase de encerramento ficaram de fora).\n',
         '| Classificacao | Qtde |', '|---|---|']
    R += [f'| {c} | {classes.get(c, 0)} |' for c in ordem]
    R += ['\n## Por responsavel\n',
          '| Responsavel | Provavel encerrado | Verificar | Sem sinal de andamento | Provavel ativo |',
          '|---|---|---|---|---|']
    for resp, c in sorted(por_resp.items(), key=lambda kv: -(kv[1]['PROVAVEL ENCERRADO'] + kv[1]['VERIFICAR'])):
        R.append(f'| {resp} | {c["PROVAVEL ENCERRADO"]} | {c["VERIFICAR"]} | '
                 f'{c["SEM SINAL DE ANDAMENTO"]} | {c["PROVAVEL ATIVO"]} |')
    R += ['\n## Como usar\n',
          '1. Cada responsavel filtra a planilha pelo seu nome e confere as linhas PROVAVEL ENCERRADO, VERIFICAR e SEM SINAL DE ANDAMENTO (processo sem tarefa aberta, sem movimentacao recente e sem atividade da equipe ha 6+ meses).',
          '2. Preenche `situacao_confirmada` (ENCERRADO/ATIVO), a fase correta e `revisado_por`.',
          '3. A mudanca de fase no ADVBOX e feita pela equipe (ou pela automacao, so com autorizacao expressa e a partir desta planilha revisada).',
          '\nA pontuacao e indicio, nao conclusao: a coluna `motivos` diz por que cada processo foi apontado.']
    with open(os.path.join(pasta, 'RESUMO.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(R) + '\n')
    print('\n'.join(R))
    print(f'\nSalvo em {os.path.normpath(pasta)}')


if __name__ == '__main__':
    main()
