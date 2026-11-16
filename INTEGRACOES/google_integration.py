"""
Integracao Google Drive/Docs/Sheets - Welington Valois Advogados Associados.

Estrutura de pastas no Drive (ver .claude/rules/padroes-documentos.md):
    {PASTA DA AREA}/{NOME DO CLIENTE}/ATOS INTERNOS | DOCUMENTOS DO CLIENTE | PASTA DO CLIENTE
Os IDs das pastas de area vem do config/.env (DRIVE_PASTA_<AREA>).
"""
import os
import sys
import unicodedata
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/spreadsheets'
]

FOLDER_MIME = 'application/vnd.google-apps.folder'
SUBPASTAS_CLIENTE = ['ATOS INTERNOS', 'DOCUMENTOS DO CLIENTE', 'PASTA DO CLIENTE']

# Area -> variavel do .env com o ID da pasta da area no Drive
AREAS = {
    'PREVIDENCIARIO': 'DRIVE_PASTA_PREVIDENCIARIO',
    'CRIMINAL': 'DRIVE_PASTA_CRIMINAL',
    'FAMILIA E SUCESSOES': 'DRIVE_PASTA_FAMILIA_E_SUCESSOES',
    'BANCARIO': 'DRIVE_PASTA_BANCARIO',
    'CIVEL E CONSUMIDOR': 'DRIVE_PASTA_CIVEL_E_CONSUMIDOR',
}

# Apelidos aceitos na linha de comando / vindos da IA
_APELIDOS_AREA = {
    'PREV': 'PREVIDENCIARIO', 'INSS': 'PREVIDENCIARIO',
    'PENAL': 'CRIMINAL',
    'FAMILIA': 'FAMILIA E SUCESSOES', 'SUCESSOES': 'FAMILIA E SUCESSOES',
    'INVENTARIO': 'FAMILIA E SUCESSOES',
    'BANCO': 'BANCARIO',
    'CIVEL': 'CIVEL E CONSUMIDOR', 'CONSUMIDOR': 'CIVEL E CONSUMIDOR',
}


def _sem_acento(texto: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', texto)
                   if unicodedata.category(c) != 'Mn')


def normalizar_area(area: str) -> str:
    """'Previdenciário', 'prev', 'familia' -> chave de AREAS. Retorna '' se nao reconhecer."""
    chave = _sem_acento(area or '').upper().replace('/', ' E ').strip()
    chave = ' '.join(chave.split())
    if not chave:
        return ''
    for area in AREAS:
        if area in chave:
            return area
    palavras = chave.split()
    for apelido, destino in _APELIDOS_AREA.items():
        if apelido in palavras:
            return destino
    return ''


def pastas_das_areas() -> dict:
    """{area: id_da_pasta} so das areas configuradas no .env."""
    return {area: os.getenv(var, '') for area, var in AREAS.items() if os.getenv(var, '')}


def _q(texto: str) -> str:
    """Escapa aspas simples para a query do Drive."""
    return texto.replace('\\', '\\\\').replace("'", "\\'")


def autenticar_google():
    """
    Autentica com OAuth2 (conta pessoal do usuario) se oauth_credentials.json existir.
    Caso contrario, usa Service Account como fallback.
    """
    # Buscar credenciais na pasta config/ (raiz do projeto)
    project_root = os.path.join(os.path.dirname(__file__), '..')
    config_dir = os.path.join(project_root, 'config')
    oauth_creds_path = os.getenv("GOOGLE_OAUTH_CREDENTIALS", os.path.join(config_dir, "oauth_credentials.json"))
    token_path = os.path.join(config_dir, "token.json")
    sa_creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", os.path.join(config_dir, "credentials.json"))

    creds = None

    # Tenta OAuth2 primeiro (conta pessoal - usa cota do usuario)
    if os.path.exists(oauth_creds_path):
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("Renovando token de acesso...")
                creds.refresh(Request())
            else:
                print("Abrindo navegador para login com sua conta Google...")
                print("(isso so precisa ser feito uma vez)")
                flow = InstalledAppFlow.from_client_secrets_file(oauth_creds_path, SCOPES)
                creds = flow.run_local_server(port=0)

            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        print("Autenticado com sua conta Google pessoal!")

    # Fallback: Service Account
    elif os.path.exists(sa_creds_path):
        print("AVISO: Usando Service Account (cota limitada).")
        print("Para usar sua conta pessoal, configure oauth_credentials.json")
        creds = service_account.Credentials.from_service_account_file(
            sa_creds_path, scopes=SCOPES)
    else:
        print(f"ERRO: Nenhum arquivo de credenciais encontrado.")
        print("Coloque 'oauth_credentials.json' em config/ (ver docs/ONBOARDING.md, secao Google).")
        sys.exit(1)

    try:
        drive_service = build('drive', 'v3', credentials=creds)
        docs_service = build('docs', 'v1', credentials=creds)
        return drive_service, docs_service
    except Exception as e:
        print(f"ERRO DE AUTENTICACAO: {str(e)}")
        sys.exit(1)


