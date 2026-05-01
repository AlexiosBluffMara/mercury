<#
.SYNOPSIS
  Register ensure-running.ps1 as a Windows Task Scheduler task at user logon.

.DESCRIPTION
  Creates a task named "RTK Stack - Ensure Running" that fires at logon for
  the current user. Does NOT require admin (runs as current user).
  Delays 30 seconds after logon to let the network interface settle.

  Run this script once; the task persists across reboots.

.NOTES
  To remove: Unregister-ScheduledTask -TaskName "RTK Stack - Ensure Running" -Confirm:$false
#>

$ErrorActionPreference = 'Stop'

$taskName   = 'RTK Stack - Ensure Running'
$scriptPath = 'D:\mercury\scripts\windows-services\ensure-running.ps1'
$logPath    = Join-Path $env:USERPROFILE '.mercury\logs\startup-task.log'

# Create log dir if needed
$logDir = Split-Path $logPath -Parent
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# Build the scheduled task
$action  = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`" *> `"$logPath`""

$trigger = New-ScheduledTaskTrigger -AtLogOn
$trigger.Delay = 'PT30S'   # 30-second delay so networking is up

$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

# Unregister existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask `
    -TaskName  $taskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "[register-startup-task] Task '$taskName' registered." -ForegroundColor Green
Write-Host "  Fires: at logon, 30s delay"
Write-Host "  Logs:  $logPath"
Write-Host ''
Write-Host 'To test immediately without rebooting:'
Write-Host "  Start-ScheduledTask -TaskName '$taskName'"
Write-Host ''
Write-Host 'To uninstall:'
Write-Host "  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
