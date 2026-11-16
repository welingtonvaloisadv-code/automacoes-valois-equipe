"""
Analise do caso + extracao dos dados do cliente (uma chamada ao Claude).

Entrada: transcricao da reuniao e documentos (CNH/RG, comprovante, cadastro .txt, CNIS...).
PDFs e imagens vao direto para o Claude (le inclusive documento escaneado/foto);
.txt e .docx vao como texto.

Saida: dict com os dados da ficha (documento guia). Campo nao informado volta vazio -
o gerador de documentos transforma em [PREENCHER] e nada e inventado.

Modelo: INTAKE_MODELO no config/.env (padrao claude-opus-5-5).
"""
import base64
import json
import mimetypes
import os

import anthropic

MODELO_PADRAO = 'claude-opus-5-5'

# O que procurar em cada area (vira a secao "dados especificos" da ficha).
FOCO_AREA = {
    'PREVIDENCIARIO': (
        'Previdenciario (RGPS/INSS). O escritorio ajuiza na comarca local (competencia delegada). '
        'Identifique o beneficio (salario-maternidade, beneficio por incapacidade, BPC/LOAS, '
        'aposentadoria rural ou urbana, pensao por morte, auxilio-acidente). Dados especificos a '
        'procurar: beneficio pretendido, situacao no INSS (nao requerido / em analise / indeferido, '
        'NB e DER se houver, motivo do indeferimento), qualidade de segurado e carencia, tempo '
        'rural e inicio de prova material, CID e data do laudo (incapacidade: laudo com menos de '
        '60 dias), composicao e renda do grupo familiar e CadUnico (BPC: renda per capita inferior '
        'a 1/4 do salario minimo), data do parto/nascimento (maternidade), data do obito e '
        'dependentes (pensao).'
    ),
    'CRIMINAL': (
        'Defesa criminal. Dados especificos a procurar: situacao do cliente (preso, solto, '
        'investigado, reu), data e local da prisao/fato, tipo penal imputado, delegacia/vara e '
        'numero do inquerito/processo, fase do processo, prazos correndo, antecedentes. Prisao ou '
        'prazo correndo e URGENTE: descreva em motivo_urgencia.'
    ),
    'FAMILIA E SUCESSOES': (
        'Familia e sucessoes. Dados especificos a procurar: tipo de demanda (divorcio, alimentos, '
        'guarda, uniao estavel, inventario/arrolamento), a outra parte, filhos menores, regime de '
        'bens, bens a partilhar, falecido e data do obito, herdeiros, possibilidade de via '
        'extrajudicial (cartorio) e consenso entre as partes.'
    ),
    'BANCARIO': (
        'Direito bancario. Dados especificos a procurar: banco, tipo de contrato (consignado, RMC/'
        'cartao consignado, financiamento, emprestimo pessoal), valores, parcelas, descontos '
        'indevidos, busca e apreensao em curso. Parecer de viabilidade e obrigatorio antes de agir.'
    ),
    'CIVEL E CONSUMIDOR': (
        'Civel e consumidor. Dados especificos a procurar: fornecedor/parte contraria, o que '
        'aconteceu e quando, prejuizo material, dano moral, tentativas de solucao (protocolos), '
        'provas disponiveis, valor envolvido (Juizado Especial ou vara civel).'
    ),
}

SYSTEM = """Voce e advogado(a) senior do escritorio Welington Valois Advogados Associados \
(Iuna, Ibatiba e Irupi/ES; responsavel Dr. Welington Dias Valois, OAB/ES 34.912). O publico \
e do interior do Espirito Santo, boa parte rural.

Voce recebe a transcricao da reuniao de contratacao e os documentos do cliente. Faca duas coisas:

1. EXTRAIA os dados do cliente e do caso para a ficha (documento guia da contratacao).
   - Dados pessoais (nome, CPF, RG, nascimento, nacionalidade) vem PRIMEIRO dos documentos
     (CNH/RG) e do cadastro; a transcricao so completa o que faltar.
   - Datas no formato DD/MM/AAAA. CPF como aparece no documento.
   - NUNCA invente. Dado que nao aparece nos documentos nem na conversa = string vazia "".
   - pendencias: o que falta para fechar a contratacao ou que esta contraditorio
     (ex.: "CPF da transcricao difere do RG", "falta comprovante de endereco").

2. ESCREVA a analise tecnica em resumo_fatos, em linguagem juridica formal, terceira pessoa,
   referindo-se ao cliente pelo polo (o(a) Requerente / o(a) Assistido(a)), com as secoes:
   Sintese dos Fatos; Enquadramento Juridico (requisitos legais e se cada um esta presente,
   ausente ou a confirmar); Via Recomendada; Gestao de Riscos (riscos, pontos fortes, pior
   cenario); Perguntas ao Cliente para reforco probatorio; Conclusao.
   - Cite somente dispositivos legais de que tenha certeza. Jurisprudencia: NAO cite numero de
     processo ou sumula; se for util, escreva [CONFERIR jurisprudencia sobre ...].
   - Formato: texto simples, um paragrafo por linha, titulos de secao em **negrito** sozinhos
     na linha, itens numerados "1." quando for lista. Sem markdown alem de **negrito**.

Area do caso (informada pelo advogado): {area}
{foco}"""

