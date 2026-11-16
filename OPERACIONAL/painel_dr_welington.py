"""
Painel diario do Dr. Welington - abre todo dia as 7h (e ao entrar no notebook).

Mostra tudo o que a automacao tratou: publicacoes, decisao de tratamento, prazos, minutas
no timbrado, tarefas lancadas no ADVBOX, o que precisa da decisao dele e as demais entregas
do dia (arquivos novos em SAIDA/). Cada item tem "Validado" / "Corrigir" + observacao,
guardados no navegador; o botao "Baixar validacao" gera um CSV em Downloads que a execucao
seguinte importa (fica registrado no estado).

Arquivo: SAIDA/painel/painel_AAAA-MM-DD.html (+ SAIDA/painel/HOJE.html, sempre o ultimo).
"""
import csv
import glob
import html
import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / 'SAIDA' / 'painel'

import importlib.util
_spec = importlib.util.spec_from_file_location('regras_publicacoes', RAIZ / 'config' / 'regras_publicacoes.py')
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)

DIAS_SEMANA = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']
MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
         'outubro', 'novembro', 'dezembro']
ROTULO_TRAT = {
    'ciencia_favoravel': 'Ciência (favorável)', 'acompanhar': 'Acompanhar', 'embargos_declaracao': 'Embargos de declaração',
    'apelacao': 'Apelação / recurso inominado', 'contrarrazoes': 'Contrarrazões', 'agravo_instrumento': 'Agravo de instrumento',
    'replica': 'Réplica', 'manifestacao_laudo': 'Manifestação sobre laudo', 'manifestacao_simples': 'Manifestação simples',
    'manifestacao_complexa': 'Manifestação complexa', 'emenda_inicial': 'Emenda à inicial', 'quesitos': 'Quesitos',
    'pericia_designada': 'Perícia designada', 'audiencia_designada': 'Audiência designada',
    'cumprimento_sentenca': 'Cumprimento de sentença', 'conferir_calculo': 'Conferir cálculo',
    'implantacao_beneficio': 'Implantação de benefício', 'levantamento_valores': 'Levantamento de valores',
    'resposta_acusacao': 'Resposta à acusação', 'alegacoes_finais': 'Alegações finais',
    'revogacao_prisao': 'Revogação da prisão', 'habeas_corpus': 'Habeas corpus',
    'recurso_tribunal_superior': 'Avaliar recurso a tribunal superior', 'sem_providencia': 'Sem providência',
}


def e(t):
    return html.escape(str(t if t is not None else ''))


