"""
TRATAMENTO AUTOMATICO DE PUBLICACOES (POP 10) - Welington Valois Advogados Associados

Para cada publicacao nova do Sync (Atende Direito / DJEN):
  1. casa o processo no ADVBOX (area, cliente, responsavel, historico de tarefas);
  2. a IA identifica COMO O ESCRITORIO TRATA aquela publicacao (config/regras_publicacoes.py
     + o historico do proprio processo) e o ato a praticar;
  3. calcula prazo fatal e prazo interno (3 dias uteis antes; urgencia = mesmo dia) [CONFERIR];
  4. minuta a peca no timbrado, marcada PRONTA PARA REVISAO do advogado da area;
  5. lanca a tarefa no ADVBOX para advogado + controller (e a do suporte, se houver);
     a tarefa com prazo aparece na agenda do ADVBOX; o prazo ja fica na agenda do Sync;
     opcional: evento no Google Agenda (AGENDA_GOOGLE=1);
  6. atualiza o painel diario do Dr. Welington (OPERACIONAL/painel_dr_welington.py).

A IA NUNCA PROTOCOLA e nada aqui marca a intimacao como tratada no Sync (POP 09 item 6.3).

Uso:
  python OPERACIONAL/tratamento_publicacoes.py rodar              # simulacao: nao lanca no ADVBOX
  python OPERACIONAL/tratamento_publicacoes.py rodar --executar   # lanca tarefas no ADVBOX
      [--limite N] [--sem-peca] [--desde AAAA-MM-DD] [--reprocessar ID]
  python OPERACIONAL/tratamento_publicacoes.py diario --executar --abrir   # usado pelo agendador
  python OPERACIONAL/tratamento_publicacoes.py painel [--abrir]
  python OPERACIONAL/tratamento_publicacoes.py autorizar-agenda   # 1a vez do Google Agenda
"""
import os
import re
import sys
import json
import time
import logging
import argparse
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / 'INTEGRACOES'))
sys.path.insert(0, str(RAIZ / 'OPERACIONAL'))
sys.path.append(str(RAIZ / 'OPERACIONAL' / 'agente_operacional'))  # no fim: ele tem um config.py proprio

from dotenv import load_dotenv
load_dotenv(RAIZ / 'config' / '.env')

import requests
import importlib.util


def _carregar_regras():
    spec = importlib.util.spec_from_file_location('regras_publicacoes', RAIZ / 'config' / 'regras_publicacoes.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


R = _carregar_regras()
from INTEGRACOES import sync_atendedireito as sync
import ia_backend

SAIDA = RAIZ / 'SAIDA' / 'publicacoes'
ESTADO = SAIDA / 'estado.json'
TRAVA = SAIDA / '.rodando'
log = logging.getLogger('publicacoes')


# ============================================================
# UTILITARIOS
# ============================================================

def _sem_acento(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t or '') if unicodedata.category(c) != 'Mn')


def _slug(t, n=60):
    t = re.sub(r'[^\w\s.-]', '', _sem_acento(t)).strip()
    return re.sub(r'\s+', ' ', t)[:n]


def _d(txt):
    return datetime.strptime(txt[:10], '%Y-%m-%d').date() if txt else None


def br(d):
    return d.strftime('%d/%m/%Y') if d else '-'


def carregar_estado():
    if ESTADO.exists():
        return json.loads(ESTADO.read_text(encoding='utf-8'))
    return {'marco_inicial': '', 'registros': {}, 'execucoes': []}


def salvar_estado(est):
    SAIDA.mkdir(parents=True, exist_ok=True)
    tmp = ESTADO.with_suffix('.tmp')
    tmp.write_text(json.dumps(est, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    tmp.replace(ESTADO)


# ============================================================
# CALENDARIO FORENSE (dias uteis) - sempre [CONFERIR]: nao tem feriado municipal/estadual
# ============================================================

def _pascoa(ano):
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(ano):
    fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25),
             (12, 8)]  # 8/12: Dia da Justica (expediente forense)
    p = _pascoa(ano)
    moveis = [p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2),
              p + timedelta(days=60)]
    return {date(ano, m, d) for m, d in fixos} | set(moveis)


def em_recesso(d):
    """CPC art. 220: prazos suspensos de 20/12 a 20/01."""
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 20)


def dia_util(d, criminal=False):
    if d.weekday() >= 5 or d in feriados(d.year):
        return False
    return criminal or not em_recesso(d)


def somar_uteis(inicio, n, criminal=False):
    """Conta n dias uteis a partir de 'inicio' (inicio = 1o dia do prazo)."""
    d, contados = inicio, 0
    while True:
        if dia_util(d, criminal):
            contados += 1
            if contados >= n:
                return d
        d += timedelta(days=1)


