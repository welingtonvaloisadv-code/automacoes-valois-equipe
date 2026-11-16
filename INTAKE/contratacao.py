"""
Documentos da contratacao - Welington Valois Advogados Associados.

Monta, no timbrado do escritorio (config/timbrado_modelo.docx), a partir dos dados do
cliente (ficha = documento guia):
    Ficha do Cliente           -> ATOS INTERNOS (interno, marcada PRONTA PARA REVISAO)
    Contrato de Honorarios     -> PASTA DO CLIENTE (vai para assinatura)
    Procuracao                 -> PASTA DO CLIENTE (vai para assinatura)
    Declaracao de Hipossuficiencia -> PASTA DO CLIENTE (so quando ha pedido de gratuidade)

Textos em INTAKE/modelos/ (provisorios); o modelo real do escritorio, quando chegar,
vai em DOCS_MODELOS/contratacao/ com o mesmo nome e passa a valer no lugar.

Dado que falta NUNCA e inventado: sai [PREENCHER: campo] no documento, e o envio para
assinatura fica bloqueado enquanto sobrar qualquer marca (ver pendencias_no_texto).
"""
import importlib.util
import os
import re
import sys
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import equipe  # noqa: E402
from config import regras_financeiras  # noqa: E402

# Motor de formatacao das pecas (mesmo padrao: Segoe UI 12, 1,15, timbrado). Carregado pelo
# caminho porque a pasta dele tem um config.py que colidiria com config/ da raiz.
_spec = importlib.util.spec_from_file_location(
    'escritorio_format',
    os.path.join(ROOT, 'OPERACIONAL', 'agente_operacional', 'escritorio_format.py'))
fmt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fmt)

MODELOS_PADRAO = os.path.join(ROOT, 'INTAKE', 'modelos')
MODELOS_ESCRITORIO = os.path.join(ROOT, 'DOCS_MODELOS', 'contratacao')

# Marcas que impedem o envio para assinatura enquanto estiverem no documento.
MARCAS_PENDENTES = ('[PREENCHER', '[CONFERIR', '{{')

MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho',
         'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

# Documentos da contratacao: chave -> (nome no arquivo, modelo, subpasta no Drive, assina?)
DOCUMENTOS = {
    'ficha': ('Ficha Cliente', 'ficha.txt', 'ATOS INTERNOS', False),
    'contrato': ('Contrato de Honorarios', 'contrato.txt', 'PASTA DO CLIENTE', True),
    'procuracao': ('Procuracao', 'procuracao.txt', 'PASTA DO CLIENTE', True),
    'declaracao': ('Declaracao de Hipossuficiencia', 'declaracao_hipossuficiencia.txt',
                   'PASTA DO CLIENTE', True),
}

# Campos que os modelos podem usar (alem dos dados do cliente vindos da IA).
CAMPOS = (
    'nome, cpf, rg, orgao_emissor, data_nascimento, nacionalidade, estado_civil, profissao, '
    'telefone, email, endereco_completo, qualificacao_cliente, area, tipo_acao, parte_contraria, '
    'numero_processo, referencia_processo, referencia_parte_contraria, data_reuniao, indicante, '
    'origem, urgencia, dados_area, resumo_fatos, documentos_necessarios, pendencias, '
    'escritorio_razao_social, escritorio_cnpj, escritorio_endereco, advogados_area, outorgados, '
    'responsavel_revisao, responsavel_revisao_maiusculo, cidade_unidade, comarca_foro, '
    'local_data, numero_contrato, clausula_objeto, clausula_honorarios, poderes_area, '
    'honorarios_valor, honorarios_pagamento'
)

