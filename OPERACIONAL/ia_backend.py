"""
Camada unica de IA para as automacoes do escritorio.

Ordem de uso:
  1. ANTHROPIC_API_KEY no ambiente/config/.env -> SDK oficial (anthropic), Opus 5.5.
  2. Sem chave -> Claude Code instalado na maquina (claude.exe -p), que usa o login
     da assinatura do escritorio. E o caminho padrao hoje (a maquina nao tem chave de API).

gerar(prompt, system='') -> str        texto livre (pecas)
gerar_json(prompt, system='') -> dict  resposta JSON (classificacao)
"""
import os
import re
import json
import glob
import shutil
import tempfile
import subprocess
import logging

log = logging.getLogger('operacional.ia')

MODELO = os.getenv('IA_MODELO', 'claude-opus-5-5')
FERRAMENTAS_BLOQUEADAS = ('Bash,Edit,Write,Read,Glob,Grep,WebFetch,WebSearch,NotebookEdit,'
                          'Agent,Task,TodoWrite,PowerShell')


class ErroIA(RuntimeError):
    pass


def _claude_cli():
    """Caminho do claude.exe: CLAUDE_CLI, PATH ou o binario da extensao do VS Code (mais novo)."""
    if os.getenv('CLAUDE_CLI') and os.path.exists(os.getenv('CLAUDE_CLI')):
        return os.getenv('CLAUDE_CLI')
    achado = shutil.which('claude')
    if achado:
        return achado
    padrao = os.path.join(os.path.expanduser('~'), '.vscode', 'extensions',
                          'anthropic.claude-code-*', 'resources', 'native-binary', 'claude.exe')
    candidatos = sorted(glob.glob(padrao), key=os.path.getmtime, reverse=True)
    return candidatos[0] if candidatos else None


def _via_api(prompt, system, effort):
    import anthropic
    client = anthropic.Anthropic(timeout=1800.0)
    kwargs = dict(model=MODELO, max_tokens=64000,
                  messages=[{'role': 'user', 'content': prompt}],
                  output_config={'effort': effort},
                  betas=['server-side-fallback-2026-07-01'], fallbacks='default')
    if system:
        kwargs['system'] = system
    with client.beta.messages.stream(**kwargs) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == 'refusal':
        raise ErroIA('a IA recusou o pedido (refusal)')
    return ''.join(b.text for b in msg.content if b.type == 'text')


def _via_cli(prompt, system, effort):
    exe = _claude_cli()
    if not exe:
        raise ErroIA('sem ANTHROPIC_API_KEY e sem Claude Code instalado (claude.exe)')
    texto = (f'<instrucoes_do_sistema>\n{system}\n</instrucoes_do_sistema>\n\n{prompt}'
             if system else prompt)
    cmd = [exe, '-p', '--output-format', 'json', '--model', MODELO,
           '--disallowedTools', FERRAMENTAS_BLOQUEADAS]
    env = dict(os.environ)
    # pasta neutra: nao carrega o CLAUDE.md do repositorio a cada chamada (o contexto vai no prompt)
    with tempfile.TemporaryDirectory(prefix='valois_ia_') as pasta:
        try:
            r = subprocess.run(cmd, input=texto, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', cwd=pasta,
                               timeout=1800, env=env,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except subprocess.TimeoutExpired:
            raise ErroIA('a IA passou de 30 minutos sem responder')
    saida = (r.stdout or '').strip()
    linha = next((l for l in reversed(saida.splitlines()) if l.startswith('{')), '')
    try:
        dados = json.loads(linha)
    except ValueError:
        raise ErroIA(f'resposta inesperada do Claude Code: {(r.stderr or saida)[:300]}')
    if dados.get('is_error') or dados.get('subtype') != 'success':
        raise ErroIA(f"Claude Code: {dados.get('result') or dados.get('subtype')}")
    return dados.get('result', '')


def gerar(prompt, system='', effort='high'):
    if os.getenv('ANTHROPIC_API_KEY'):
        return _via_api(prompt, system, effort)
    return _via_cli(prompt, system, effort)


def gerar_json(prompt, system='', effort='high'):
    texto = gerar(prompt + '\n\nResponda SOMENTE com o objeto JSON, sem texto antes ou depois.',
                  system, effort)
    bloco = re.search(r'\{.*\}', texto, re.S)
    if not bloco:
        raise ErroIA(f'a IA nao devolveu JSON: {texto[:200]}')
    try:
        return json.loads(bloco.group(0))
    except ValueError as e:
        raise ErroIA(f'JSON invalido da IA: {e}')