def _br(txt):
    try:
        return datetime.strptime(str(txt)[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return '-'


def _dias(txt):
    try:
        return (datetime.strptime(str(txt)[:10], '%Y-%m-%d').date() - date.today()).days
    except ValueError:
        return None


def caminho_painel(dia=None):
    return PASTA / f'painel_{dia or date.today()}.html'


# ------------------------------------------------------------------
# validacao (CSV baixado do painel -> estado)
# ------------------------------------------------------------------

def importar_validacoes(est):
    pasta = Path(os.path.expanduser('~')) / 'Downloads'
    for arq in sorted(glob.glob(str(pasta / 'validacao_painel_*.csv'))):
        try:
            with open(arq, encoding='utf-8-sig') as f:
                for linha in csv.DictReader(f, delimiter=';'):
                    reg = est.get('registros', {}).get(linha.get('id', ''))
                    if reg and linha.get('situacao'):
                        reg['validacao'] = dict(situacao=linha['situacao'], obs=linha.get('observacao', ''),
                                                arquivo=Path(arq).name)
        except Exception:
            continue


# ------------------------------------------------------------------
# blocos
# ------------------------------------------------------------------

def _outras_entregas():
    """Arquivos gerados em SAIDA/ nas ultimas 36h (fora o proprio painel/estado)."""
    limite = datetime.now().timestamp() - 36 * 3600
    saida = RAIZ / 'SAIDA'
    itens = []
    if not saida.exists():
        return itens
    for p in saida.rglob('*'):
        if not p.is_file() or p.suffix.lower() in ('.json', '.log', '.tmp') or p.name.startswith('.'):
            continue
        rel = p.relative_to(saida).parts
        if rel[0] in ('painel', 'migracao_infinitum') or (rel[0] == 'publicacoes'):
            continue
        if p.stat().st_mtime >= limite:
            itens.append(p)
    return sorted(itens, key=lambda p: p.stat().st_mtime, reverse=True)[:60]


def _status_tarefa(t):
    s = t.get('status', '')
    cls = 'ok' if s == 'lancada' else ('aviso' if 'ja lancada' in s or 'simula' in s else 'erro')
    rot = {'lancada': 'Lançada no ADVBOX'}.get(s, s)
    return (f'<li><span class="pill {cls}">{e(rot)}</span> {e(t["tarefa"])} '
            f'<span class="mut">→ prazo {_br(t.get("prazo"))}'
            + (f' · post {e(t.get("advbox_post_id"))}' if t.get('advbox_post_id') else '') + '</span></li>')


def _cartao(reg):
    adv = R.NOMES.get(reg.get('advogado'), reg.get('advogado'))
    ctl = R.NOMES.get(reg.get('controller'), reg.get('controller'))
    dias = _dias(reg.get('prazo_fatal'))
    if dias is None:
        prazo_cls, prazo_txt = 'aviso', 'sem prazo fatal [CONFERIR]'
    else:
        prazo_cls = 'erro' if dias <= 2 else ('aviso' if dias <= 5 else 'ok')
        prazo_txt = f'{_br(reg["prazo_fatal"])} ({"vencido" if dias < 0 else "hoje" if dias == 0 else f"em {dias} dia(s)"})'
    peca = ''
    if reg.get('peca_arquivo'):
        uri = Path(reg['peca_arquivo']).as_uri()
        peca = (f'<div class="peca">📄 <a href="{e(uri)}">{e(Path(reg["peca_arquivo"]).name)}</a>'
                f'<span class="mut"> — minuta no timbrado, PRONTA PARA REVISÃO de {e(adv)}</span></div>')
    elif reg.get('peca_tipo'):
        peca = f'<div class="peca mut">Minuta prevista ({e(reg["peca_tipo"])}) não gerada: {e(reg.get("peca_erro") or "ver conferir")}</div>'
    tarefas = ''.join(_status_tarefa(t) for t in reg.get('tarefas', [])) or '<li class="mut">Nenhuma tarefa (sem providência ou processo fora do ADVBOX)</li>'
    conferir = ''.join(f'<li>{e(c)}</li>' for c in reg.get('conferir', []))
    val = reg.get('validacao') or {}
    selo = f'<span class="pill ok">Validado pelo senhor</span>' if val.get('situacao') == 'VALIDADO' else (
        f'<span class="pill erro">Correção pedida: {e(val.get("obs"))}</span>' if val.get('situacao') else '')
    return f'''
<article class="cartao{' urgente' if reg.get('urgente') else ''}" data-id="{e(reg['id'])}">
  <header>
    <div>
      <div class="tit">{e(reg.get('cliente') or '[cliente não identificado]')} <span class="mut">· {e(reg.get('area'))}</span></div>
      <div class="mut">{e(reg['processo'])} · {e(reg.get('orgao'))} · {e(reg.get('acao') or '')}</div>
    </div>
    <div class="dir">
      {'<span class="pill erro">URGENTE</span>' if reg.get('urgente') else ''}
      <span class="pill neutro">{e(ROTULO_TRAT.get(reg['tratamento'], reg['tratamento']))}</span>
      {selo}
    </div>
  </header>
  <p>{e(reg.get('resumo_para_o_dr'))}</p>
  <div class="grade">
    <div><b>Providência</b><br>{e(reg.get('ato_a_praticar'))}<br><span class="mut">{e(reg.get('base_legal') or '')}</span></div>
    <div><b>Prazo fatal</b><br><span class="pill {prazo_cls}">{e(prazo_txt)}</span><br><span class="mut">interno: {_br(reg.get('prazo_interno'))}</span></div>
    <div><b>Responsáveis</b><br>{e(adv)} (peça)<br><span class="mut">controller: {e(ctl)}</span></div>
  </div>
  <div class="mut pequeno"><b>Como o escritório costuma tratar:</b> {e(reg.get('como_tratou_antes'))}</div>
  {peca}
  <ul class="tarefas">{tarefas}</ul>
  {f'<details open><summary>Conferir ({len(reg.get("conferir", []))})</summary><ul>{conferir}</ul></details>' if conferir else ''}
  <div class="mut pequeno">Agenda: {e(reg.get('agenda'))} · {'<a href="' + e(reg['link']) + '">abrir publicação no tribunal</a>' if reg.get('link') else ''}</div>
  <div class="validar">
    <button class="b-ok" onclick="marcar('{e(reg['id'])}','VALIDADO')">✔ Validado</button>
    <button class="b-cor" onclick="marcar('{e(reg['id'])}','CORRIGIR')">✎ Corrigir</button>
    <input placeholder="Observação do senhor (o que corrigir)" oninput="obs('{e(reg['id'])}',this.value)">
    <span class="estado-val"></span>
  </div>
</article>'''


def gerar_painel(est):
    PASTA.mkdir(parents=True, exist_ok=True)
    hoje = date.today()
    dia = str(hoje)
    execs = [x for x in est.get('execucoes', []) if x.get('dia') == dia]
    ult = execs[-1] if execs else {}
    processando = ult.get('status') == 'processando'
    regs = [r for r in est.get('registros', {}).values() if r.get('dia') == dia]
    regs.sort(key=lambda r: (not r.get('urgente'), r.get('prazo_fatal') or '9999'))
    pecas = [r for r in regs if r.get('peca_arquivo')]
    tarefas = [t for r in regs for t in r.get('tarefas', [])]
    lancadas = [t for t in tarefas if t.get('status') == 'lancada']
    atencao = [r for r in regs if r.get('urgente') or any('NAO encontrado' in c or 'JA PASSOU' in c or 'area nao' in c
                                                          for c in r.get('conferir', []))
               or any(t.get('status', '').startswith('ERRO') for t in r.get('tarefas', []))]
    sync = est.get('ultimo_sync', {})
    prazos = sorted([p for p in sync.get('prazos', []) if (p.get('dias_restantes') or 0) <= 7],
                    key=lambda p: p.get('data_fatal') or '')
    tratados_ids = set(est.get('registros', {}).keys())
    backlog = [a for a in sync.get('abertas', []) if str(a['id']) not in tratados_ids]
    pendentes_val = [r for r in est.get('registros', {}).values()
                     if r.get('dia') != dia and not r.get('validacao') and r.get('dia', '') >= str(hoje - timedelta(days=7))]
    entregas = _outras_entregas()

    hora = datetime.now().hour
    saud = 'Bom dia' if hora < 12 else ('Boa tarde' if hora < 18 else 'Boa noite')
    data_ext = f'{DIAS_SEMANA[hoje.weekday()]}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}'
    modo = ('' if not ult else
            ('<span class="pill ok">Tarefas lançadas no ADVBOX</span>' if ult.get('executar')
             else '<span class="pill aviso">SIMULAÇÃO: nada foi lançado no ADVBOX</span>'))
    if processando:
        status = f'<div class="faixa aviso">⏳ Estou tratando as publicações de hoje, senhor ({ult.get("tratadas", 0)} de {ult.get("fila", "?")}). Esta página se atualiza sozinha.</div>'
    elif ult.get('status') == 'falhou':
        status = f'<div class="faixa erro">A execução de hoje falhou, senhor: {e("; ".join(ult.get("erros", [])))}. Verifique SAIDA/publicacoes/logs.</div>'
    elif not ult:
        status = '<div class="faixa aviso">A rotina de hoje ainda não rodou, senhor.</div>'
    else:
        status = (f'<div class="faixa ok">Rotina concluída às {e(ult.get("fim", "")[11:16])}. '
                  f'{len(regs)} publicação(ões) nova(s) tratada(s) hoje.'
                  + (f' Erros: {e("; ".join(ult.get("erros")))}' if ult.get('erros') else '') + '</div>')

    def tile(n, rot, cls=''):
        return f'<div class="tile {cls}"><div class="n">{n}</div><div class="r">{rot}</div></div>'

    tiles = (tile(len(regs), 'publicações tratadas hoje') + tile(len(pecas), 'minutas no timbrado') +
             tile(len(lancadas), 'tarefas lançadas no ADVBOX') +
             tile(len(prazos), 'prazos fatais em até 7 dias', 'aviso' if prazos else '') +
             tile(len(atencao), 'precisam da decisão do senhor', 'erro' if atencao else ''))

    bloco_atencao = ''.join(
        f'<li><a href="#c{e(r["id"])}">{e(r.get("cliente") or r["processo"])}</a> — '
        f'{"URGENTE: " + e(r.get("motivo_urgencia") or r.get("ato_a_praticar")) if r.get("urgente") else e("; ".join(r.get("conferir", [])[:2]))}</li>'
        for r in atencao) or '<li class="mut">Nada que dependa do senhor agora.</li>'
    cartoes = ''.join(f'<div id="c{e(r["id"])}"></div>' + _cartao(r) for r in regs) or \
        '<p class="mut">Nenhuma publicação nova desde a última rotina.</p>'
    linhas_prazo = ''.join(
        f'<tr><td><span class="pill {"erro" if (p.get("dias_restantes") or 0) <= 1 else "aviso" if (p.get("dias_restantes") or 0) <= 3 else "ok"}">'
        f'{_br(p.get("data_fatal"))}</span></td><td>{e(p.get("dias_restantes"))}</td><td>{e(p.get("processo"))}</td>'
        f'<td>{e(p.get("orgao"))}</td><td>{e((p.get("costura") or {}).get("prazos", [{}])[0].get("rotulo") or p.get("prazo_ato"))}</td></tr>'
        for p in prazos) or '<tr><td colspan="5" class="mut">Sem prazo fatal nos próximos 7 dias na agenda do Sync.</td></tr>'
    linhas_backlog = ''.join(
        f'<tr><td>{_br(a.get("data_fatal"))}</td><td>{e(a.get("processo"))}</td><td>{e(a.get("orgao"))}</td>'
        f'<td>{e(a.get("tipo_ato"))}</td><td class="pequeno">{e((a.get("resumo") or "")[:180])}</td></tr>'
        for a in sorted(backlog, key=lambda a: a.get('data_fatal') or '9999')[:60])
    linhas_entregas = ''.join(
        f'<li><a href="{e(p.as_uri())}">{e(p.name)}</a> <span class="mut">· {e(p.parent.relative_to(RAIZ / "SAIDA"))} · '
        f'{datetime.fromtimestamp(p.stat().st_mtime).strftime("%d/%m %H:%M")}</span></li>' for p in entregas) or \
        '<li class="mut">Nenhum outro arquivo gerado nas últimas 36 horas.</li>'
    lista_pend_val = ''.join(f'<li>{_br(r["dia"])} — {e(r.get("cliente") or r["processo"])}: {e(ROTULO_TRAT.get(r["tratamento"]))}</li>'
                             for r in pendentes_val[:30])

    pagina = f'''<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{'<meta http-equiv="refresh" content="20">' if processando else ''}
<title>Painel do Dr. Welington — {hoje.strftime('%d/%m/%Y')}</title>
<style>
:root {{ --azul:#14294b; --ouro:#b08d3c; --fundo:#f5f3ee; --card:#fff; --txt:#1d1d1f; --mut:#6b6b70;
        --ok:#1f7a4d; --okf:#e5f3eb; --av:#8a5a00; --avf:#fbf1dc; --er:#a1262b; --erf:#fbe6e6; }}
* {{ box-sizing:border-box }}
body {{ margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:var(--fundo); color:var(--txt); font-size:15px }}
.topo {{ background:var(--azul); color:#fff; padding:22px 32px; border-bottom:4px solid var(--ouro) }}
.topo h1 {{ margin:0; font-size:24px; font-weight:600 }} .topo .sub {{ opacity:.85; margin-top:4px }}
main {{ max-width:1180px; margin:0 auto; padding:20px 24px 60px }}
h2 {{ color:var(--azul); font-size:18px; margin:30px 0 10px; border-bottom:1px solid #ddd6c6; padding-bottom:6px }}
.faixa {{ padding:12px 16px; border-radius:8px; margin:14px 0 }} .faixa.ok {{ background:var(--okf) }}
.faixa.aviso {{ background:var(--avf) }} .faixa.erro {{ background:var(--erf) }}
.tiles {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px }}
.tile {{ background:var(--card); border-radius:10px; padding:14px 16px; border-top:3px solid var(--azul) }}
.tile.aviso {{ border-top-color:var(--ouro) }} .tile.erro {{ border-top-color:var(--er) }}
.tile .n {{ font-size:30px; font-weight:700; color:var(--azul) }} .tile .r {{ color:var(--mut); font-size:13px }}
.cartao {{ background:var(--card); border-radius:10px; padding:16px 18px; margin:12px 0; border-left:4px solid var(--azul) }}
.cartao.urgente {{ border-left-color:var(--er) }}
.cartao header {{ display:flex; justify-content:space-between; gap:12px }} .tit {{ font-weight:600; font-size:16px }}
.dir {{ text-align:right }} .grade {{ display:grid; grid-template-columns:2fr 1fr 1fr; gap:14px; margin:10px 0 }}
.mut {{ color:var(--mut) }} .pequeno {{ font-size:13px }}
.pill {{ display:inline-block; padding:2px 9px; border-radius:20px; font-size:12.5px; margin:2px 0 }}
.pill.ok {{ background:var(--okf); color:var(--ok) }} .pill.aviso {{ background:var(--avf); color:var(--av) }}
.pill.erro {{ background:var(--erf); color:var(--er) }} .pill.neutro {{ background:#e9edf4; color:var(--azul) }}
.peca {{ background:#f8f6f0; padding:8px 12px; border-radius:6px; margin:8px 0 }}
ul.tarefas {{ margin:8px 0; padding-left:18px }} details {{ margin:6px 0 }} summary {{ cursor:pointer; color:var(--av) }}
.validar {{ display:flex; gap:8px; align-items:center; margin-top:10px; border-top:1px dashed #e2ddd0; padding-top:10px }}
.validar input {{ flex:1; padding:6px 8px; border:1px solid #d6d0c2; border-radius:6px; font:inherit }}
button {{ font:inherit; border:0; border-radius:6px; padding:6px 12px; cursor:pointer }}
.b-ok {{ background:var(--okf); color:var(--ok) }} .b-cor {{ background:var(--avf); color:var(--av) }}
.b-csv {{ background:var(--azul); color:#fff }}
.cartao.val-VALIDADO {{ opacity:.7 }} .cartao.val-CORRIGIR {{ border-left-color:var(--ouro) }}
table {{ width:100%; border-collapse:collapse; background:var(--card); border-radius:10px; overflow:hidden }}
th, td {{ text-align:left; padding:7px 10px; border-bottom:1px solid #eee9de; vertical-align:top }}
th {{ background:#efebe1; color:var(--azul); font-weight:600; font-size:13px }}
a {{ color:var(--azul) }} .regra {{ font-size:13px; color:var(--mut); margin-top:30px }}
@media (max-width:900px) {{ .tiles {{ grid-template-columns:repeat(2,1fr) }} .grade {{ grid-template-columns:1fr }} }}
</style></head><body>
<div class="topo">
  <h1>{saud}, senhor.</h1>
  <div class="sub">Painel do Dr. Welington Dias Valois · {e(data_ext)} · Welington Valois Advogados Associados</div>
</div>
<main>
{status}
<div>{modo}</div>
<div class="tiles">{tiles}</div>

<h2>O que precisa da decisão do senhor</h2>
<ul>{bloco_atencao}</ul>

<h2>Publicações tratadas hoje <span class="mut pequeno">(ordem: urgência e prazo)</span></h2>
<p><button class="b-csv" onclick="baixar()">Baixar validação (CSV)</button>
<span class="mut pequeno"> Marque cada item; o arquivo vai para Downloads e a rotina de amanhã registra a validação do senhor.</span></p>
{cartoes}

<h2>Prazos fatais nos próximos 7 dias (agenda do Sync)</h2>
<table><tr><th>Fatal</th><th>Dias</th><th>Processo</th><th>Órgão</th><th>Ato</th></tr>{linhas_prazo}</table>

{f"<h2>Ainda sem validação do senhor (últimos 7 dias)</h2><ul>{lista_pend_val}</ul>" if lista_pend_val else ""}

<h2>Outras entregas para o senhor e para o escritório (últimas 36h)</h2>
<ul>{linhas_entregas}</ul>

{f"""<h2>Pendentes no Sync anteriores ao início da automação ({len(backlog)})</h2>
<p class="mut pequeno">Capturadas antes de {_br(est.get('marco_inicial'))}: não foram tratadas automaticamente. Pelo POP 09 o controller da área lança no ADVBOX.</p>
<table><tr><th>Fatal</th><th>Processo</th><th>Órgão</th><th>Ato</th><th>Resumo</th></tr>{linhas_backlog}</table>""" if backlog else ""}

<p class="regra">Regra de ouro: a IA nunca protocola. Toda minuta acima é para revisão do advogado da área antes de qualquer protocolo.
Prazos são calculados (Sync/automação) e vão marcados [CONFERIR]. Nenhuma intimação é marcada como tratada no Sync (POP 09).
Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}.</p>
</main>
<script>
const CHAVE = 'painel-valois-{dia}';
const val = JSON.parse(localStorage.getItem(CHAVE) || '{{}}');
function salvar() {{ localStorage.setItem(CHAVE, JSON.stringify(val)); pintar(); }}
function marcar(id, s) {{ val[id] = Object.assign(val[id] || {{}}, {{situacao: s}}); salvar(); }}
function obs(id, t) {{ val[id] = Object.assign(val[id] || {{}}, {{obs: t}}); localStorage.setItem(CHAVE, JSON.stringify(val)); }}
function pintar() {{
  document.querySelectorAll('.cartao').forEach(c => {{
    const v = val[c.dataset.id] || {{}};
    c.classList.remove('val-VALIDADO', 'val-CORRIGIR');
    if (v.situacao) c.classList.add('val-' + v.situacao);
    c.querySelector('.estado-val').textContent = v.situacao === 'VALIDADO' ? 'validado' : (v.situacao === 'CORRIGIR' ? 'correção pedida' : '');
    const inp = c.querySelector('.validar input'); if (v.obs && !inp.value) inp.value = v.obs;
  }});
}}
function baixar() {{
  let csv = 'id;situacao;observacao\\n';
  for (const [id, v] of Object.entries(val)) csv += id + ';' + (v.situacao || '') + ';' + (v.obs || '').replace(/[;\\n]/g, ' ') + '\\n';
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(['\\ufeff' + csv], {{type: 'text/csv'}}));
  a.download = 'validacao_painel_{dia}.csv'; a.click();
}}
pintar();
</script>
</body></html>'''
    destino = caminho_painel(dia)
    tmp = destino.with_suffix('.tmp')
    tmp.write_text(pagina, encoding='utf-8')
    tmp.replace(destino)
    shutil.copyfile(destino, PASTA / 'HOJE.html')
    return str(destino)