def somar_corridos(inicio, n, criminal=False):
    d = inicio + timedelta(days=n - 1)
    while not dia_util(d, criminal):
        d += timedelta(days=1)
    return d


def voltar_uteis(fim, n, criminal=False):
    d, contados = fim, 0
    while contados < n:
        d -= timedelta(days=1)
        if dia_util(d, criminal):
            contados += 1
    return d


# ============================================================
# FONTES: SYNC, DJEN, ADVBOX
# ============================================================

def intimacoes_pendentes():
    """Todas as intimacoes pendentes (nao tratadas) do Sync, paginando."""
    todas, pagina = [], 1
    while pagina <= 20:
        r = sync.intimacoes(status='pendentes', pagina=pagina, itens=50)
        if not isinstance(r, dict):
            raise RuntimeError(f'Sync nao respondeu: {str(r)[:200]}')
        lote = r.get('intimacoes') or []
        todas.extend(lote)
        if not lote or len(todas) >= (r.get('total') or 0):
            break
        pagina += 1
    vistos, unicas = set(), []
    for i in todas:
        if i['id'] not in vistos:
            vistos.add(i['id'])
            unicas.append(i)
    return unicas


def prazos_sync():
    r = sync.prazos_a_vencer()
    return (r or {}).get('a_vencer', []) if isinstance(r, dict) else []


def teor_djen(numero, disponibilizacao):
    """Texto integral no DJEN quando o Sync corta o teor (comunicaapi.pje.jus.br)."""
    digitos = re.sub(r'\D', '', numero or '')
    if len(digitos) != 20 or not disponibilizacao:
        return ''
    try:
        r = requests.get('https://comunicaapi.pje.jus.br/api/v1/comunicacao', timeout=30,
                         headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
                         params={'numeroProcesso': digitos, 'itensPorPagina': 50,
                                 'dataDisponibilizacaoInicio': disponibilizacao,
                                 'dataDisponibilizacaoFim': disponibilizacao})
        itens = r.json().get('items', []) if r.ok else []
    except (requests.RequestException, ValueError):
        return ''
    textos = [re.sub(r'<[^>]+>', ' ', i.get('texto') or '') for i in itens]
    return max(textos, key=len, default='').strip()


TIPOS_RELEVANTES = ('peticao inicial', 'contestacao', 'laudo', 'pericia', 'estudo social', 'sentenca',
                    'acordao', 'decisao', 'despacho', 'apelacao', 'recurso', 'contrarrazoes', 'impugnacao',
                    'denuncia', 'resposta a acusacao', 'alegacoes', 'calculo', 'dossie', 'replica', 'embargos')


def _ler_doc(doc_id, limite):
    texto, offset = '', 0
    while len(texto) < limite:
        r = sync.chamar('ler_documento', documento_id=doc_id, offset=offset or None)
        if not isinstance(r, dict) or not r.get('markdown'):
            break
        texto += r['markdown']
        offset = r.get('proximo_offset') or (offset + len(r['markdown']))
        if offset >= (r.get('markdown_total_chars') or 0):
            break
    return texto[:limite]


def pecas_dos_autos(numero, para='minuta', disponibilizacao=''):
    """Teor das pecas relevantes dos autos (Sync). 'triagem' = so o recente; 'minuta' = inicial,
    contestacao, laudo, ultima decisao/sentenca e recursos. Falha silenciosa: devolve ''."""
    try:
        proc = sync.ver_processo(numero)
        docs = (proc or {}).get('documentos') or [] if isinstance(proc, dict) else []
    except Exception:
        return ''
    docs = [d for d in docs if d.get('conteudo_status') == 'disponivel' and d.get('tem_markdown', True)]
    docs.sort(key=lambda d: d.get('data_juntada') or '', reverse=True)

    def tipo(d):
        return _sem_acento(f"{d.get('tipo', '')} {d.get('nome', '')}").lower()
    escolhidos = []
    if para == 'triagem':
        corte = str(_d(disponibilizacao) - timedelta(days=20)) if disponibilizacao else ''
        escolhidos = [d for d in docs if (d.get('data_juntada') or '') >= corte
                      and any(t in tipo(d) for t in TIPOS_RELEVANTES) and 'certidao' not in tipo(d)][:3]
        limite_doc, limite_total = 15000, 40000
    else:
        vistos = set()
        for chave in TIPOS_RELEVANTES:
            d = next((d for d in docs if chave in tipo(d) and 'certidao' not in tipo(d)), None)
            if d and d['id'] not in vistos:
                vistos.add(d['id'])
                escolhidos.append(d)
        escolhidos.sort(key=lambda d: d.get('data_juntada') or '')
        limite_doc, limite_total = 30000, 150000
    partes, total = [], 0
    for d in escolhidos:
        if total >= limite_total:
            break
        txt = _ler_doc(d['id'], min(limite_doc, limite_total - total))
        if txt:
            total += len(txt)
            partes.append(f"--- {d.get('tipo')} | {d.get('nome')} | juntado {str(d.get('data_juntada'))[:10]} ---\n{txt}")
    return '\n\n'.join(partes)


