"""
Calculo da folha de pagamento - Welington Valois Advogados Associados.

Aplica a regra geral de remuneracao do escritorio (config/regras_financeiras.py):

    o que cada colaborador recebe = salario base + participacao da sua area

A participacao incide sobre o resultado da area no mes de referencia, apurado no
ADVBOX pelos valores EFETIVAMENTE RECEBIDOS E PAGOS (date_payment), nunca pelos
previstos. A area de cada receita sai da propria categoria do ADVBOX.

NAO LANCA NADA. Gera relatorio e CSV para o Dr. Welington aprovar. O lancamento
no ADVBOX exige autorizacao expressa dele para aquele lancamento especifico.

Uso:
    python FINANCEIRO/calcular_folha.py 09/2026
    python FINANCEIRO/calcular_folha.py 09/2026 --base RECEITA
    python FINANCEIRO/calcular_folha.py 09/2026 --comparar
"""
import argparse
import calendar
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv(RAIZ / 'config' / '.env')

from config import equipe, regras_financeiras as regras          # noqa: E402
from INTEGRACOES import advbox_integration as adv                 # noqa: E402

SAIDA = RAIZ / 'SAIDA' / 'folha'


def _intervalo(mes, ano):
    ultimo = calendar.monthrange(ano, mes)[1]
    return f'{ano:04d}-{mes:02d}-01', f'{ano:04d}-{mes:02d}-{ultimo:02d}'


def apurar(mes, ano):
    """Receita por area, despesas e margem do mes, pelo que foi pago/recebido."""
    inicio, fim = _intervalo(mes, ano)
    transacoes = adv.listar_transacoes({
        'date_payment_start': inicio, 'date_payment_end': fim,
    })
    # A API filtra por intervalo, mas conferimos o mes para nao contar vizinho.
    prefixo = f'{ano:04d}-{mes:02d}'
    transacoes = [t for t in transacoes
                  if (t.get('date_payment') or '').startswith(prefixo)]

    por_area, nao_identificadas = regras.receita_por_area(transacoes)
    receita = sum(por_area.values())
    despesa = sum(t.get('amount') or 0.0 for t in transacoes
                  if t.get('entry_type') == 'expense')
    margem = regras.margem_do_escritorio(receita, despesa)
    return {
        'por_area': por_area, 'receita': receita, 'despesa': despesa,
        'margem': margem, 'nao_identificadas': nao_identificadas,
    }


def calcular(mes, ano):
    ap = apurar(mes, ano)
    participacoes, areas_sem_regra = regras.participacoes_por_area(
        ap['por_area'], ap['margem'])
    linhas = regras.folha_por_pessoa(equipe.colaboradores_na_folha(), participacoes)
    ap['participacoes'] = participacoes
    ap['areas_sem_regra'] = areas_sem_regra
    ap['linhas'] = linhas
    return ap


def imprimir(ap, mes, ano):
    print()
    print('=' * 86)
    print(f'  FOLHA - base no resultado de {mes:02d}/{ano}   '
          f'(participacao sobre {regras.BASE_PARTICIPACAO})')
    print('=' * 86)
    print(f'  Receita recebida .... R$ {ap["receita"]:>12,.2f}')
    print(f'  Despesas pagas ...... R$ {ap["despesa"]:>12,.2f}')
    print(f'  Margem aplicada ..... {ap["margem"] * 100:>12.2f}%')
    print()
    print('  Receita por area:')
    for area in sorted(ap['por_area'], key=lambda a: -ap['por_area'][a]):
        pct = regras.PARTICIPACAO_POR_AREA.get(area)
        rotulo = f'{pct * 100:.0f}%' if pct is not None else 'SEM REGRA'
        print(f'    {area:<24} R$ {ap["por_area"][area]:>11,.2f}   {rotulo:>10}')
    print()
    print(f'  {"PESSOA":<34}{"BASE":>11}{"PARTICIP.":>13}{"TOTAL":>13}')
    for l in ap['linhas']:
        print(f'  {l["nome"]:<34}{l["salario_base"]:>11,.2f}'
              f'{l["participacao"]:>13,.2f}{l["total"]:>13,.2f}')
    tb = sum(l['salario_base'] for l in ap['linhas'])
    tp = sum(l['participacao'] for l in ap['linhas'])
    print(f'  {"TOTAL":<34}{tb:>11,.2f}{tp:>13,.2f}{tb + tp:>13,.2f}')
    print()
    if ap['areas_sem_regra']:
        print('  ATENCAO - areas com receita e SEM percentual definido:')
        for area, valor in ap['areas_sem_regra']:
            print(f'    {area:<24} R$ {valor:>11,.2f}  -> ninguem recebe sobre isso')
        print()
    if ap['nao_identificadas']:
        print('  ATENCAO - categorias de receita sem area identificada:')
        for cat in ap['nao_identificadas']:
            print(f'    {cat}')
        print()
    print('  Valores em REMUNERACAO BRUTA. INSS e FGTS sao lancados a parte.')
    print('  NADA FOI LANCADO NO ADVBOX - depende de autorizacao expressa.')
    print()


def gravar_csv(ap, mes, ano):
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f'folha_base_{ano:04d}-{mes:02d}.csv'
    with open(destino, 'w', newline='', encoding='utf-8-sig') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(['pessoa', 'area', 'responsavel_area', 'salario_base',
                    'participacao', 'total_bruto', 'aprovado_por'])
        for l in ap['linhas']:
            w.writerow([l['nome'], l['area'] or '', 'SIM' if l['responsavel'] else 'NAO',
                        f'{l["salario_base"]:.2f}', f'{l["participacao"]:.2f}',
                        f'{l["total"]:.2f}', ''])
    print(f'  CSV para aprovacao: {destino}')
    return destino


def main():
    p = argparse.ArgumentParser(description='Calcula a folha pela regra do escritorio.')
    p.add_argument('competencia', help='mes de referencia do resultado, MM/AAAA')
    p.add_argument('--base', choices=['LUCRO', 'RECEITA'],
                   help='sobrepoe BASE_PARTICIPACAO so nesta execucao')
    p.add_argument('--comparar', action='store_true',
                   help='mostra o total nas duas bases, lado a lado')
    p.add_argument('--sem-csv', action='store_true')
    args = p.parse_args()

    try:
        mes, ano = (int(x) for x in args.competencia.split('/'))
    except ValueError:
        p.error('competencia deve ser MM/AAAA, ex.: 09/2026')

    if args.base:
        regras.BASE_PARTICIPACAO = args.base

    if args.comparar:
        for base in ('LUCRO', 'RECEITA'):
            regras.BASE_PARTICIPACAO = base
            ap = calcular(mes, ano)
            total = sum(l['total'] for l in ap['linhas'])
            print(f'  base {base:<8} -> folha R$ {total:,.2f}')
        return

    ap = calcular(mes, ano)
    imprimir(ap, mes, ano)
    if not args.sem_csv:
        gravar_csv(ap, mes, ano)


if __name__ == '__main__':
    main()