# Documentos que o escritorio sempre exige por area (CLAUDE.md, "Regras que a IA nunca ignora").
DOCUMENTOS_FIXOS = {
    'PREVIDENCIARIO': [
        'Documento de identidade com CPF e comprovante de endereço atualizado',
        'Senha do Meu INSS (gov.br) ou extrato do CNIS',
        'Comunicado de indeferimento / protocolo do requerimento no INSS, se já houver',
        'Benefício por incapacidade: laudo médico com MENOS DE 60 DIAS e descrição da CID',
        'BPC/LOAS: renda per capita inferior a 1/4 do salário mínimo, laudo médico atualizado '
        'e cadastro no CRAS/CadÚnico atualizado',
        'Rural: início de prova material do período (notas, ITR/CCIR, contrato de parceria, '
        'declaração do sindicato) e nomes de testemunhas',
    ],
    'CRIMINAL': [
        'Cópia do auto de prisão em flagrante, inquérito, denúncia ou número do processo',
        'Documento de identidade, comprovante de residência e de ocupação lícita',
    ],
    'FAMILIA E SUCESSOES': [
        'Certidões de casamento, nascimento dos filhos e/ou óbito, conforme o caso',
        'Documentos dos bens (matrícula de imóvel, CRLV, extratos) e de renda',
    ],
    'BANCARIO': [
        'Contratos, extratos e histórico de empréstimos consignados (Meu INSS)',
        'Parecer de viabilidade OBRIGATÓRIO antes de qualquer ação revisional/defensiva',
    ],
    'CIVEL E CONSUMIDOR': [
        'Provas do fato: notas, protocolos de atendimento, prints, fotos, contratos',
    ],
}


# ============================================================
# DADOS DO CLIENTE: normalizacao e validacao
# ============================================================

def _digitos(valor):
    return ''.join(c for c in str(valor or '') if c.isdigit())


def cpf_valido(cpf):
    d = _digitos(cpf)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if (soma * 10 % 11) % 10 != int(d[n]):
            return False
    return True


def formatar_cpf(cpf):
    d = _digitos(cpf)
    return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}' if len(d) == 11 else (cpf or '')


def formatar_cep(cep):
    d = _digitos(cep)
    return f'{d[:5]}-{d[5:]}' if len(d) == 8 else (cep or '')


def formatar_telefone(tel):
    d = _digitos(tel)
    if d.startswith('55') and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return f'({d[:2]}) {d[2:7]}-{d[7:]}'
    if len(d) == 10:
        return f'({d[:2]}) {d[2:6]}-{d[6:]}'
    return tel or ''


def data_valida(data):
    try:
        datetime.strptime(str(data or ''), '%d/%m/%Y')
        return True
    except ValueError:
        return False


def normalizar_dados(dados):
    """Formata CPF/CEP/telefone e devolve (dados, avisos). Nao inventa nada."""
    d = {k: (v.strip() if isinstance(v, str) else v) for k, v in dados.items()}
    avisos = []
    if d.get('cpf'):
        if cpf_valido(d['cpf']):
            d['cpf'] = formatar_cpf(d['cpf'])
        else:
            avisos.append(f'CPF "{d["cpf"]}" invalido (digitos verificadores) - conferir no documento')
    if d.get('cep'):
        d['cep'] = formatar_cep(d['cep'])
    if d.get('telefone'):
        d['telefone'] = formatar_telefone(d['telefone'])
    if d.get('uf'):
        d['uf'] = d['uf'].upper()[:2]
    for campo in ('data_nascimento', 'data_reuniao'):
        if d.get(campo) and not data_valida(d[campo]):
            avisos.append(f'{campo} "{d[campo]}" fora do formato DD/MM/AAAA')
    return d, avisos


def _ou_pendente(valor, rotulo):
    return valor if valor else f'[PREENCHER: {rotulo}]'


def endereco_completo(d):
    rua = d.get('logradouro', '')
    if rua and d.get('numero'):
        rua = f'{rua}, nº {d["numero"]}'
    partes = [
        _ou_pendente(rua, 'logradouro e número'),
        _ou_pendente(d.get('bairro'), 'bairro'),
        _ou_pendente(f'{d["cidade"]}/{d.get("uf", "")}'.rstrip('/') if d.get('cidade') else '',
                     'cidade/UF'),
        'CEP ' + _ou_pendente(d.get('cep'), 'CEP'),
    ]
    return ', '.join(partes)


