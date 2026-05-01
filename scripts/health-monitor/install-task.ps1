<#
.SYNOPSIS
  Register a Windows Task Scheduler entry that runs monitor.py every minute.

.DESCRIPTION
  Idempotent: if a task with the same name already exists, it's recreated
  with the latest configuration so re-running picks up code/path changes.
#>

[CmdletBinding()]
param(
    [string]$TaskName = 'rtk-health-monitor',
    [string]$Python = 'D:\mercury\.venv\Scripts\python.exe',
    [string]$Script = 'D:\mercury\scripts\health-monitor\monitor.py'
)

$ErrorActionPreference = 'Stop'

# Self-elevate
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '[install-task] Not elevated. Re-launching as Administrator...' -ForegroundColor Yellow
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath) -Verb RunAs
    exit
}

if (-not (Test-Path $Python)) { throw "Python interpreter not found at $Python" }
if (-not (Test-Path $Script)) { throw "monitor.py not found at $Script" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory (Split-Path $Script -Parent)

# Repeat every minute, indefinitely. (Trigger fires once at registration; the
# repetition pattern handles the every-minute cadence.)
$start = (Get-Date).AddMinutes(1)
$trigger = New-ScheduledTaskTrigger -Once -At $start
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $start -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration ([TimeSpan]::MaxValue)).Repetition

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType InteractiveToken -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

# Recreate idempotently
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "[install-task] Removing existing $TaskName..." -ForegroundColor DarkGray
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description 'rtk-* health monitor: probes each service, restarts on failure, alerts Discord on recovery failure' | Out-Null

Write-Host "[install-task] Registered $TaskName (every 1 minute)." -ForegroundColor Green
Get-ScheduledTask -TaskName $TaskName | Format-Table TaskName, State, Author -AutoSize | Out-String | Write-Host