def _listar_pastas(drive_service, q: str) -> list:
    results = drive_service.files().list(
        q=f"{q} and mimeType='{FOLDER_MIME}' and trashed=false",
        fields='files(id, name, parents, webViewLink)', pageSize=100).execute()
    return results.get('files', [])


def buscar_pasta_cliente(drive_service, nome_cliente: str) -> tuple:
    """
    Procura a pasta do cliente nas pastas de area do .env (nome exato, depois parcial).
    Se nao achar, tenta em todo o Drive (pastas antigas fora das areas).
    Retorna (id, nome, area) ou (None, None, None).
    """
    nome = nome_cliente.strip()
    if not nome:
        return None, None, None

    areas = pastas_das_areas()
    for modo in ('=', 'contains'):
        for area, pasta_area_id in areas.items():
            achadas = _listar_pastas(
                drive_service, f"'{pasta_area_id}' in parents and name {modo} '{_q(nome)}'")
            if achadas:
                return achadas[0]['id'], achadas[0]['name'], area

    for modo in ('=', 'contains'):
        achadas = _listar_pastas(drive_service, f"name {modo} '{_q(nome)}'")
        if achadas:
            return achadas[0]['id'], achadas[0]['name'], ''
    return None, None, None


def buscar_subpasta(drive_service, pasta_cliente_id: str, nome_subpasta: str):
    """ID da subpasta (ex.: 'ATOS INTERNOS') ou None."""
    achadas = _listar_pastas(
        drive_service, f"'{pasta_cliente_id}' in parents and name = '{_q(nome_subpasta)}'")
    return achadas[0]['id'] if achadas else None


DOCX_MIME = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def enviar_arquivo(drive_service, caminho: str, pasta_id: str, mimetype: str = DOCX_MIME) -> dict:
    """
    Sobe um arquivo local para a pasta do Drive SEM converter (o .docx continua .docx,
    com o timbrado intacto; o Drive abre para edicao e salva de volta em .docx).
    Se ja existir arquivo com o mesmo nome na pasta, atualiza o conteudo (nao duplica).
    Retorna {'id', 'webViewLink'}.
    """
    from googleapiclient.http import MediaFileUpload
    nome = os.path.basename(caminho)
    media = MediaFileUpload(caminho, mimetype=mimetype, resumable=False)
    existentes = drive_service.files().list(
        q=f"'{pasta_id}' in parents and name = '{_q(nome)}' and trashed=false",
        fields='files(id)', pageSize=1).execute().get('files', [])
    if existentes:
        return drive_service.files().update(
            fileId=existentes[0]['id'], media_body=media, fields='id, webViewLink').execute()
    return drive_service.files().create(
        body={'name': nome, 'parents': [pasta_id]}, media_body=media,
        fields='id, webViewLink').execute()


def baixar_arquivo(drive_service, file_id: str, destino: str) -> str:
    """Baixa o arquivo do Drive (versao atual, ja com a revisao do advogado) para destino."""
    import io
    from googleapiclient.http import MediaIoBaseDownload
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, drive_service.files().get_media(fileId=file_id))
    feito = False
    while not feito:
        _, feito = dl.next_chunk()
    with open(destino, 'wb') as f:
        f.write(buf.getvalue())
    return destino


def link_pasta(drive_service, pasta_id: str) -> str:
    return drive_service.files().get(fileId=pasta_id, fields='webViewLink').execute().get(
        'webViewLink', '')