def _advbox():
    import advbox_integration as a
    return a


def processo_advbox(numero):
    if not os.getenv('ADVBOX_API_TOKEN'):
        return None, []
    a = _advbox()
    try:
        achados = a.buscar_processo(numero_processo=numero) or []
    except Exception as e:
        log.warning('ADVBOX busca %s: %s', numero, e)
        return None, []
    proc = next((p for p in achados if re.sub(r'\D', '', p.get('process_number') or '')
                 == re.sub(r'\D', '', numero)), None)
    if not proc:
        return None, []
    try:
        hist = a.listar_historico(proc['id']) or []
    except Exception:
        hist = []
    return proc, hist


def area_do_processo(proc, ia_area=''):
    from google_integration import normalizar_area
    area = normalizar_area((proc or {}).get('group') or '') if proc else ''
    if not area and proc:
        area = normalizar_area(proc.get('type') or '')
    return area or normalizar_area(ia_area) or ''


def cliente_do_processo(proc):
    for c in (proc or {}).get('customers', []):
        if 'CONTR' not in (c.get('origin') or '').upper():
            return c.get('name', '')
    return ''


# ============================================================
# 1) DECISAO: como o escritorio trata esta publicacao
# ============================================================

SYSTEM_TRIAGEM = """Voce e a controladoria juridica do escritorio Welington Valois Advogados Associados
(Iuna/ES, Ibatiba/ES, Irupi/ES). Previdenciario ~65% (ajuizado na comarca local por competencia
delegada), criminal ~25%, familia/sucessoes, bancario e civel/consumidor.
Sua tarefa: ler uma publicacao judicial e decidir COMO O ESCRITORIO A TRATA, escolhendo um
tratamento do catalogo do escritorio e o ato a praticar, olhando tambem o historico de tarefas
do proprio processo no ADVBOX (o que a equipe ja fez em situacoes parecidas).
Regras: nunca invente fato, data ou jurisprudencia; em duvida de prazo, escolha o MENOR e
registre em 'conferir'; reu preso, habeas corpus e liminar sao urgentes; o escritorio pode
representar qualquer polo - identifique o cliente pelos advogados constituidos e pelo ADVBOX."""


def montar_prompt_triagem(it, proc, hist, teor, prazos_proc, autos=''):
    catalogo = '\n'.join(f'- {k}: {v["quando"]}' for k, v in R.TRATAMENTOS.items())
    if proc:
        dados_proc = (f"ADVBOX id {proc['id']} | acao: {proc.get('type')} | grupo/area: {proc.get('group')} | "
                      f"fase: {proc.get('stage')} ({proc.get('step')}) | responsavel: {proc.get('responsible')}\n"
                      f"partes: " + '; '.join(f"{c.get('name')} ({c.get('origin')})" for c in proc.get('customers', [])))
    else:
        dados_proc = 'PROCESSO NAO ENCONTRADO NO ADVBOX.'
    historico = '\n'.join(
        f"- {h.get('created_at', '')[:10]} | {h.get('task')} | prazo {h.get('date_deadline') or '-'} | "
        f"{h.get('responsible')} | {(h.get('comments') or '')[:160]}" for h in hist[:25]) or '(sem tarefas)'
    opcoes = '\n'.join(f"- prazo_ato={p.get('prazo_ato')} | {p.get('prazo_dias')} dias | fatal {p.get('data_fatal')} | "
                       f"base {p.get('base_legal', '')}" for p in prazos_proc) or '(nenhuma alem da propria intimacao)'
    datas = {x['id']: x['valor'] for x in it.get('datas', [])}
    return f"""CATALOGO DE TRATAMENTOS DO ESCRITORIO (chave: quando usar)
{catalogo}

PROCESSO
numero {it.get('processo')} | {it.get('tribunal')} | {it.get('orgao')}
{dados_proc}

HISTORICO DE TAREFAS DO PROCESSO NO ADVBOX (mais recentes primeiro)
{historico}

PUBLICACAO
tipo: {it.get('tipo_comunicacao')} / ato: {it.get('tipo_ato')} | disponibilizacao {datas.get('disponibilizacao')} | publicacao {datas.get('publicacao')} | inicio do prazo {datas.get('inicio')}
prazo calculado pelo Sync: {it.get('prazo_ato')} - {it.get('prazo_dias')} dias - fatal {it.get('data_fatal')}
outros prazos do mesmo processo na agenda do Sync:
{opcoes}
resumo do Sync: {it.get('resumo')}

TEOR
{(teor or it.get('texto') or '')[:30000]}

PECAS RECENTES DOS AUTOS (Sync; use para entender o que foi decidido quando a intimacao so diz 'ciencia')
{autos or '(nao disponiveis)'}

Devolva um JSON com exatamente estas chaves:
{{
 "escritorio_atua": true/false,
 "cliente": "nome do cliente do escritorio no processo",
 "polo_cliente": "autor|reu|requerente|requerido|reu (criminal)|vitima|terceiro",
 "area": "PREVIDENCIARIO|CRIMINAL|FAMILIA E SUCESSOES|BANCARIO|CIVEL E CONSUMIDOR",
 "sucessoes_ou_imovel": true/false,
 "resultado_para_cliente": "favoravel|desfavoravel|parcial|neutro",
 "tratamento": "uma chave do catalogo",
 "ato_a_praticar": "frase curta: o que o escritorio deve fazer",
 "prazo_ato_sync": "o prazo_ato do Sync que corresponde ao ato escolhido, ou '' se nenhum",
 "prazo_dias": numero de dias do ato escolhido,
 "contagem": "uteis|corridos",
 "base_legal": "artigo",
 "urgente": true/false,
 "motivo_urgencia": "",
 "instrucoes_peca": "o que a minuta deve enfrentar, ponto a ponto (vazio se nao houver peca)",
 "resumo_para_o_dr": "2 a 3 frases objetivas para o Dr. Welington",
 "explicacao_cliente": "1 a 2 frases em linguagem simples para o cliente",
 "como_o_escritorio_tratou_antes": "o que o historico mostra de parecido (ou 'sem precedente no processo')",
 "conferir": ["pontos que o advogado precisa conferir"]
}}"""