def qualificacao(d):
    """Qualificacao do cliente no padrao dos instrumentos. Campo ausente -> [PREENCHER]."""
    rg = _ou_pendente(d.get('rg'), 'RG')
    if d.get('rg') and d.get('orgao_emissor'):
        rg = f'{d["rg"]} ({d["orgao_emissor"]})'
    return (f'**{_ou_pendente(d.get("nome", "").upper(), "nome completo")}**, '
            f'{_ou_pendente(d.get("nacionalidade"), "nacionalidade")}, '
            f'{_ou_pendente(d.get("estado_civil"), "estado civil")}, '
            f'{_ou_pendente(d.get("profissao"), "profissão")}, '
            f'portador(a) do RG nº {rg}, '
            f'inscrito(a) no CPF sob o nº {_ou_pendente(d.get("cpf"), "CPF")}, '
            f'residente e domiciliado(a) em {endereco_completo(d)}, '
            f'telefone/WhatsApp {_ou_pendente(d.get("telefone"), "telefone")}'
            + (f', e-mail {d["email"]}' if d.get('email') else ''))


# ============================================================
# CONTEXTO DOS MODELOS
# ============================================================

def _advogado(chave):
    a = equipe.ADVOGADOS[chave]
    titulo = 'Dra.' if a['genero'] == 'F' else 'Dr.'
    return titulo, a['nome'], a['oab']


def advogados_da_area(area):
    return equipe.ADVOGADOS_POR_AREA.get(area) or ['WELINGTON']


def responsavel_revisao(area):
    titulo, nome, _ = _advogado(advogados_da_area(area)[0])
    return f'{titulo} {nome}'


def outorgados(area):
    """Advogados da area + o socio (Dr. Welington), sem repetir."""
    chaves = list(advogados_da_area(area))
    if 'WELINGTON' not in chaves:
        chaves.append('WELINGTON')
    return '; '.join(f'**{n.upper()}**, advogado(a), {oab}'
                     for _, n, oab in (_advogado(c) for c in chaves))


def unidade(chave=None, cidade_cliente=''):
    """Unidade do escritorio: a informada, a da cidade do cliente, ou a padrao (Iuna)."""
    if chave and chave.upper() in equipe.UNIDADES:
        return equipe.UNIDADES[chave.upper()]
    cidade = fmt._normalizar_acento(cidade_cliente or '')
    for u in equipe.UNIDADES.values():
        if fmt._normalizar_acento(u['cidade'].split('/')[0]) in cidade:
            return u
    return equipe.UNIDADES[equipe.UNIDADE_PADRAO]


def data_extenso(quando=None):
    q = quando or datetime.now()
    return f'{q.day} de {MESES[q.month - 1]} de {q.year}'


def _lista(itens):
    itens = [i for i in (itens or []) if str(i).strip()]
    return '\n'.join(f'{n}. {i}' for n, i in enumerate(itens, 1)) if itens else 'Nenhuma.'


def montar_contexto(dados, area, unidade_chave=None, numero_contrato='', avisos=None):
    """Junta dados do cliente + escritorio + area num dicionario para os modelos."""
    d = dict(dados)
    u = unidade(unidade_chave, d.get('cidade', ''))
    cidade_u = u['cidade']
    resp = responsavel_revisao(area)

    ctx = {k: v for k, v in d.items() if isinstance(v, str)}
    ctx.update({
        'nome': d.get('nome', '').upper(),
        'area': area,
        'endereco_completo': endereco_completo(d),
        'qualificacao_cliente': qualificacao(d),
        'escritorio_razao_social': os.getenv('ESCRITORIO_RAZAO_SOCIAL')
        or os.getenv('ESCRITORIO_NOME') or 'Welington Valois Advogados Associados',
        'escritorio_cnpj': os.getenv('ESCRITORIO_CNPJ', '64.917.923/0001-95'),
        'escritorio_endereco': u['endereco'],
        'advogados_area': ', '.join(f'{t} {n} ({oab})' for t, n, oab in
                                    (_advogado(c) for c in advogados_da_area(area))),
        'outorgados': outorgados(area),
        'responsavel_revisao': resp,
        'responsavel_revisao_maiusculo': resp.split(' ', 1)[1].upper(),
        'cidade_unidade': cidade_u,
        'comarca_foro': cidade_u,
        'local_data': f'{cidade_u}, {data_extenso()}.',
        'numero_contrato': f'Contrato nº {numero_contrato}' if numero_contrato else '',
        'referencia_processo': (f', autos nº {d["numero_processo"]}'
                                if d.get('numero_processo') else ''),
        'referencia_parte_contraria': (f', em face de {d["parte_contraria"]}'
                                       if d.get('parte_contraria') else ''),
        'urgencia': (f'**URGENTE:** {d["motivo_urgencia"]}' if d.get('motivo_urgencia') else ''),
        'dados_area': '\n'.join(f'**{i["campo"]}:** {i["valor"]}'
                                for i in d.get('dados_area') or [] if i.get('valor'))
        or 'Nenhum dado específico informado na reunião.',
        'documentos_necessarios': _lista(DOCUMENTOS_FIXOS.get(area, [])
                                         + list(d.get('documentos_necessarios') or [])),
        'pendencias': _lista(list(avisos or []) + list(d.get('pendencias') or [])),
    })
    ctx.update(regras_financeiras.HONORARIOS_PADRAO.get(area, {}))

    # Clausulas que dependem da area (arquivos proprios, tambem substituiveis)
    for campo, pasta in (('clausula_objeto', 'objeto'), ('clausula_honorarios', 'honorarios'),
                         ('poderes_area', 'poderes')):
        ctx[campo] = preencher(carregar_modelo(os.path.join(pasta, f'{area}.txt')), ctx)
    return ctx


