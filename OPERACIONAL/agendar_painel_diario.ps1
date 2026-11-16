# Agenda no Windows o tratamento de publicacoes + painel do Dr. Welington.
#   - todo dia as 07:00 (se o notebook estiver desligado, roda assim que ligar);
#   - e ao entrar no Windows (se a rotina do dia ja rodou, so abre o painel).
# Uso (PowerShell, na pasta do repositorio):
#   powershell -ExecutionPolicy Bypass -File OPERACIONAL\agendar_painel_diario.ps1            # lanca no ADVBOX
#   powershell -ExecutionPolicy Bypass -File OPERACIONAL\agendar_painel_diario.ps1 -Simulacao # so painel, sem ADVBOX
#   powershell -ExecutionPolicy Bypass -File OPERACIONAL\agendar_painel_diario.ps1 -Remover
param([switch]$Simulacao, [switch]$Remover, [string]$Hora = '07:00')

$Nome = 'VALOIS - Painel do Dr. Welington (publicacoes)'
if ($Remover) {
    Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
    Write-Output "Tarefa removida: $Nome"
    return
}

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
# Python real (o de WindowsApps e so um atalho); pythonw = sem janela preta
$Py = (& python -c "import sys; print(sys.executable)").Trim() -replace 'python\.exe$', 'pythonw.exe'
if (-not (Test-Path $Py)) { $Py = (Get-Command pythonw.exe).Source }
$Script = Join-Path $Repo 'OPERACIONAL\tratamento_publicacoes.py'
$Argumentos = "`"$Script`" diario --abrir"
if (-not $Simulacao) { $Argumentos += ' --executar' }

$Acao = New-ScheduledTaskAction -Execute $Py -Argument $Argumentos -WorkingDirectory $Repo
$Gatilhos = @(
    (New-ScheduledTaskTrigger -Daily -At $Hora),
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME")
)
$Gatilhos[1].Delay = 'PT1M'   # 1 minuto depois do login (rede e navegador prontos)
$Config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
$Quem = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $Nome -Action $Acao -Trigger $Gatilhos -Settings $Config -Principal $Quem `
    -Description 'Trata as publicacoes do Sync (POP 10), lanca tarefas no ADVBOX e abre o painel diario do Dr. Welington.' `
    -Force | Out-Null
$Modo = if ($Simulacao) { 'SIMULACAO (nada vai para o ADVBOX)' } else { 'EXECUCAO (lanca tarefas no ADVBOX)' }
Write-Output "Agendado: $Nome | todo dia $Hora e ao entrar no Windows | $Modo"
Write-Output "Python: $Py"