def decidir(it, proc, hist, teor, prazos_proc, autos=''):
    d = ia_backend.gerar_json(montar_prompt_triagem(it, proc, hist, teor, prazos_proc, autos),
                              SYSTEM_TRIAGEM, effort='high')
    if d.get('tratamento') not in R.TRATAMENTOS:
        d.setdefault('conferir', []).append(f"IA sugeriu tratamento fora do catalogo: {d.get('tratamento')}")
        d['tratamento'] = 'manifestacao_simples' if it.get('requer_manifestacao') else 'acompanhar'
    return d


# ============================================================
# 2) PRAZO
# ============================================================

def calcular_prazos(it, dec, prazos_proc, area):
    criminal = area == 'CRIMINAL'
    datas = {x['id']: x['valor'] for x in it.get('datas', [])}
    trat = R.TRATAMENTOS[dec['tratamento']]
    hoje = date.today()
    conferir = []
    fatal = None
    chave = (dec.get('prazo_ato_sync') or '').strip()
    if chave:
        if chave == it.get('prazo_ato'):
            fatal = _d(it.get('data_fatal'))
        else:
            fatal = next((_d(p.get('data_fatal')) for p in prazos_proc if p.get('prazo_ato') == chave), None)
    if not fatal and dec.get('prazo_dias') and datas.get('inicio'):
        ini = _d(datas['inicio'])
        n = int(dec['prazo_dias'])
        fatal = (somar_corridos(ini, n, criminal) if dec.get('contagem') == 'corridos'
                 else somar_uteis(ini, n, criminal))
        conferir.append(f'prazo fatal calculado pela automacao ({n} dias {dec.get("contagem", "uteis")} '
                        f'a partir de {br(ini)}) - sem feriado municipal/estadual')
    if not fatal and it.get('data_fatal'):
        fatal = _d(it['data_fatal'])
    if fatal:
        conferir.append('prazo fatal calculado (Sync/automacao), nao informado pelo tribunal')
    urgente = bool(dec.get('urgente') or trat.get('urgente'))
    if urgente or not fatal:
        interno = hoje
    else:
        interno = max(voltar_uteis(fatal, R.DIAS_UTEIS_PRAZO_INTERNO, criminal), hoje)
    if fatal and fatal < hoje:
        conferir.append('PRAZO FATAL JA PASSOU - verificar se o ato foi praticado')
    return fatal, interno, urgente, conferir


# ============================================================
# 3) MINUTA DA PECA
# ============================================================

def _manual_da_area(area, tratamento):
    nome = R.AGENTE_DA_AREA.get(area)
    if tratamento == 'quesitos':
        nome = 'valois-quesitos'
    arq = RAIZ / '.claude' / 'agents' / f'{nome}.md' if nome else None
    if not arq or not arq.exists():
        return ''
    txt = arq.read_text(encoding='utf-8')
    txt = re.sub(r'^---.*?---\s*', '', txt, flags=re.S)
    return txt[:25000]


