<#
.SYNOPSIS
  Cleanly remove the rtk-* Windows services. Idempotent.

.DESCRIPTION
  Stops each service (waits up to 30s), then deletes via NSSM. Leaves the
  log files in place so post-mortem inspection is still possible.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

# Self-elevate
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '[uninstall-services] Not elevated. Re-launching as Administrator...' -ForegroundColor Yellow
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath) -Verb RunAs
    exit
}

$nssm = (Get-Command nssm -ErrorAction SilentlyContinue).Source
if (-not $nssm) {
    $candidate = 'C:\Program Files\nssm\nssm.exe'
    if (Test-Path $candidate) { $nssm = $candidate }
    else { throw 'NSSM not on PATH and not at C:\Program Files\nssm\nssm.exe. Nothing to do.' }
}

$services = @('rtk-mercury-gateway','rtk-cortex-webapp','rtk-cloudflared')

foreach ($svc in $services) {
    if (-not (Get-Service -Name $svc -ErrorAction SilentlyContinue)) {
        Write-Host "[uninstall-services] $svc not installed -- skipping." -ForegroundColor DarkGray
        continue
    }

    Write-Host "[uninstall-services] Stopping $svc..." -ForegroundColor Cyan
    try {
        Stop-Service -Name $svc -Force -ErrorAction Stop
    } catch {
        Write-Host "  Stop-Service failed: $($_.Exception.Message). Continuing." -ForegroundColor Yellow
    }

    # Wait up to 30s for STOPPED
    $deadline = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $deadline) {
        $s = Get-Service -Name $svc -ErrorAction SilentlyContinue
        if (-not $s -or $s.Status -eq 'Stopped') { break }
        Start-Sleep -Milliseconds 500
    }

    Write-Host "[uninstall-services] Removing $svc..." -ForegroundColor Cyan
    & $nssm remove $svc confirm | Out-Null
}

Write-Host ''
Write-Host '=== Remaining rtk-* services ===' -ForegroundColor Green
$leftover = Get-Service -Name 'rtk-*' -ErrorAction SilentlyContinue
if (-not $leftover) {
    Write-Host '(none)' -ForegroundColor Green
} else {
    $leftover | Format-Table Name, Status, StartType -AutoSize | Out-String | Write-Host
}
