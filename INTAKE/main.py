"""
Contratacao automatizada - Welington Valois Advogados Associados.

Duas etapas, com a revisao do advogado no meio (regra de ouro: a IA prepara, o humano
confere e so entao algo sai para o cliente):

  1. GERAR  - a IA le a reuniao e os documentos, monta a ficha (documento guia), o contrato,
              a procuracao e a declaracao no timbrado, cria a pasta do cliente no Drive
              (AREA > NOME > 3 subpastas) e registra o caso no indice de revisao.
  2. ENVIAR - depois que o advogado revisou (coluna revisado_por + enviar=SIM no indice),
              baixa a versao revisada do Drive, converte em PDF, cria os documentos no
              ZapSign, manda os links ao cliente pelo WhatsApp (Evolution) e cadastra
              cliente/processo no ADVBOX.

Uso:
  python INTAKE/main.py gerar TRANSCRICAO.pdf CNH.pdf CADASTRO.txt --area PREVIDENCIARIO
  python INTAKE/main.py gerar ... --area CRIMINAL --unidade IBATIBA
  python INTAKE/main.py gerar --exemplo                 # caso ficticio, sem IA e sem Drive
  python INTAKE/main.py advbox 123.456.789-00           # cliente JA cadastrado no ADVBOX
  python INTAKE/main.py advbox "MARIA" --area PREVIDENCIARIO --acao "Salario-maternidade rural"
  python INTAKE/main.py status
  python INTAKE/main.py enviar --simular                # confere tudo, nao manda nada
  python INTAKE/main.py enviar                          # envia o que foi revisado
  python INTAKE/main.py enviar --so "MARIA"

Indice de revisao: SAIDA/intake/INDICE_CONTRATACOES.csv (abre no Excel; separador ';').
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'INTAKE'))
sys.path.insert(0, os.path.join(ROOT, 'INTEGRACOES'))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, 'config', '.env'))

import contratacao  # noqa: E402
from google_integration import AREAS, normalizar_area  # noqa: E402

SAIDA = os.path.join(ROOT, 'SAIDA', 'intake')
INDICE = os.path.join(SAIDA, 'INDICE_CONTRATACOES.csv')
COLUNAS = ['caso', 'data', 'cliente', 'area', 'responsavel', 'telefone', 'modelo',
           'pendencias', 'pasta_drive', 'revisado_por', 'tipo_advbox', 'enviar', 'status',
           'obs']
SIM = ('SIM', 'S', 'X')


# ============================================================
# UTILITARIOS
# ============================================================

def _slug(texto):
    t = unicodedata.normalize('NFD', texto or '')
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^A-Za-z0-9]+', '_', t).strip('_').upper()[:60] or 'CLIENTE'


def _ler_indice():
    if not os.path.exists(INDICE):
        return []
    with open(INDICE, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f, delimiter=';'))


def _gravar_indice(linhas):
    os.makedirs(SAIDA, exist_ok=True)
    try:
        with open(INDICE, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=';', extrasaction='ignore')
            w.writeheader()
            w.writerows(linhas)
    except PermissionError:
        print(f'\nERRO: nao consegui gravar {INDICE}.')
        print('Feche o arquivo no Excel e rode de novo.')
        sys.exit(1)


def _atualizar_indice(caso, **campos):
    linhas = _ler_indice()
    for linha in linhas:
        if linha['caso'] == caso:
            linha.update(campos)
            break
    else:
        linhas.append({c: '' for c in COLUNAS} | {'caso': caso} | campos)
    _gravar_indice(linhas)


def _pasta_caso(caso):
    return os.path.join(SAIDA, caso)


def _ler_caso(caso):
    with open(os.path.join(_pasta_caso(caso), 'caso.json'), encoding='utf-8') as f:
        return json.load(f)


def _gravar_caso(registro):
    with open(os.path.join(_pasta_caso(registro['caso']), 'caso.json'), 'w',
              encoding='utf-8') as f:
        json.dump(registro, f, ensure_ascii=False, indent=2)


def _primeiro_nome(nome):
    p = (nome or '').strip().split()
    return p[0].capitalize() if p else ''


# ============================================================
# 1. GERAR
# ============================================================

def _preflight_gerar(args, area):
    """Confere tudo que pode travar ANTES de gastar com a IA."""
    erros = []
    if not os.path.exists(contratacao.fmt.TEMPLATE_PATH):
        erros.append('Timbrado ausente: coloque o timbrado em config/timbrado_modelo.docx')
    if not args.exemplo and not getattr(args, 'cliente', None):
        if not args.arquivos:
            erros.append('Informe a transcricao da reuniao (e os documentos do cliente).')
        for arq in args.arquivos:
            if not os.path.exists(arq):
                erros.append(f'Arquivo nao encontrado: {arq}')
    if args.usar_drive:
        if not os.getenv(AREAS[area]):
            erros.append(f'{AREAS[area]} vazio no config/.env (ID da pasta da area no Drive). '
                         'Configure ou rode com --sem-drive.')
        credenciais = (os.getenv('GOOGLE_OAUTH_CREDENTIALS')
                       or os.path.join(ROOT, 'config', 'oauth_credentials.json'),
                       os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                       or os.path.join(ROOT, 'config', 'credentials.json'))
        if not any(os.path.exists(c) for c in credenciais):
            erros.append('Credencial do Google ausente (config/oauth_credentials.json; ver '
                         'docs/ONBOARDING.md). Configure ou rode com --sem-drive.')
    if args.unidade and args.unidade.upper() not in contratacao.equipe.UNIDADES:
        erros.append(f'Unidade invalida: {args.unidade}. Use: '
                     f'{", ".join(contratacao.equipe.UNIDADES)}')
    return erros


def gerar(args):
    area = normalizar_area('PREVIDENCIARIO' if args.exemplo and not args.area else args.area)
    if not area:
        print(f'ERRO: informe a area com --area ({", ".join(AREAS)}).')
        return 1
    args.usar_drive = not (args.sem_drive or args.exemplo)

    erros = _preflight_gerar(args, area)
    if erros:
        print('Nao da para comecar:')
        for e in erros:
            print(f'  - {e}')
        return 1

    print('\n=== CONTRATACAO - GERAR ===')
    print(f'Area: {area} | Revisao: {contratacao.responsavel_revisao(area)}')

    # 1. Analise do caso + dados do cliente
    if args.exemplo:
        from exemplo import DADOS_EXEMPLO
        print('\n1. Usando o caso FICTICIO de exemplo (sem IA).')
        dados = dict(DADOS_EXEMPLO)
    else:
        from llm_processor import ErroAnalise, analisar_caso
        print(f'\n1. A IA esta lendo a reuniao e {len(args.arquivos) - 1} documento(s)... '
              '(pode levar alguns minutos)')
        try:
            dados = analisar_caso(args.arquivos[0], args.arquivos[1:], area)
        except ErroAnalise as e:
            print(f'ERRO: {e}')
            return 1

    dados, avisos = contratacao.normalizar_dados(dados)
    nome = dados.get('nome', '').strip()
    print(f'   Cliente: {nome or "(nao identificado)"}')
    print(f'   Demanda: {dados.get("tipo_acao") or "(nao identificada)"}')
    if dados.get('motivo_urgencia'):
        print(f'   >>> URGENTE: {dados["motivo_urgencia"]}')
    for a in avisos:
        print(f'   Aviso: {a}')
    return _montar_caso(args, area, dados, avisos)


def _montar_caso(args, area, dados, avisos, chaves=None, advbox=None, tipo_advbox=''):
    """Pasta no Drive + documentos no timbrado + registro no indice (comum aos dois fluxos)."""
    nome = dados.get('nome', '').strip()
    caso = f'{datetime.now():%Y-%m-%d}_{_slug(nome)}'
    pasta = _pasta_caso(caso)
    os.makedirs(pasta, exist_ok=True)
    if not nome:
        with open(os.path.join(pasta, 'dados_extraidos.json'), 'w', encoding='utf-8') as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        print('ERRO: nome do cliente nao encontrado. Confira os arquivos/o cadastro.')
        print(f'O que foi lido ficou em {pasta}')
        return 1

    # 2. Pasta no Drive + numero do contrato
    drive = pasta_cliente_id = None
    link_drive = numero_contrato = ''
    if args.usar_drive:
        import google_integration as g
        print('\n2. Google Drive: pasta do cliente...')
        drive, _ = g.autenticar_google()
        pasta_cliente_id = g.criar_pasta_cliente(drive, nome, area)
        if not pasta_cliente_id:
            return 1
        link_drive = g.link_pasta(drive, pasta_cliente_id)
        numero_contrato = g.buscar_proximo_contrato(
            drive, nome, dados.get('parte_contraria', ''), area)
    else:
        print('\n2. Sem Drive (--sem-drive/--exemplo): documentos ficam so nesta maquina.')

    # 3. Documentos no timbrado
    print('\n3. Gerando documentos no timbrado...')
    docs = contratacao.gerar_documentos(dados, area, pasta, args.unidade, numero_contrato,
                                        avisos, chaves)
    for d in docs:
        pend = f' - {len(d["pendencias"])} pendencia(s)' if d['pendencias'] else ''
        print(f'   {d["nome"]}.docx [{d["modelo"]}]{pend}')

    # 4. Sobe para o Drive (versao que o advogado vai revisar)
    if drive:
        import google_integration as g
        print('\n4. Subindo para o Drive...')
        for d in docs:
            sub = g.buscar_subpasta(drive, pasta_cliente_id, d['subpasta']) or pasta_cliente_id
            enviado = g.enviar_arquivo(drive, d['arquivo'], sub)
            d['drive_id'] = enviado['id']
            d['drive_link'] = enviado.get('webViewLink', '')
            print(f'   {d["subpasta"]}/{os.path.basename(d["arquivo"])}')

    registro = {
        'caso': caso, 'criado_em': datetime.now().isoformat(timespec='seconds'),
        'area': area, 'unidade': args.unidade or '', 'dados': dados, 'avisos': avisos,
        'documentos': docs, 'drive_pasta_id': pasta_cliente_id, 'drive_link': link_drive,
        'zapsign': {}, 'whatsapp_enviado': False, 'advbox': dict(advbox or {}),
    }
    _gravar_caso(registro)

    pendencias = sorted({p for d in docs for p in d['pendencias']})
    modelos = {d['modelo'] for d in docs if d['assina']}
    _atualizar_indice(
        caso, data=datetime.now().strftime('%d/%m/%Y'), cliente=nome.upper(), area=area,
        responsavel=contratacao.responsavel_revisao(area), telefone=dados.get('telefone', ''),
        modelo='PROVISORIO' if 'PROVISORIO' in modelos else 'ESCRITORIO',
        pendencias=' | '.join(pendencias), pasta_drive=link_drive or pasta,
        tipo_advbox=tipo_advbox, status='AGUARDANDO REVISAO')

    print('\n' + '=' * 70)
    print(f'  Caso: {caso}')
    print(f'  Documentos: {link_drive or pasta}')
    if pendencias:
        print(f'  Falta completar no contrato/procuracao/declaracao ({len(pendencias)}):')
        for p in pendencias:
            print(f'     {p}')
    if 'PROVISORIO' in modelos:
        print('  ATENCAO: texto-base PROVISORIO (o escritorio ainda nao enviou os modelos reais).')
    print()
    print(f'  PROXIMO PASSO (humano): {contratacao.responsavel_revisao(area)} revisa os')
    print('  documentos, completa o que estiver [PREENCHER] (no Drive, editando o proprio .docx),')
    print(f'  e no indice {INDICE}')
    print('  escreve o nome na coluna "revisado_por" e marca "enviar" com SIM. Depois:')
    print('      python INTAKE/main.py enviar --simular   (confere)')
    print('      python INTAKE/main.py enviar             (manda para assinatura)')
    print('=' * 70)
    return 0


# ============================================================
# 1b. GERAR A PARTIR DO CADASTRO NO ADVBOX
# ============================================================

def _cliente_advbox(adv, busca):
    """CPF (11 digitos), ID (so digitos) ou nome -> cadastro completo do cliente."""
    digitos = ''.join(c for c in busca if c.isdigit())
    if len(digitos) == 11:
        achados = adv.buscar_cliente(cpf=contratacao.formatar_cpf(digitos)) \
            or adv.buscar_cliente(cpf=digitos)
    elif digitos and digitos == busca.strip():
        return adv.obter_cliente(digitos)
    else:
        achados = adv.buscar_cliente(nome=busca)
    if not achados:
        return None
    if len(achados) > 1:
        print(f'Achei {len(achados)} clientes para "{busca}". Rode de novo com o CPF ou o ID:')
        for c in achados[:15]:
            print(f'  ID {c.get("id")}: {c.get("name")} - CPF {c.get("identification") or "-"}')
        sys.exit(1)
    return adv.obter_cliente(achados[0]['id'])


def _escolher_processo(processos, processo_id):
    if processo_id:
        return next((p for p in processos if str(p.get('id')) == str(processo_id)), None)
    if len(processos) == 1:
        return processos[0]
    return None


def gerar_advbox(args):
    """Cliente ja cadastrado no ADVBOX -> contrato, procuracao e declaracao (sem IA)."""
    if not os.getenv('ADVBOX_API_TOKEN'):
        print('ERRO: ADVBOX_API_TOKEN vazio no config/.env.')
        return 1
    args.usar_drive = not args.sem_drive
    args.exemplo, args.arquivos = False, []
    import advbox_integration as adv

    print('\n=== CONTRATACAO - A PARTIR DO ADVBOX ===')
    cadastro = _cliente_advbox(adv, args.cliente)
    if not cadastro:
        print(f'ERRO: cliente "{args.cliente}" nao encontrado no ADVBOX.')
        return 1
    cad = cadastro.get('data', cadastro) if isinstance(cadastro, dict) else {}
    cliente_id = cad.get('id') or cad.get('customers_id')
    dados = contratacao.dados_do_advbox(cadastro)

    # Area e acao: do processo do cliente no ADVBOX, ou informadas na linha de comando
    processo = None
    processos = adv.buscar_processo(cliente_id=cliente_id) if cliente_id else []
    if not (args.area and args.acao):
        processo = _escolher_processo(processos, args.processo)
        if processos and not processo:
            print('O cliente tem mais de um processo no ADVBOX. Escolha com --processo ID '
                  '(ou informe --area e --acao):')
            for p in processos[:15]:
                print(f'  ID {p.get("id")}: {p.get("type") or "-"} ({p.get("group") or "-"}) '
                      f'{p.get("process_number") or ""}')
            return 1
    area = normalizar_area(args.area or (processo or {}).get('group', '')
                           or (processo or {}).get('type', ''))
    dados['tipo_acao'] = args.acao or (processo or {}).get('type', '') or ''
    if processo and processo.get('process_number'):
        dados['numero_processo'] = processo['process_number']
    if not area:
        print(f'ERRO: nao consegui saber a area. Informe --area ({", ".join(AREAS)}).')
        return 1

    erros = _preflight_gerar(args, area)
    if erros:
        print('Nao da para comecar:')
        for e in erros:
            print(f'  - {e}')
        return 1

    dados, avisos = contratacao.normalizar_dados(dados)
    print(f'Cliente: {dados.get("nome")} (ADVBOX ID {cliente_id})')
    print(f'Area: {area} | Acao: {dados["tipo_acao"] or "(nao informada)"} | '
          f'Revisao: {contratacao.responsavel_revisao(area)}')
    for a in avisos:
        print(f'   Aviso: {a}')
    if not dados.get('nome'):
        print('ERRO: cadastro do ADVBOX sem nome.')
        return 1

    advbox = {'cliente_id': cliente_id}
    if processo:
        advbox['processo_id'] = processo.get('id')
    return _montar_caso(args, area, dados, avisos,
                        chaves=['contrato', 'procuracao', 'declaracao'], advbox=advbox,
                        tipo_advbox=(processo or {}).get('type', ''))


# ============================================================
# 2. ENVIAR
# ============================================================

def _versao_revisada(registro, doc, drive):
    """Caminho do .docx revisado: baixa do Drive se o caso foi para o Drive."""
    if drive and doc.get('drive_id'):
        import google_integration as g
        pasta_final = os.path.join(_pasta_caso(registro['caso']), 'revisado')
        os.makedirs(pasta_final, exist_ok=True)
        return g.baixar_arquivo(drive, doc['drive_id'],
                                os.path.join(pasta_final, os.path.basename(doc['arquivo'])))
    return doc['arquivo']


def _preparar(linha, drive):
    """Confere o caso e gera os PDFs. Retorna (registro, [(doc, pdf)], [problemas])."""
    from pdf_conversao import docx_para_pdf
    registro = _ler_caso(linha['caso'])
    dados = registro['dados']
    problemas = []
    if not (linha.get('revisado_por') or '').strip():
        problemas.append('sem "revisado_por" no indice (o POP exige a revisao do advogado)')
    if not (dados.get('telefone') or dados.get('email')):
        problemas.append('cliente sem telefone e sem e-mail para receber o link de assinatura')

    a_converter = []
    for doc in registro['documentos']:
        if not doc['assina']:
            continue
        docx = _versao_revisada(registro, doc, drive)
        restantes = contratacao.pendencias_no_texto(contratacao.texto_do_docx(docx))
        if restantes:
            problemas.append(f'{doc["nome"]}: ainda tem {", ".join(restantes[:4])}'
                             + (' ...' if len(restantes) > 4 else ''))
            continue
        if doc['chave'] not in registro['zapsign']:  # senao ja foi numa rodada anterior
            a_converter.append((doc, docx))

    prontos = []
    if a_converter and not problemas:
        try:
            pdfs = docx_para_pdf([docx for _, docx in a_converter])
            prontos = [(doc, pdfs[docx]) for doc, docx in a_converter]
        except RuntimeError as e:
            problemas.append(str(e))
    return registro, prontos, problemas


def _mensagem_whatsapp(nome, links):
    linhas = [f'Olá, {_primeiro_nome(nome)}! Aqui é do escritório Welington Valois Advogados '
              'Associados.', '',
              'Seguem os documentos da sua contratação para assinar pelo celular. É só tocar '
              'em cada link e seguir as instruções da tela:', '']
    for n, (rotulo, link) in enumerate(links, 1):
        linhas.append(f'{n}. {rotulo}: {link}')
    linhas += ['', 'Qualquer dúvida, é só responder esta mensagem.']
    return '\n'.join(linhas)


def _rotulo(doc):
    return contratacao.DOCUMENTOS[doc['chave']][0].replace('Honorarios', 'Honorários') \
        .replace('Procuracao', 'Procuração').replace('Declaracao', 'Declaração') \
        .replace('Hipossuficiencia', 'Hipossuficiência')


def _dados_advbox(dados):
    rua = dados.get('logradouro', '')
    if rua and dados.get('numero'):
        rua = f'{rua}, {dados["numero"]}'
    return {
        'nome': dados.get('nome', '').upper(), 'cpf': dados.get('cpf', ''),
        'rg': dados.get('rg', ''), 'email': dados.get('email', ''),
        'telefone': dados.get('telefone', ''), 'data_nascimento': dados.get('data_nascimento', ''),
        'profissao': dados.get('profissao', ''), 'estado_civil': dados.get('estado_civil', ''),
        'rua': rua, 'bairro': dados.get('bairro', ''), 'cidade': dados.get('cidade', ''),
        'estado': dados.get('uf', ''), 'cep': dados.get('cep', ''),
    }


def _enviar_caso(linha, registro, prontos, args, whatsapp_proprio):
    import base64

    import zapsign_integration as z
    dados = registro['dados']
    nome = dados.get('nome', '').upper()
    obs = []

    # ZapSign
    for doc, pdf in prontos:
        signatarios = [z.criar_signatario(nome, dados.get('email'), dados.get('telefone'),
                                          send_whatsapp=not whatsapp_proprio)]
        if doc['chave'] == 'contrato' and os.getenv('ADVOGADO_RESPONSAVEL_NOME'):
            signatarios.append(z.criar_signatario(
                os.getenv('ADVOGADO_RESPONSAVEL_NOME'),
                os.getenv('ADVOGADO_RESPONSAVEL_EMAIL') or None, send_whatsapp=False))
        with open(pdf, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        try:
            out = z.criar_documento(doc['nome'], b64, signatarios, folder_path=f'/{nome}/',
                                    external_id=registro['caso'])
        except Exception as e:  # requests.HTTPError, timeout...
            obs.append(f'ZapSign falhou em {doc["nome"]}: {e}')
            continue
        link_cliente = next((s['link'] for s in out['sign_urls']
                             if (s['signatario'] or '').upper() == nome), '')
        registro['zapsign'][doc['chave']] = {'token': out['token'], 'link': link_cliente,
                                             'painel': out['doc_url']}
        _gravar_caso(registro)
        print(f'   ZapSign: {doc["nome"]}')
        time.sleep(1)

    # WhatsApp (Evolution) com todos os links de uma vez
    links = [(_rotulo(d), registro['zapsign'][d['chave']]['link'])
             for d in registro['documentos']
             if d['chave'] in registro['zapsign'] and registro['zapsign'][d['chave']]['link']]
    if whatsapp_proprio and links and not registro['whatsapp_enviado']:
        from INTEGRACOES import evolution_integration as evo
        if evo.enviar_texto(dados.get('telefone'), _mensagem_whatsapp(nome, links)):
            registro['whatsapp_enviado'] = True
            print('   WhatsApp: links enviados ao cliente')
        else:
            obs.append('WhatsApp falhou - mandar os links manualmente (ver caso.json)')

    # ADVBOX
    if not args.sem_advbox:
        if not os.getenv('ADVBOX_API_TOKEN'):
            obs.append('ADVBOX nao configurado - cadastrar cliente manualmente')
        else:
            import advbox_integration as adv
            try:
                if not registro['advbox'].get('cliente_id'):
                    r = adv.cadastrar_cliente(_dados_advbox(dados))
                    if r and r.get('customers_id'):
                        registro['advbox']['cliente_id'] = r['customers_id']
                tipo = (linha.get('tipo_advbox') or '').strip()
                if registro['advbox'].get('cliente_id') and not registro['advbox'].get(
                        'processo_id'):
                    if tipo:
                        r = adv.cadastrar_processo(registro['advbox']['cliente_id'], {
                            'tipo': tipo, 'pasta': nome,
                            'notas': f'Contratacao {registro["caso"]} - {dados.get("tipo_acao", "")}'
                                     f' - area {registro["area"]}. Drive: {registro["drive_link"]}',
                        })
                        if r and r.get('lawsuits_id'):
                            registro['advbox']['processo_id'] = r['lawsuits_id']
                    else:
                        obs.append('processo nao cadastrado no ADVBOX: preencha a coluna '
                                   '"tipo_advbox" com o tipo de acao exato do ADVBOX')
            except Exception as e:  # ValueError (tipo invalido), HTTP...
                obs.append(f'ADVBOX: {e}')
            _gravar_caso(registro)

    faltam = [d['nome'] for d in registro['documentos']
              if d['assina'] and d['chave'] not in registro['zapsign']]
    status = 'ENVIADO' if not faltam else 'PARCIAL'
    if faltam:
        obs.append(f'faltou enviar: {", ".join(faltam)}')
    _atualizar_indice(registro['caso'], status=status,
                      obs=f'{datetime.now():%d/%m/%Y %H:%M} ' + ' | '.join(obs))
    for o in obs:
        print(f'   Aviso: {o}')
    return status


def enviar(args):
    linhas = _ler_indice()
    fila = [l for l in linhas if (l.get('enviar') or '').strip().upper() in SIM
            and l.get('status') != 'ENVIADO']
    if args.so:
        fila = [l for l in fila if args.so.upper() in l['cliente'].upper()]
    if not fila:
        print('Nenhum caso marcado com SIM na coluna "enviar" (e ainda nao enviado).')
        print(f'Indice: {INDICE}')
        return 0

    drive = None
    if any(_ler_caso(l['caso']).get('drive_pasta_id') for l in fila):
        import google_integration as g
        drive, _ = g.autenticar_google()

    print(f'\n=== CONTRATACAO - CONFERINDO {len(fila)} CASO(S) ===')
    preparados = []
    for linha in fila:
        registro, prontos, problemas = _preparar(linha, drive)
        print(f'\n- {linha["cliente"]} ({linha["area"]}) revisado por: '
              f'{linha.get("revisado_por") or "-"}')
        if problemas:
            for p in problemas:
                print(f'   BLOQUEADO: {p}')
            _atualizar_indice(linha['caso'], status='BLOQUEADO', obs=' | '.join(problemas))
            continue
        for doc, pdf in prontos:
            print(f'   pronto: {os.path.basename(pdf)}')
        preparados.append((linha, registro, prontos))

    if not preparados:
        print('\nNada pronto para envio.')
        return 1
    if args.simular:
        print(f'\n[SIMULACAO] {len(preparados)} caso(s) passariam para o ZapSign. Nada foi enviado.')
        return 0

    if not os.getenv('ZAPSIGN_API_TOKEN'):
        print('\nERRO: ZAPSIGN_API_TOKEN vazio no config/.env.')
        return 1
    from INTEGRACOES import evolution_integration as evo
    whatsapp_proprio = evo.configurado() and evo.conectado()
    print('\nO que vai acontecer:')
    print('  - documentos criados no ZapSign (contrato: cliente + '
          f'{os.getenv("ADVOGADO_RESPONSAVEL_NOME") or "sem 2o signatario"})')
    print('  - links ao cliente pelo ' + ('WhatsApp do escritorio (Evolution)' if whatsapp_proprio
                                         else 'proprio ZapSign (Evolution nao conectada)'))
    print('  - ' + ('ADVBOX: NAO (--sem-advbox)' if args.sem_advbox
                    else 'cadastro do cliente (e do processo, se tipo_advbox preenchido) no ADVBOX'))
    if not args.sim:
        resp = input(f'\nConfirma o envio de {len(preparados)} caso(s)? (digite SIM): ')
        if resp.strip().upper() != 'SIM':
            print('Cancelado.')
            return 0

    resultado = {}
    for linha, registro, prontos in preparados:
        print(f'\n> {linha["cliente"]}')
        st = _enviar_caso(linha, registro, prontos, args, whatsapp_proprio)
        resultado[st] = resultado.get(st, 0) + 1
    print(f'\nResultado: {resultado}. Indice atualizado: {INDICE}')
    print('Os documentos assinados descem para o Drive pelo SYNC/sync_assinados.py.')
    return 0


# ============================================================
# STATUS
# ============================================================

def status(_args):
    linhas = _ler_indice()
    if not linhas:
        print('Nenhuma contratacao registrada ainda.')
        return 0
    for l in linhas:
        print(f'{l["data"]:10} {l["status"]:18} {l["area"]:20} {l["cliente"][:40]:40} '
              f'rev: {l.get("revisado_por") or "-"}')
    print(f'\nIndice: {INDICE}')
    return 0


def main():
    ap = argparse.ArgumentParser(description='Contratacao automatizada (intake).')
    sub = ap.add_subparsers(dest='comando')

    g = sub.add_parser('gerar', help='analisa a reuniao e gera os documentos para revisao')
    g.add_argument('arquivos', nargs='*', help='transcricao primeiro, depois os documentos')
    g.add_argument('--area', default='', help=', '.join(AREAS))
    g.add_argument('--unidade', default='', help='IUNA, IBATIBA ou IRUPI (local/foro)')
    g.add_argument('--sem-drive', action='store_true', help='gera so nesta maquina')
    g.add_argument('--exemplo', action='store_true', help='caso ficticio, sem IA e sem Drive')

    a = sub.add_parser('advbox', help='cliente ja cadastrado no ADVBOX -> contrato, procuracao '
                                      'e declaracao para revisao')
    a.add_argument('cliente', help='CPF, ID do ADVBOX ou nome do cliente')
    a.add_argument('--area', default='', help='se o cliente ainda nao tem processo no ADVBOX')
    a.add_argument('--acao', default='', help='ex.: "Salario-maternidade rural"')
    a.add_argument('--processo', default='', help='ID do processo, se o cliente tiver varios')
    a.add_argument('--unidade', default='', help='IUNA, IBATIBA ou IRUPI (local/foro)')
    a.add_argument('--sem-drive', action='store_true', help='gera so nesta maquina')

    e = sub.add_parser('enviar', help='envia para assinatura o que ja foi revisado')
    e.add_argument('--so', help='so o cliente cujo nome contem este texto')
    e.add_argument('--simular', action='store_true', help='confere e gera PDFs, nao envia')
    e.add_argument('--sem-advbox', action='store_true', help='nao cadastra no ADVBOX')
    e.add_argument('--sim', action='store_true', help='nao pede confirmacao')

    sub.add_parser('status', help='lista as contratacoes e o andamento')

    # Compatibilidade: "main.py TRANSCRICAO.pdf ... --area X" = gerar
    argv = sys.argv[1:]
    if argv and argv[0] not in ('gerar', 'advbox', 'enviar', 'status', '-h', '--help'):
        argv = ['gerar'] + argv
    args = ap.parse_args(argv)
    if not args.comando:
        ap.print_help()
        return 1
    return {'gerar': gerar, 'advbox': gerar_advbox, 'enviar': enviar,
            'status': status}[args.comando](args)


if __name__ == '__main__':
    sys.exit(main())