def minutar(reg, it, proc, teor):
    import peca_escritorio_engine as E
    trat = R.TRATAMENTOS[reg['tratamento']]
    adv = reg['advogado']
    assinatura = f"{R.NOMES[adv]} - {R.OAB.get(adv, '')}"
    cidade = reg.get('cidade') or '[CIDADE]/ES'
    regras = [
        f'Peca: {trat["peca"]}. Ato a praticar: {reg["ato_a_praticar"]}.',
        f'Cliente do escritorio: {reg["cliente"] or "[PREENCHER]"} ({reg.get("polo_cliente", "")}).',
        f'Prazo fatal: {br(_d(reg["prazo_fatal"]))} [CONFERIR].',
        'Use SOMENTE fatos do teor e dos dados abaixo. Dado ausente -> [PREENCHER] ou [CONFERIR].',
        'NAO cite jurisprudencia de memoria: onde caberia precedente, escreva '
        '[INSERIR JURISPRUDENCIA VERIFICADA - tema: ...]. Lei e sumula so se tiver certeza do texto.',
        f'Local e data: {cidade}, [DATA]. Assinatura: {assinatura}.',
        f'Ultima linha da peca, isolada: PRONTA PARA REVISAO DO(A) {R.NOMES[adv].upper()}',
    ]
    dados = (f"PROCESSO {it.get('processo')} - {it.get('orgao')} ({it.get('tribunal')})\n"
             f"ACAO NO ADVBOX: {(proc or {}).get('type', '[CONFERIR]')}\n"
             f"PARTES: " + '; '.join(f"{c.get('name')} ({c.get('origin')})" for c in (proc or {}).get('customers', [])) +
             f"\n\nO QUE A PECA DEVE ENFRENTAR:\n{reg.get('instrucoes_peca') or '-'}\n\n"
             f"TEOR DA PUBLICACAO:\n{(teor or it.get('texto') or '')[:40000]}\n\n"
             f"PECAS DOS AUTOS (inicial, contestacao, laudo, decisoes - fonte: Sync):\n"
             f"{pecas_dos_autos(it['processo'], 'minuta') or '(autos nao disponiveis: use [PREENCHER])'}")
    manual = _manual_da_area(reg['area'], reg['tratamento'])
    dna = E.carregar_dna_escritorio()
    amostras = E.carregar_amostras_escritorio(max_chars_cada=12000)
    blocos = []
    if manual:
        blocos.append(f'=== MANUAL DA AREA (agente do escritorio) ===\n{manual}\n=== FIM ===')
    if dna:
        blocos.append(f'=== DNA DE ESCRITA DO ESCRITORIO ===\n{dna}\n=== FIM ===')
    for nome, txt in amostras:
        blocos.append(f'=== PECA-MODELO DO ESCRITORIO ({nome}) ===\n{txt}\n=== FIM ===')
    prompt = ('REGRAS DESTA MINUTA:\n- ' + '\n- '.join(regras) + '\n\n' +
              '\n\n'.join(blocos) + f'\n\n=== DADOS DO CASO ===\n{dados}\n=== FIM ===\n\n'
              'Escreva a peca completa, do enderecamento a assinatura, sem comentarios fora da peca.')
    texto = ia_backend.gerar(prompt, E.SYSTEM_PROMPT_ESCRITORIO, effort='high').strip()
    linha_revisao = f'PRONTA PARA REVISAO DO(A) {R.NOMES[adv].upper()}'
    if 'PRONTA PARA REVISAO' not in _sem_acento(texto).upper():
        texto += f'\n\n{linha_revisao}'
    pasta = SAIDA / reg['dia'] / _slug(reg['area'] or 'SEM AREA')
    pasta.mkdir(parents=True, exist_ok=True)
    base = pasta / _slug(f"{reg['cliente'] or it.get('processo')} - {trat['peca']} - {it.get('processo')}", 150)
    base.with_suffix('.txt').write_text(texto, encoding='utf-8')
    try:
        docx = E.formatar_no_timbrado(texto, base.with_suffix('.docx'))
        return str(docx), texto
    except Exception as e:
        log.warning('timbrado falhou (%s); minuta ficou em .txt', e)
        return str(base.with_suffix('.txt')), texto


# ============================================================
# 4) ADVBOX (tarefa) e AGENDA
# ============================================================

def _ja_lancada(hist, tarefa, disponibilizacao):
    """A equipe ja lancou tarefa parecida depois da publicacao? (evita duplicar o controller)"""
    if not tarefa or not disponibilizacao:
        return None
    for h in hist:
        criada = (h.get('created_at') or '')[:10]
        if criada >= disponibilizacao and _sem_acento(h.get('task') or '').upper() == _sem_acento(tarefa).upper():
            return h
    return None


def _id_tarefa(nome):
    if not nome:
        return None
    a = _advbox()
    alvo = _sem_acento(nome).upper()
    for t in a.carregar_settings().get('tasks', []):
        if _sem_acento(t.get('task') or '').upper() == alvo:
            return t['id']
    return a.buscar_tipo_tarefa(nome)