def duplicar_template(drive_service, template_id: str, nome_cliente: str, data: str, pasta_destino_id: str = None) -> str:
    """
    Duplica o arquivo de template e o renomeia, mantendo na mesma pasta original
    ou enviando para uma pasta destino específica.
    """
    print("Gerando cópia do Template Ficha no Google Drive...")

    try:
        nome_arquivo = f"{nome_cliente} - Ficha Cliente - {data}"
        body = {
            'name': nome_arquivo,
            'mimeType': 'application/vnd.google-apps.document'
        }

        if pasta_destino_id:
            body['parents'] = [pasta_destino_id]
        else:
            arquivo_origem = drive_service.files().get(fileId=template_id, fields='parents').execute()
            if 'parents' in arquivo_origem:
                body['parents'] = arquivo_origem['parents']

        copia = drive_service.files().copy(
            fileId=template_id, body=body).execute()

        return copia.get('id')

    except HttpError as error:
        print(f"ERRO DE API DRIVE: Falha ao duplicar o arquivo.")
        print("A conta autenticada tem acesso ao template e a pasta destino?")
        print(f"Detalhes técnicos: {error}")
        sys.exit(1)


def criar_pasta_cliente(drive_service, nome_cliente: str, area: str) -> str:
    """
    Garante {PASTA DA AREA}/{NOME DO CLIENTE}/ com as 3 subpastas padrao.
    Se a pasta do cliente ja existir na area, reaproveita (nao duplica) e so cria
    as subpastas que faltarem. Retorna o ID da pasta do cliente, ou None.
    """
    area_norm = normalizar_area(area)
    if not area_norm:
        print(f"ERRO: area '{area}' nao reconhecida. Use uma de: {', '.join(AREAS)}.")
        return None
    pasta_area_id = os.getenv(AREAS[area_norm], '')
    if not pasta_area_id:
        print(f"ERRO: {AREAS[area_norm]} nao configurado no config/.env (ID da pasta da area no Drive).")
        return None

    nome_pasta = nome_cliente.strip().upper()

    try:
        existentes = _listar_pastas(
            drive_service, f"'{pasta_area_id}' in parents and name = '{_q(nome_pasta)}'")
        if existentes:
            pasta_id = existentes[0]['id']
            pasta_link = existentes[0].get('webViewLink', '')
            print(f"Pasta do cliente ja existe em {area_norm}: {nome_pasta} (reaproveitada)")
        else:
            print(f"Criando pasta do cliente em {area_norm}: {nome_pasta}...")
            pasta_cliente = drive_service.files().create(body={
                'name': nome_pasta,
                'mimeType': FOLDER_MIME,
                'parents': [pasta_area_id]
            }, fields='id, webViewLink').execute()
            pasta_id = pasta_cliente['id']
            pasta_link = pasta_cliente.get('webViewLink', '')

        for sub in SUBPASTAS_CLIENTE:
            if buscar_subpasta(drive_service, pasta_id, sub):
                continue
            drive_service.files().create(body={
                'name': sub,
                'mimeType': FOLDER_MIME,
                'parents': [pasta_id]
            }).execute()
            print(f"   Subpasta criada: {sub}")

        print(f"Link: {pasta_link}")
        return pasta_id

    except HttpError as error:
        print(f"ERRO ao criar pasta do cliente: {error}")
        return None


