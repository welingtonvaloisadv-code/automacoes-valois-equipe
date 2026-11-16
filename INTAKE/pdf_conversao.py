"""
Converte .docx em PDF para envio ao ZapSign, preservando o timbrado e a fonte Segoe UI.

Ordem: Microsoft Word (maquina do escritorio, via PowerShell/COM, uma sessao para todos os
arquivos) -> LibreOffice. Sem nenhum dos dois, levanta erro: nao mandamos o .docx cru para
o ZapSign porque a conversao do lado deles troca a fonte e pode desalinhar o timbrado.
"""
import os
import shutil
import subprocess

TIMEOUT = 300

# Arquivos chegam por variavel de ambiente (caminhos com acento/espaco sem dor de aspas).
_PS_WORD = r"""
$ErrorActionPreference = 'Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    foreach ($par in ($env:CONVERTER -split '\|')) {
        $docx, $pdf = $par -split '>'
        $doc = $word.Documents.Open($docx, $false, $true, $false)
        $doc.ExportAsFixedFormat($pdf, 17)
        $doc.Close($false)
    }
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
"""


def _pids_word():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq WINWORD.EXE', '/FO', 'CSV', '/NH'],
                       capture_output=True, text=True)
    return {linha.split('","')[1] for linha in r.stdout.splitlines() if 'WINWORD' in linha}


def _via_word(pares):
    if os.name != 'nt':
        return False
    antes = _pids_word()
    env = dict(os.environ, CONVERTER='|'.join(f'{d}>{p}' for d, p in pares))
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', _PS_WORD],
                           env=env, capture_output=True, text=True, timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        # Word invisivel preso em algum dialogo: fecha so o que esta conversao abriu.
        for pid in _pids_word() - antes:
            subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
        return False
    return r.returncode == 0 and all(os.path.exists(p) for _, p in pares)


def _soffice():
    for c in (shutil.which('soffice'), r'C:\Program Files\LibreOffice\program\soffice.exe',
              '/usr/bin/soffice', '/Applications/LibreOffice.app/Contents/MacOS/soffice'):
        if c and os.path.exists(c):
            return c
    return None


def _via_libreoffice(pares):
    soffice = _soffice()
    if not soffice:
        return False
    for docx, pdf in pares:
        pasta = os.path.dirname(pdf)
        subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', pasta, docx],
                       capture_output=True, timeout=TIMEOUT)
        gerado = os.path.join(pasta, os.path.splitext(os.path.basename(docx))[0] + '.pdf')
        if gerado != pdf and os.path.exists(gerado):
            os.replace(gerado, pdf)
    return all(os.path.exists(p) for _, p in pares)


def docx_para_pdf(arquivos):
    """
    arquivos: lista de caminhos .docx. Retorna {docx: pdf} (PDF ao lado do .docx).
    Levanta RuntimeError se nao conseguir converter todos.
    """
    pares = [(os.path.abspath(d), os.path.splitext(os.path.abspath(d))[0] + '.pdf')
             for d in arquivos]
    if not pares:
        return {}
    for _, pdf in pares:
        if os.path.exists(pdf):
            os.remove(pdf)
    for conversor in (_via_word, _via_libreoffice):
        try:
            if conversor(pares):
                return {d: p for d, p in zip(arquivos, (p for _, p in pares))}
        except (OSError, subprocess.SubprocessError):
            continue
    raise RuntimeError('Nao consegui converter os documentos em PDF. Precisa do Microsoft Word '
                       'ou do LibreOffice instalado nesta maquina (e o Word sem janela aberta '
                       'pedindo ativacao/login).')
