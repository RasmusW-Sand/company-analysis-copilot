# setup_scheduler.ps1
#
# Oppretter en Windows Task Scheduler-oppgave som kjoerer watchlist-monitoren
# daglig kl. 08:00.
#
# KRAV: Kjor PowerShell som administrator.
#
# BRUK:
#   .\setup_scheduler.ps1
#
# ANDRE NYTTIGE KOMMANDOER:
#   Sjekk at oppgaven ble opprettet:
#     Get-ScheduledTask -TaskName "CompanyAnalysisCopilot-Monitor"
#
#   Se neste planlagte kjoretid:
#     Get-ScheduledTask -TaskName "CompanyAnalysisCopilot-Monitor" | Get-ScheduledTaskInfo
#
#   Kjor manuelt (for testing):
#     Start-ScheduledTask -TaskName "CompanyAnalysisCopilot-Monitor"
#
#   Slett oppgaven:
#     Unregister-ScheduledTask -TaskName "CompanyAnalysisCopilot-Monitor" -Confirm:$false

$taskName = "CompanyAnalysisCopilot-Monitor"
$batPath  = "C:\Programmering\Finans\AI agents for market research\run_monitor.bat"

# Kjoer run_monitor.bat via cmd.exe slik at .bat-filen fungerer korrekt
$action = New-ScheduledTaskAction `
    -Execute  "cmd.exe" `
    -Argument "/c `"$batPath`""

# Daglig kl. 08:00
$trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# Registrer oppgaven. Krever administratorrettigheter.
Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -RunLevel  Highest `
    -Force

$info = Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo
Write-Host ""
Write-Host "Oppgave '$taskName' opprettet." -ForegroundColor Green
Write-Host "Neste kjoretid: $($info.NextRunTime)"
Write-Host ""
Write-Host "For a kjore manuelt naa:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName `"$taskName`""