# ============================================================
# MODELOS
# ============================================================

def origem_modelo(nome_arquivo):
    """'ESCRITORIO' se ha modelo do escritorio em DOCS_MODELOS/contratacao/, senao 'PROVISORIO'."""
    return ('ESCRITORIO' if os.path.exists(os.path.join(MODELOS_ESCRITORIO, nome_arquivo))
            else 'PROVISORIO')


def carregar_modelo(nome_arquivo):
    for base in (MODELOS_ESCRITORIO, MODELOS_PADRAO):
        caminho = os.path.join(base, nome_arquivo)
        if os.path.exists(caminho):
            with open(caminho, encoding='utf-8') as f:
                linhas = [l for l in f.read().splitlines() if not l.lstrip().startswith('%')]
            return '\n'.join(linhas).strip('\n')
    raise FileNotFoundError(f'Modelo nao encontrado: {nome_arquivo}')


_RE_CAMPO = re.compile(r'\{\{(\?)?\s*([a-zA-Z_]+)\s*\}\}')


def preencher(texto, ctx):
    """{{campo}} -> valor ou [PREENCHER: campo]; {{?campo}} -> valor ou vazio."""
    def troca(m):
        opcional, campo = m.group(1), m.group(2)
        valor = str(ctx.get(campo) or '').strip()
        if valor:
            return valor
        return '' if opcional else f'[PREENCHER: {campo.replace("_", " ")}]'
    return _RE_CAMPO.sub(troca, texto)


def pendencias_no_texto(texto):
    """Lista as marcas que bloqueiam o envio ([PREENCHER...], [CONFERIR...], {{...}})."""
    achadas = re.findall(r'\[(?:PREENCHER|CONFERIR)[^\]]*\]|\{\{[^}]*\}\}', texto)
    return sorted(set(achadas))


# ============================================================
# RENDERIZACAO NO TIMBRADO
# ============================================================

def renderizar_docx(texto, saida):
    """Escreve o texto (marcacao do LEIA-ME) no timbrado, no padrao do escritorio."""
    if not os.path.exists(fmt.TEMPLATE_PATH):
        raise FileNotFoundError(f'Timbrado nao encontrado: {fmt.TEMPLATE_PATH}')
    doc = Document(str(fmt.TEMPLATE_PATH))
    fmt._ajustar_margens(doc)
    fmt._limpar_corpo(doc)

    # Linha em branco no modelo so separa paragrafos; o espacamento vem do estilo do timbrado.
    for linha in texto.split('\n'):
        s = linha.strip()
        if not s or s == '>>':
            continue
        p = doc.add_paragraph()
        if s.startswith('## '):
            fmt._padrao_paragrafo(p, recuo_primeira=False)
            fmt._add_texto_inline(p, s[3:], negrito_total=True)
        elif s.startswith('# '):
            fmt._padrao_paragrafo(p, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, recuo_primeira=False)
            fmt._add_texto_inline(p, s[2:], negrito_total=True)
        elif s.startswith('>>'):
            fmt._padrao_paragrafo(p, alinhamento=WD_ALIGN_PARAGRAPH.CENTER, recuo_primeira=False)
            fmt._add_texto_inline(p, s[2:].strip())
        else:
            fmt._padrao_paragrafo(p)
            fmt._add_texto_inline(p, s)
    doc.save(saida)
    return saida


