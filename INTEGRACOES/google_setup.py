"""
Conferencia da integracao Google Drive - Welington Valois Advogados Associados.

    python INTEGRACOES/google_setup.py

1a vez: abre o navegador para login na conta Google do escritorio e grava
config/token.json. Depois so confere, SEM criar nem alterar nada no Drive:
  - qual conta esta autenticada
  - se cada pasta/modelo configurado no config/.env existe e esta acessivel
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'config', '.env'))

from googleapiclient.errors import HttpError
from google_integration import autenticar_google, AREAS

IDS_OPCIONAIS = [
    'GOOGLE_TEMPLATE_ID',
    'GOOGLE_PLANILHA_CONTRATOS',
    'GOOGLE_TEMPLATE_CONTRATO', 'GOOGLE_TEMPLATE_PROCURACAO', 'GOOGLE_TEMPLATE_DECLARACAO',
    'GOOGLE_PASTA_CONTRATO', 'GOOGLE_PASTA_PROCURACAO', 'GOOGLE_PASTA_DECLARACAO',
    'DRIVE_PASTA_FECHAMENTO_ID', 'DRIVE_PASTA_FINANCEIRO_ID',
    'DRIVE_PLANILHA_HISTORICO_ID', 'DRIVE_PLANILHA_RESULTADO_ID', 'DRIVE_PASTA_CLIENTES_ID',
]


def conferir(drive, var: str) -> bool:
    file_id = os.getenv(var, '')
    if not file_id:
        print(f"  [ -- ] {var:32} (vazio)")
        return False
    try:
        f = drive.files().get(fileId=file_id, fields='name, mimeType, trashed',
                              supportsAllDrives=True).execute()
        tipo = 'pasta' if f['mimeType'].endswith('folder') else f['mimeType'].split('.')[-1]
        lixeira = '  <- NA LIXEIRA' if f.get('trashed') else ''
        print(f"  [ OK ] {var:32} {f['name']} ({tipo}){lixeira}")
        return not f.get('trashed')
    except HttpError as e:
        print(f"  [ERRO] {var:32} {file_id} -> {e.status_code} (nao existe ou sem acesso)")
        return False


def main():
    drive, _docs = autenticar_google()
    user = drive.about().get(fields='user(emailAddress, displayName)').execute()['user']
    print(f"\nConta: {user.get('displayName', '')} <{user['emailAddress']}>")

    print("\nPastas de area (onde nascem as pastas de cliente):")
    areas_ok = sum(conferir(drive, var) for var in AREAS.values())

    print("\nModelos, planilhas e pastas auxiliares:")
    for var in IDS_OPCIONAIS:
        conferir(drive, var)

    print(f"\n{areas_ok}/{len(AREAS)} pastas de area acessiveis.")
    if areas_ok == 0:
        print("Preencha DRIVE_PASTA_<AREA> no config/.env (o ID e o final da URL da pasta).")


if __name__ == '__main__':
    main()