def texto_tarefa(reg):
    linhas = [
        '[TRATAMENTO AUTOMATICO DE PUBLICACAO - VALOIS.IA]',
        f"Publicacao: {reg['tipo_ato']} | {reg['orgao']} | disponibilizada {br(_d(reg['disponibilizacao']))}",
        f"Resumo: {reg['resumo_para_o_dr']}",
        f"Providencia: {reg['ato_a_praticar']}",
        f"PRAZO FATAL: {br(_d(reg['prazo_fatal']))} [CONFERIR]" if reg.get('prazo_fatal') else 'PRAZO FATAL: [CONFERIR]',
        f"Prazo interno: {br(_d(reg['prazo_interno']))}" + (' - URGENTE' if reg.get('urgente') else ''),
    ]
    if reg.get('peca_arquivo'):
        linhas.append(f"Minuta: {Path(reg['peca_arquivo']).name} (SAIDA/publicacoes/{reg['dia']}) - "
                      f"PRONTA PARA REVISAO DO(A) {R.NOMES[reg['advogado']].upper()}. A IA nao protocola.")
    if reg.get('conferir'):
        linhas.append('Conferir: ' + ' | '.join(reg['conferir'])[:600])
    return '\n'.join(linhas)


def lancar_tarefas(reg, hist, executar):
    a = _advbox()
    trat = R.TRATAMENTOS[reg['tratamento']]
    acoes = []
    pessoas = {'advogado': [reg['advogado'], reg['controller']], 'controller': [reg['controller']]}
    principal = trat.get('tarefa')
    if principal and reg.get('advbox_id'):
        quem = pessoas['advogado'] if reg.get('urgente') else pessoas[trat['para']]  # POP 09 4.2
        guests = sorted({R.USUARIOS[p] for p in quem})
        acoes.append(dict(tipo='principal', tarefa=principal, guests=guests,
                          prazo=reg['prazo_interno'], urgente=reg.get('urgente', False),
                          texto=texto_tarefa(reg)))
    if trat.get('suporte') and reg.get('advbox_id'):
        prazo_sup = _d(reg['prazo_interno']) if reg.get('urgente') else \
            somar_uteis(date.today() + timedelta(days=1), R.DIAS_UTEIS_SUPORTE)
        if reg.get('prazo_interno') and prazo_sup > _d(reg['prazo_interno']):
            prazo_sup = _d(reg['prazo_interno'])
        acoes.append(dict(tipo='suporte', tarefa=trat['suporte'], guests=[R.USUARIOS[reg['suporte']]],
                          prazo=str(prazo_sup), urgente=False,
                          texto=('[VALOIS.IA] Falar com o cliente: ' + (reg.get('explicacao_cliente') or '') +
                                 f"\nProcesso {reg['processo']} - {reg['ato_a_praticar']}")))
    for ac in acoes:
        dup = _ja_lancada(hist, ac['tarefa'], reg['disponibilizacao'])
        if dup:
            ac['status'] = f"ja lancada pela equipe em {dup.get('created_at', '')[:10]} ({dup.get('responsible')})"
            continue
        if not executar:
            ac['status'] = 'simulacao (nao lancada)'
            continue
        tid = _id_tarefa(ac['tarefa'])
        if not tid:
            ac['status'] = 'ERRO: tipo de tarefa nao encontrado no ADVBOX'
            continue
        try:
            r = a.criar_publicacao(reg['advbox_id'], tid, ac['guests'], comments=ac['texto'],
                                   from_id=os.getenv('ADVBOX_USER_FROM') or R.USUARIOS['WELINGTON'],
                                   date_deadline=ac['prazo'], urgent=ac['urgente'])
            ac['status'] = 'lancada'
            ac['advbox_post_id'] = (r or {}).get('posts_id') or (r or {}).get('id')
        except Exception as e:
            ac['status'] = f'ERRO ADVBOX: {str(e)[:150]}'
    return acoes


def agendar_google(reg, executar):
    if os.getenv('AGENDA_GOOGLE') != '1':
        return 'Google Agenda nao ativado (prazo na agenda do ADVBOX e do Sync)'
    if not reg.get('prazo_fatal'):
        return 'sem prazo fatal'
    if not executar:
        return 'simulacao'
    try:
        import agenda_google
        ev = agenda_google.criar_evento_dia(
            _d(reg['prazo_fatal']),
            f"PRAZO FATAL - {reg['cliente'] or reg['processo']} - {reg['ato_a_praticar'][:60]}",
            texto_tarefa(reg), chave=f"valois-pub-{reg['id']}")
        return f'Google Agenda: {ev}'
    except Exception as e:
        return f'ERRO Google Agenda: {str(e)[:120]}'


# ============================================================
# PIPELINE
# ============================================================

