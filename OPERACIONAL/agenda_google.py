"""
Google Agenda (opcional) para os prazos fatais do tratamento de publicacoes.

Usa token proprio (config/token_agenda.json), separado do token do Drive, para nao
derrubar o login que ja funciona. Ativar: AGENDA_GOOGLE=1 no config/.env e rodar uma vez
  python OPERACIONAL/tratamento_publicacoes.py autorizar-agenda
(abre o navegador para o Dr. Welington autorizar). Calendario: AGENDA_GOOGLE_CALENDARIO
(padrao 'primary').
"""
import os
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TOKEN = RAIZ / 'config' / 'token_agenda.json'
ESCOPOS = ['https://www.googleapis.com/auth/calendar.events']


def _credenciais(interativo=False):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials.from_authorized_user_file(str(TOKEN), ESCOPOS) if TOKEN.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json())
    if creds and creds.valid:
        return creds
    if not interativo:
        raise RuntimeError('Google Agenda sem autorizacao: rodar "tratamento_publicacoes.py autorizar-agenda"')
    from google_auth_oauthlib.flow import InstalledAppFlow
    segredo = os.getenv('GOOGLE_OAUTH_CREDENTIALS') or str(RAIZ / 'config' / 'oauth_credentials.json')
    creds = InstalledAppFlow.from_client_secrets_file(segredo, ESCOPOS).run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    return creds


def autorizar():
    _credenciais(interativo=True)
    return f'Google Agenda autorizado ({TOKEN.name}).'


def criar_evento_dia(dia, titulo, descricao, chave):
    """Evento de dia inteiro. 'chave' evita duplicar (procura por privateExtendedProperty)."""
    from googleapiclient.discovery import build
    servico = build('calendar', 'v3', credentials=_credenciais(), cache_discovery=False)
    cal = os.getenv('AGENDA_GOOGLE_CALENDARIO', 'primary')
    existentes = servico.events().list(calendarId=cal, privateExtendedProperty=f'valois={chave}',
                                       maxResults=1).execute().get('items', [])
    if existentes:
        return f"ja existia ({existentes[0].get('htmlLink', '')})"
    ev = servico.events().insert(calendarId=cal, body={
        'summary': titulo, 'description': descricao,
        'start': {'date': str(dia)}, 'end': {'date': str(dia + timedelta(days=1))},
        'extendedProperties': {'private': {'valois': chave}},
        'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 24 * 60 * 3}]},
    }).execute()
    return f"criado ({ev.get('htmlLink', '')})"
