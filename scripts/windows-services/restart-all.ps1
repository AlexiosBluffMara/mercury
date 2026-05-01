<#
.SYNOPSIS
  Restart all three rtk-* services in dependency order.

.DESCRIPTION
  Order: cloudflared (tunnel must be up first) -> cortex-webapp -> mercury-gateway.
  Useful after a config change (e.g. ~/.cloudflared/config.yml edit, .env update,
  cortex code pull) where you don't want to bounce the whole machine.
#>

[CmdletBinding()]
param(
    [int]$WaitSecondsBetween = 3
)

$ErrorActionPreference = 'Continue'

# Self-elevate (Restart-Service needs it for these)
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '[restart-all] Not elevated. Re-launching as Administrator...' -ForegroundColor Yellow
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath) -Verb RunAs
    exit
}

$ordered = @('rtk-cloudflared','rtk-cortex-webapp','rtk-mercury-gateway')

foreach ($svc in $ordered) {
    $existing = Get-Service -Name $svc -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "[restart-all] $svc not installed -- skipping." -ForegroundColor DarkGray
        continue
    }

    Write-Host "[restart-all] Restarting $svc..." -ForegroundColor Cyan
    try {
        Restart-Service -Name $svc -Force -ErrorAction Stop
    } catch {
        Write-Host "  Restart-Service failed: $($_.Exception.Message)" -ForegroundColor Red
        continue
    }
    Start-Sleep -Seconds $WaitSecondsBetween
}

Write-Host ''
Write-Host '=== Status after restart ===' -ForegroundColor Green
Get-Service -Name 'rtk-*' | Format-Table Name, Status, StartType -AutoSize | Out-String | Write-Host