def tratar(it, prazos, executar, com_peca, dia):
    datas = {x['id']: x['valor'] for x in it.get('datas', [])}
    proc, hist = processo_advbox(it['processo'])
    teor = it.get('texto') or ''
    if teor.endswith('…') or len(teor) < 1500:
        teor = teor_djen(it['processo'], datas.get('disponibilizacao')) or teor
    prazos_proc = [p for p in prazos if p.get('processo') == it['processo']]
    autos_recentes = pecas_dos_autos(it['processo'], 'triagem', datas.get('disponibilizacao'))
    dec = decidir(it, proc, hist, teor, prazos_proc, autos_recentes)
    area = area_do_processo(proc, dec.get('area'))
    papeis = dict(R.AREAS.get(area) or {'advogado': 'WELINGTON', 'controller': 'KAUA', 'suporte': 'KESIA'})
    if area == 'FAMILIA E SUCESSOES' and dec.get('sucessoes_ou_imovel'):
        papeis['controller'] = R.CONTROLLER_SUCESSOES
    fatal, interno, urgente, conf_prazo = calcular_prazos(it, dec, prazos_proc, area)
    orgao = it.get('orgao') or ''
    cidade = next((c for c in ('Iúna', 'Ibatiba', 'Irupi') if _sem_acento(c).lower() in _sem_acento(orgao).lower()), '')
    reg = dict(
        id=it['id'], dia=dia, processado_em=datetime.now().isoformat(timespec='seconds'),
        processo=it['processo'], tribunal=it.get('tribunal'), orgao=orgao, link=it.get('link'),
        tipo_ato=it.get('tipo_ato'), disponibilizacao=datas.get('disponibilizacao'),
        resumo_sync=it.get('resumo'), advbox_id=(proc or {}).get('id'),
        acao=(proc or {}).get('type'), cliente=dec.get('cliente') or cliente_do_processo(proc),
        polo_cliente=dec.get('polo_cliente'), area=area or '[CONFERIR]', cidade=f'{cidade}/ES' if cidade else '',
        tratamento=dec['tratamento'], resultado=dec.get('resultado_para_cliente'),
        ato_a_praticar=dec.get('ato_a_praticar') or '', base_legal=dec.get('base_legal'),
        prazo_fatal=str(fatal) if fatal else '', prazo_interno=str(interno), urgente=urgente,
        motivo_urgencia=dec.get('motivo_urgencia'), resumo_para_o_dr=dec.get('resumo_para_o_dr') or '',
        explicacao_cliente=dec.get('explicacao_cliente') or '',
        como_tratou_antes=dec.get('como_o_escritorio_tratou_antes') or '',
        instrucoes_peca=dec.get('instrucoes_peca') or '',
        advogado=papeis['advogado'], controller=papeis['controller'], suporte=papeis['suporte'],
        conferir=list(dict.fromkeys((dec.get('conferir') or []) + conf_prazo)),
        escritorio_atua=dec.get('escritorio_atua', True), executado=executar,
    )
    if not proc:
        reg['conferir'].insert(0, 'processo NAO encontrado no ADVBOX: cadastrar ou conferir o numero (nenhuma tarefa lancada)')
    if not area:
        reg['conferir'].insert(0, 'area nao identificada - advogado/controller padrao (Dr. Welington/Kaua)')
    if not reg['escritorio_atua']:
        reg['tratamento'] = 'sem_providencia'
    trat = R.TRATAMENTOS[reg['tratamento']]
    if trat.get('peca') and com_peca:
        try:
            reg['peca_arquivo'], _ = minutar(reg, it, proc, teor)
            reg['peca_tipo'] = trat['peca']
        except Exception as e:
            reg['peca_erro'] = str(e)[:200]
            reg['conferir'].append(f'minuta nao gerada: {str(e)[:120]}')
    elif trat.get('peca'):
        reg['peca_tipo'] = trat['peca']
        reg['conferir'].append('minuta nao gerada nesta execucao (--sem-peca)')
    reg['tarefas'] = lancar_tarefas(reg, hist, executar) if trat.get('tarefa') or trat.get('suporte') else []
    reg['agenda'] = agendar_google(reg, executar)
    return reg