def buscar_proximo_contrato(drive_service, nome_cliente="", empresa="", area=""):
    """
    Busca o proximo numero sequencial de contrato na planilha de controle
    e registra o novo contrato na proxima linha.
    """
    import openpyxl
    import io
    from datetime import datetime
    from googleapiclient.http import MediaInMemoryUpload

    planilha_id = os.getenv("GOOGLE_PLANILHA_CONTRATOS", "")
    if not planilha_id:
        print("   Aviso: GOOGLE_PLANILHA_CONTRATOS nao configurado; pulando numeracao de contrato.")
        return ""

    ano_atual = str(datetime.now().year)
    aba_contratos = os.getenv("GOOGLE_ABA_CONTRATOS", "") or f"Contratos {ano_atual}"

    try:
        content = drive_service.files().get_media(fileId=planilha_id).execute()
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb[aba_contratos]

        # Encontrar ultimo numero e ultima linha preenchida
        sufixo_ano = f'/{ano_atual}'
        ultimo = 0
        ultima_linha = 4
        for row in range(5, ws.max_row + 1):
            val = str(ws.cell(row=row, column=8).value or '')
            if sufixo_ano in val:
                try:
                    num = int(val.split('/')[0])
                    if num > ultimo:
                        ultimo = num
                        ultima_linha = row
                except:
                    pass

        proximo = ultimo + 1
        nova_linha = ultima_linha + 1
        numero_contrato = f"{proximo}/{ano_atual}"

        # Preencher nova linha no padrao
        ws.cell(row=nova_linha, column=4, value=nome_cliente.upper())  # D: Nome
        ws.cell(row=nova_linha, column=6, value=datetime.now())  # F: Data cadastro
        ws.cell(row=nova_linha, column=8, value=numero_contrato)  # H: CT.
        ws.cell(row=nova_linha, column=9, value=empresa.upper())  # I: Parte contraria
        ws.cell(row=nova_linha, column=10, value=area)  # J: Area

        # Salvar e fazer upload de volta
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        media = MediaInMemoryUpload(
            buffer.read(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        drive_service.files().update(
            fileId=planilha_id,
            media_body=media
        ).execute()

        print(f"   Planilha atualizada: linha {nova_linha} - {nome_cliente.upper()} - {numero_contrato}")
        return f"CT. {numero_contrato}"

    except Exception as e:
        print(f"   Aviso: Nao conseguiu atualizar planilha: {e}")
        return ""


def gerar_documentos_cliente(drive_service, docs_service, nome_cliente: str, dados: dict,
                             pasta_cliente_id: str = None, area: str = ""):
    """
    Gera Contrato, Procuracao e Declaracao de Hipossuficiencia
    a partir dos templates (Google Docs com chaves {{...}}), preenchendo com os dados do cliente.

    Modelos vem do .env: GOOGLE_TEMPLATE_CONTRATO / _PROCURACAO / _DECLARACAO.
    Destino: GOOGLE_PASTA_<DOC> se configurada; senao, 'PASTA DO CLIENTE' da pasta do cliente.
    Dado que falta NAO e inventado: a chave {{...}} fica no documento para o revisor preencher.
    """
    from datetime import datetime

    templates = {
        'Contrato de Honorarios': {
            'template_id': os.getenv("GOOGLE_TEMPLATE_CONTRATO", ""),
            'pasta_id': os.getenv("GOOGLE_PASTA_CONTRATO", ""),
        },
        'Procuracao': {
            'template_id': os.getenv("GOOGLE_TEMPLATE_PROCURACAO", ""),
            'pasta_id': os.getenv("GOOGLE_PASTA_PROCURACAO", ""),
        },
        'Declaracao de Hipossuficiencia': {
            'template_id': os.getenv("GOOGLE_TEMPLATE_DECLARACAO", ""),
            'pasta_id': os.getenv("GOOGLE_PASTA_DECLARACAO", ""),
        },
    }

    pasta_padrao = None
    if pasta_cliente_id:
        pasta_padrao = buscar_subpasta(drive_service, pasta_cliente_id, 'PASTA DO CLIENTE') or pasta_cliente_id

    meses = ['Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho', 'Julho',
             'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    agora = datetime.now()
    hoje = f"{agora.day:02d} de {meses[agora.month - 1]} de {agora.year}"

    cidade_foro = os.getenv('CIDADE_FORO', 'Iúna/ES')
    data_local = f"{cidade_foro}, {hoje}"

    # Buscar numero sequencial do contrato
    empresa = dados.get('qual_empresa', dados.get('empresa', ''))
    numero_contrato = buscar_proximo_contrato(drive_service, nome_cliente, empresa, area)
    print(f"   Numero do contrato: {numero_contrato}")

    # Tratar endereco: remover prefixo de logradouro (Rua, Av, Avenida, etc.)
    # pois o template ja contem "Rua {{Endereco}}" / "residente ... a Rua {{Endereco}}"
    import re
    endereco_raw = dados.get('endereco', '')
    endereco_limpo = re.sub(r'^(Rua|Av\.?|Avenida|Alameda|Travessa|Estrada|Rodovia|R\.)\s+', '', endereco_raw, flags=re.IGNORECASE).strip()

    # Mapeamento das chaves dos templates para os dados extraidos
    mapa_chaves = {
        '{{Nome do cliente}}': dados.get('nome', ''),
        '{{Nome completo}}': dados.get('nome', ''),
        '{{CPF do cliente}}': dados.get('cpf', ''),
        '{{CPF}}': dados.get('cpf', ''),
        '{{RG do cliente}}': dados.get('rg', ''),
        '{{RG}}': dados.get('rg', ''),
        '{{Nacionalidade do cliente}}': dados.get('nacionalidade', ''),
        '{{Nacionalidade}}': dados.get('nacionalidade', ''),
        '{{Estado civil do cliente}}': dados.get('estado_civil', ''),
        '{{Estado Civil}}': dados.get('estado_civil', ''),
        '{{Profissão do cliente}}': dados.get('profissao', ''),
        '{{Profissão}}': dados.get('profissao', ''),
        '{{ENDEREÇO DO CLIENTE}}': endereco_limpo,
        '{{Endereço}}': endereco_limpo,
        '{{Bairro}}': dados.get('bairro', ''),
        '{{Cidade Estado}}': dados.get('cidade_estado', ''),
        '{{CEP}}': dados.get('cep', ''),
        '{{telefone do cliente}}': dados.get('telefone', ''),
        '{{e-mail do cliente}}': dados.get('email', ''),
        '{{NOME DA AÇÃO}}': dados.get('tipo_acao', ''),
        '{{NOME DA EMPRESA}}': dados.get('qual_empresa', ''),
        '{{nome da empresa}}': dados.get('qual_empresa', ''),
        '{{Data e local de hoje}}': data_local,
        '{{data e cidade}}': data_local,
        '{{ Número sequencial de contrato  EX: CT. N°.182/2024}}': numero_contrato,
    }

    docs_gerados = []

    for doc_nome, config in templates.items():
        if not config['template_id']:
            print(f"   Pulando {doc_nome}: modelo nao configurado no .env.")
            continue
        destino = config['pasta_id'] or pasta_padrao
        print(f"   Gerando: {nome_cliente} - {doc_nome}...")

        try:
            nome_arquivo = f"{nome_cliente} - {doc_nome}"
            body = {'name': nome_arquivo, 'mimeType': 'application/vnd.google-apps.document'}
            if destino:
                body['parents'] = [destino]
            copia = drive_service.files().copy(
                fileId=config['template_id'], body=body).execute()

            doc_id = copia['id']

            # Preencher as chaves
            requests = []
            for chave, valor in mapa_chaves.items():
                if valor:
                    requests.append({
                        'replaceAllText': {
                            'containsText': {'text': chave, 'matchCase': False},
                            'replaceText': valor
                        }
                    })

            if requests:
                docs_service.documents().batchUpdate(
                    documentId=doc_id, body={'requests': requests}).execute()

            docs_gerados.append({'nome': nome_arquivo, 'id': doc_id})
            print(f"   Pronto: {nome_arquivo}")

        except HttpError as error:
            print(f"   ERRO ao gerar {doc_nome}: {error}")

    return docs_gerados


def preencher_documento(docs_service, document_id: str, dados: dict):
    """
    Edita um documento Google via Requests de BatchUpdate substituindo os placeholders
    {{CHAVE}} com os valores recém extraídos pela IA no dicionário.
    """
    print("Inserindo Fatos e Detalhes no novo documento gerado...")

    requests = []

    # Mapeamento do dicionário da IA com as Tags reais
    # Note que se a IA botou "FATOS" e "NOME_CLIENTE", vamos buscar "{{FATOS}}" no doc.
    for chave, valor in dados.items():
        if not isinstance(valor, str):
            # Se vier uma lista/dicionário maluco, converte
            valor = str(valor)

        requests.append({
            'replaceAllText': {
                'containsText': {
                    'text': f"{{{{{chave}}}}}",
                    'matchCase': True
                },
                'replaceText': valor
            }
        })

    try:
        resultado = docs_service.documents().batchUpdate(
            documentId=document_id, body={'requests': requests}).execute()
        print("Documento finalizado com Sucesso!!")

    except HttpError as error:
        print(f"ERRO DE API DOCS: Houve um erro ao formatar o texto do arquivo.")
        print(f"Detalhes: {error}")
        sys.exit(1)