# Structured outputs: todos os campos obrigatorios; vazio quando nao informado.
_TEXTO = {'type': 'string'}
CAMPOS_TEXTO = [
    'nome', 'cpf', 'rg', 'orgao_emissor', 'data_nascimento', 'nacionalidade', 'estado_civil',
    'profissao', 'telefone', 'email', 'logradouro', 'numero', 'bairro', 'cidade', 'uf', 'cep',
    'tipo_acao', 'parte_contraria', 'numero_processo', 'data_reuniao', 'indicante', 'origem',
    'motivo_urgencia', 'resumo_fatos',
]
SCHEMA = {
    'type': 'object',
    'properties': {
        **{c: _TEXTO for c in CAMPOS_TEXTO},
        'pedir_gratuidade': {'type': 'string', 'enum': ['SIM', 'NAO']},
        'dados_area': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'campo': _TEXTO, 'valor': _TEXTO},
                'required': ['campo', 'valor'],
                'additionalProperties': False,
            },
        },
        'documentos_necessarios': {'type': 'array', 'items': _TEXTO},
        'pendencias': {'type': 'array', 'items': _TEXTO},
    },
    'required': CAMPOS_TEXTO + ['pedir_gratuidade', 'dados_area', 'documentos_necessarios',
                                'pendencias'],
    'additionalProperties': False,
}

DESCRICAO_CAMPOS = """Campos: tipo_acao = demanda/beneficio em poucas palavras (ex.: "Salario-maternidade rural"); \
parte_contraria = INSS, banco, empresa, outra parte (vazio se nao houver); logradouro sem o numero; \
uf com 2 letras; indicante/origem = quem indicou e como chegou ao escritorio; \
pedir_gratuidade = SIM salvo se a conversa mostrar renda incompativel; \
documentos_necessarios = documentos que o cliente ainda precisa trazer para ESTE caso."""


class ErroAnalise(RuntimeError):
    pass


def _bloco_arquivo(caminho):
    """Transforma um arquivo em bloco de conteudo para a API."""
    ext = os.path.splitext(caminho)[1].lower()
    nome = os.path.basename(caminho)
    if ext in ('.txt', '.md', '.csv'):
        with open(caminho, encoding='utf-8', errors='replace') as f:
            return [{'type': 'text', 'text': f'<arquivo nome="{nome}">\n{f.read()}\n</arquivo>'}]
    if ext == '.docx':
        from docx import Document
        texto = '\n'.join(p.text for p in Document(caminho).paragraphs)
        return [{'type': 'text', 'text': f'<arquivo nome="{nome}">\n{texto}\n</arquivo>'}]
    with open(caminho, 'rb') as f:
        b64 = base64.standard_b64encode(f.read()).decode('utf-8')
    if ext == '.pdf':
        return [{'type': 'text', 'text': f'Arquivo a seguir: {nome}'},
                {'type': 'document',
                 'source': {'type': 'base64', 'media_type': 'application/pdf', 'data': b64}}]
    mime = mimetypes.guess_type(caminho)[0] or ''
    if mime in ('image/jpeg', 'image/png', 'image/gif', 'image/webp'):
        return [{'type': 'text', 'text': f'Imagem a seguir: {nome}'},
                {'type': 'image', 'source': {'type': 'base64', 'media_type': mime, 'data': b64}}]
    raise ErroAnalise(f'Formato nao suportado: {nome} (use PDF, imagem, .txt ou .docx)')


def analisar_caso(transcricao, documentos, area):
    """
    transcricao: caminho do arquivo da reuniao (PDF/.txt/.docx)
    documentos: lista de caminhos (CNH, RG, cadastro, comprovantes...)
    area: chave de google_integration.AREAS
    Retorna dict no formato de SCHEMA.
    """
    conteudo = [{'type': 'text', 'text': 'TRANSCRICAO DA REUNIAO:'}]
    conteudo += _bloco_arquivo(transcricao)
    if documentos:
        conteudo.append({'type': 'text', 'text': 'DOCUMENTOS DO CLIENTE:'})
        for doc in documentos:
            conteudo += _bloco_arquivo(doc)
    conteudo.append({'type': 'text', 'text': DESCRICAO_CAMPOS})

    client = anthropic.Anthropic()
    try:
        resp = client.beta.messages.create(
            model=os.getenv('INTAKE_MODELO') or MODELO_PADRAO,
            max_tokens=16000,
            system=SYSTEM.format(area=area, foco=FOCO_AREA.get(area, '')),
            messages=[{'role': 'user', 'content': conteudo}],
            output_config={'effort': 'high',
                           'format': {'type': 'json_schema', 'schema': SCHEMA}},
            # Se o modelo recusar por engano (classificador), o servidor tenta outro modelo.
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
        )
    except anthropic.AuthenticationError:
        raise ErroAnalise('Chave da API invalida: confira ANTHROPIC_API_KEY no config/.env.')
    except anthropic.BadRequestError as e:
        raise ErroAnalise(f'Pedido recusado pela API: {e.message}')
    except anthropic.APIConnectionError:
        raise ErroAnalise('Sem conexao com a API do Claude. Confira a internet.')
    except anthropic.APIStatusError as e:
        raise ErroAnalise(f'Erro da API ({e.status_code}): {e.message}')

    if resp.stop_reason == 'refusal':
        raise ErroAnalise('O modelo recusou a analise. Rode de novo ou faca a ficha manualmente.')
    if resp.stop_reason == 'max_tokens':
        raise ErroAnalise('A resposta foi cortada (limite de tamanho). Rode de novo.')

    texto = next((b.text for b in resp.content if b.type == 'text'), '')
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        raise ErroAnalise('A IA nao devolveu JSON valido.')