def rodar(executar=False, com_peca=True, limite=None, desde=None, reprocessar=None, ao_avancar=None):
    SAIDA.mkdir(parents=True, exist_ok=True)
    est = carregar_estado()
    hoje = date.today()
    dia = str(hoje)
    if not est.get('marco_inicial'):
        est['marco_inicial'] = R.MARCO_INICIAL or dia
    marco = desde or est['marco_inicial']
    execucao = dict(inicio=datetime.now().isoformat(timespec='seconds'), dia=dia,
                    executar=executar, status='processando', tratadas=0, erros=[])
    est['execucoes'].append(execucao)
    salvar_estado(est)

    pendentes = intimacoes_pendentes()
    prazos = prazos_sync()
    est['ultimo_sync'] = dict(pendentes=len(pendentes), prazos=prazos,
                              abertas=[{k: i.get(k) for k in ('id', 'processo', 'orgao', 'tipo_ato', 'data_fatal',
                                                                'resumo', 'link', 'capturado_em', 'prazo_ato')}
                                       for i in pendentes])
    fila = []
    for it in pendentes:
        capt = (it.get('capturado_em') or it.get('data') or '')[:10]
        if reprocessar and str(it['id']) == str(reprocessar):
            fila.append(it)
        elif not reprocessar and capt >= marco:
            feito = est['registros'].get(str(it['id']))
            if not feito or (executar and not feito.get('executado')):  # simulado -> trata de verdade
                fila.append(it)
    fila.sort(key=lambda i: i.get('data_fatal') or '9999')
    if limite:
        fila = fila[:limite]
    log.info('%d pendentes no Sync, %d novas para tratar (marco %s)', len(pendentes), len(fila), marco)
    execucao['fila'] = len(fila)
    salvar_estado(est)
    if ao_avancar:
        ao_avancar(est)

    for n, it in enumerate(fila, 1):
        log.info('[%d/%d] %s %s', n, len(fila), it['processo'], it.get('tipo_ato'))
        try:
            reg = tratar(it, prazos, executar, com_peca, dia)
            est['registros'][str(it['id'])] = reg
            execucao['tratadas'] += 1
        except Exception as e:
            log.exception('falha em %s', it['processo'])
            execucao['erros'].append(f"{it['processo']}: {str(e)[:200]}")
        salvar_estado(est)
        if ao_avancar:
            ao_avancar(est)

    execucao['status'] = 'concluido'
    execucao['fim'] = datetime.now().isoformat(timespec='seconds')
    salvar_estado(est)
    if ao_avancar:
        ao_avancar(est)
    return est


# ============================================================
# CLI
# ============================================================

def _configurar_log():
    (SAIDA / 'logs').mkdir(parents=True, exist_ok=True)
    saidas = [logging.FileHandler(SAIDA / 'logs' / f'{date.today()}.log', encoding='utf-8')]
    if sys.stdout:  # pythonw (agendador) nao tem console
        saidas.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=saidas)


def main():
    if sys.stdout:
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    ap = argparse.ArgumentParser(description='Tratamento automatico de publicacoes (POP 10)')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for nome in ('rodar', 'diario'):
        p = sub.add_parser(nome)
        p.add_argument('--executar', action='store_true', help='lanca as tarefas no ADVBOX')
        p.add_argument('--sem-peca', action='store_true')
        p.add_argument('--limite', type=int)
        p.add_argument('--desde')
        p.add_argument('--reprocessar')
        p.add_argument('--abrir', action='store_true', help='abre o painel no navegador')
    p = sub.add_parser('painel')
    p.add_argument('--abrir', action='store_true')
    sub.add_parser('autorizar-agenda')
    args = ap.parse_args()
    _configurar_log()
    import painel_dr_welington as P

    if args.cmd == 'autorizar-agenda':
        import agenda_google
        print(agenda_google.autorizar())
        return
    if args.cmd == 'painel':
        caminho = P.gerar_painel(carregar_estado())
        print(caminho)
        if args.abrir:
            os.startfile(caminho)
        return

    est = carregar_estado()
    hoje = str(date.today())
    ja_rodou = any(e.get('dia') == hoje and e.get('status') == 'concluido' and e.get('executar') == args.executar
                   for e in est.get('execucoes', []))
    if args.cmd == 'diario' and ja_rodou:
        caminho = P.gerar_painel(est)
        if args.abrir:
            os.startfile(caminho)
        return
    if TRAVA.exists() and time.time() - TRAVA.stat().st_mtime < 3 * 3600:
        log.info('ja existe uma execucao em andamento; so abrindo o painel')
        if args.abrir:
            os.startfile(P.caminho_painel())
        return
    SAIDA.mkdir(parents=True, exist_ok=True)
    TRAVA.write_text(str(os.getpid()))
    aberto = [False]

    def atualizar(e):
        caminho = P.gerar_painel(e)
        if args.abrir and not aberto[0]:
            os.startfile(caminho)
            aberto[0] = True
    try:
        P.importar_validacoes(est)
        salvar_estado(est)
        rodar(executar=args.executar, com_peca=not args.sem_peca, limite=args.limite,
              desde=args.desde, reprocessar=args.reprocessar, ao_avancar=atualizar)
    except Exception as e:
        log.exception('execucao falhou')
        est = carregar_estado()
        if est.get('execucoes'):
            est['execucoes'][-1].update(status='falhou', erros=est['execucoes'][-1].get('erros', []) + [str(e)[:300]])
            salvar_estado(est)
        atualizar(est)
    finally:
        TRAVA.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