def texto_do_docx(caminho):
    doc = Document(caminho)
    return '\n'.join(p.text for p in doc.paragraphs)


def documentos_da_contratacao(dados):
    """Quais documentos gerar: a declaracao so quando ha pedido de gratuidade."""
    chaves = ['ficha', 'contrato', 'procuracao']
    if str(dados.get('pedir_gratuidade', 'SIM')).upper() != 'NAO':
        chaves.append('declaracao')
    return chaves


def _primeiro(origem, *chaves):
    for c in chaves:
        v = origem.get(c)
        if v not in (None, ''):
            return str(v).strip()
    return ''


def dados_do_advbox(cliente):
    """Cadastro do cliente no ADVBOX (GET /customers/{id}) -> dados no formato da ficha.
    Campo que o ADVBOX nao tem (nacionalidade, orgao emissor...) fica vazio -> [PREENCHER]."""
    c = cliente.get('data', cliente) if isinstance(cliente, dict) else {}
    if isinstance(c, list):
        c = c[0] if c else {}
    nasc = _primeiro(c, 'birthdate', 'birth_date')
    if re.match(r'^\d{4}-\d{2}-\d{2}', nasc):
        nasc = f'{nasc[8:10]}/{nasc[5:7]}/{nasc[:4]}'
    return {
        'nome': _primeiro(c, 'name', 'nome'),
        'cpf': _primeiro(c, 'identification', 'cpf'),
        'rg': _primeiro(c, 'document', 'rg'),
        'data_nascimento': nasc,
        'nacionalidade': _primeiro(c, 'nationality', 'nacionalidade'),
        'estado_civil': _primeiro(c, 'civil_status', 'marital_status'),
        'profissao': _primeiro(c, 'occupation', 'profession'),
        'telefone': _primeiro(c, 'cellphone', 'phone', 'whatsapp'),
        'email': _primeiro(c, 'email'),
        'logradouro': _primeiro(c, 'street', 'address'),
        'numero': _primeiro(c, 'number', 'street_number'),
        'bairro': _primeiro(c, 'region', 'neighborhood', 'district'),
        'cidade': _primeiro(c, 'city'),
        'uf': _primeiro(c, 'state', 'uf'),
        'cep': _primeiro(c, 'postalcode', 'zipcode', 'cep'),
        'pedir_gratuidade': 'SIM',
    }


def gerar_documentos(dados, area, pasta_saida, unidade_chave=None, numero_contrato='',
                     avisos=None, chaves=None):
    """
    Gera os .docx da contratacao em pasta_saida (chaves: quais documentos; padrao = todos
    os cabiveis, ver documentos_da_contratacao).
    Retorna lista de dicts: {chave, nome, arquivo, subpasta, assina, modelo, pendencias}.
    """
    os.makedirs(pasta_saida, exist_ok=True)
    ctx = montar_contexto(dados, area, unidade_chave, numero_contrato, avisos)
    nome_cliente = dados.get('nome', 'CLIENTE').strip().upper() or 'CLIENTE'
    data_ficha = datetime.now().strftime('%d-%m-%Y')

    gerados = []
    for chave in chaves or documentos_da_contratacao(dados):
        rotulo, modelo, subpasta, assina = DOCUMENTOS[chave]
        texto = preencher(carregar_modelo(modelo), ctx)
        nome = (f'{nome_cliente} - {rotulo} - {data_ficha}' if chave == 'ficha'
                else f'{nome_cliente} - {rotulo}')
        arquivo = os.path.join(pasta_saida, f'{nome}.docx')
        renderizar_docx(texto, arquivo)
        origens = {origem_modelo(modelo)}
        if chave == 'contrato':
            origens |= {origem_modelo(f'objeto/{area}.txt'), origem_modelo(f'honorarios/{area}.txt')}
        elif chave == 'procuracao':
            origens.add(origem_modelo(f'poderes/{area}.txt'))
        gerados.append({
            'chave': chave, 'nome': nome, 'arquivo': arquivo, 'subpasta': subpasta,
            'assina': assina,
            'modelo': 'PROVISORIO' if 'PROVISORIO' in origens else 'ESCRITORIO',
            'pendencias': pendencias_no_texto(texto) if assina else [],
        })
    return gerados
