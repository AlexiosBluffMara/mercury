<#
.SYNOPSIS
  Ensure all RTK stack processes are running. No admin required.

.DESCRIPTION
  Checks cloudflared, cortex webapp, and mercury gateway. Starts anything that
  isn't running. Safe to call repeatedly (idempotent). Does NOT install NSSM
  services — use install-services.ps1 for that.

  Intended use:
    - Windows Task Scheduler (At logon, as current user, no elevation needed)
    - Mercury /stack start command
    - Manual recovery after suspend/crash

  Log files written to the same locations NSSM uses:
    C:\Users\<user>\.cloudflared\tunnel.log
    C:\Users\<user>\.cortex\logs\webapp.out.log
    C:\Users\<user>\.mercury\logs\gateway.out.log

.NOTES
  Does not need admin rights. Will co-exist with NSSM services: if the NSSM
  service is already running, this script detects the port/process as live
  and does nothing.
#>

[CmdletBinding()]
param(
    [int]$WaitBetweenStartsMs = 2000
)

$ErrorActionPreference = 'Continue'

$userProfile = $env:USERPROFILE

# ── Paths ────────────────────────────────────────────────────────────────────
$cloudflaredExe = 'C:\Program Files (x86)\cloudflared\cloudflared.exe'
$cloudflaredCfg = Join-Path $userProfile '.cloudflared\config.yml'
$cloudflaredLog = Join-Path $userProfile '.cloudflared\tunnel.log'

$cortexPython  = 'C:\Users\soumi\cortex\.venv\Scripts\python.exe'
$cortexAppDir  = 'D:\cortex'
$cortexLogDir  = Join-Path $userProfile '.cortex\logs'
$cortexLogOut  = Join-Path $cortexLogDir 'webapp.out.log'

$mercuryPython = 'D:\mercury\.venv\Scripts\python.exe'
$mercuryExe    = 'D:\mercury\.venv\Scripts\mercury.exe'
$mercuryAppDir = 'D:\mercury'
$mercuryLogDir = Join-Path $userProfile '.mercury\logs'
$mercuryLogOut = Join-Path $mercuryLogDir 'gateway.out.log'
$supervisorPs1 = Join-Path $mercuryAppDir 'scripts\windows-services\gateway-supervisor.ps1'

# ── Helpers ──────────────────────────────────────────────────────────────────
function Ensure-Dir { param([string]$Path); if (-not (Test-Path $Path)) { New-Item -ItemType Directory -Path $Path -Force | Out-Null } }
function Is-PortListening { param([int]$Port); return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) }
function Is-ProcessRunning { param([string]$Name); return [bool](Get-Process -Name $Name -ErrorAction SilentlyContinue) }

function Start-Detached {
    param([string]$Exe, [string[]]$Args, [string]$WorkDir, [string]$LogFile)
    Ensure-Dir (Split-Path $LogFile -Parent)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName               = $Exe
    $psi.Arguments              = $Args -join ' '
    $psi.WorkingDirectory       = $WorkDir
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute        = $false
    $psi.CreateNoWindow         = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    # Async log capture
    $proc.BeginOutputReadLine()
    $proc.BeginErrorReadLine()
    Register-ObjectEvent -InputObject $proc -EventName OutputDataReceived -Action {
        if ($Event.SourceEventArgs.Data) { Add-Content -Path $LogFile -Value $Event.SourceEventArgs.Data }
    } | Out-Null
    Register-ObjectEvent -InputObject $proc -EventName ErrorDataReceived -Action {
        if ($Event.SourceEventArgs.Data) { Add-Content -Path $LogFile -Value $Event.SourceEventArgs.Data }
    } | Out-Null
    return $proc
}

# ── 1. cloudflared ───────────────────────────────────────────────────────────
Write-Host '[ensure-running] Checking cloudflared...' -ForegroundColor Cyan

$cfRunning = Is-ProcessRunning 'cloudflared'

if ($cfRunning) {
    Write-Host '  cloudflared: already running ✓' -ForegroundColor Green
} elseif (Test-Path $cloudflaredExe) {
    Write-Host '  cloudflared: starting...' -ForegroundColor Yellow
    Ensure-Dir (Split-Path $cloudflaredLog -Parent)
    $cfArgs = @('tunnel', '--config', "`"$cloudflaredCfg`"", 'run', 'rtk-5090')
    Start-Detached -Exe $cloudflaredExe -Args $cfArgs -WorkDir $userProfile -LogFile $cloudflaredLog | Out-Null
    Start-Sleep -Milliseconds $WaitBetweenStartsMs
    if (Is-ProcessRunning 'cloudflared') {
        Write-Host '  cloudflared: started ✓' -ForegroundColor Green
    } else {
        Write-Host '  cloudflared: FAILED to start — check log: ' + $cloudflaredLog -ForegroundColor Red
    }
} else {
    Write-Host "  cloudflared: executable not found at $cloudflaredExe" -ForegroundColor Red
}

# ── 2. cortex webapp ────────────────────────────────────────────────────────
Write-Host '[ensure-running] Checking cortex webapp (:8765)...' -ForegroundColor Cyan

if (Is-PortListening 8765) {
    Write-Host '  cortex webapp: already listening on :8765 ✓' -ForegroundColor Green
} elseif (Test-Path $cortexPython) {
    Write-Host '  cortex webapp: starting uvicorn...' -ForegroundColor Yellow
    Ensure-Dir $cortexLogDir
    $uvArgs = @('-m', 'uvicorn', 'webapp.server:app', '--host', '0.0.0.0', '--port', '8765')
    Start-Detached -Exe $cortexPython -Args $uvArgs -WorkDir $cortexAppDir -LogFile $cortexLogOut | Out-Null
    Start-Sleep -Milliseconds ($WaitBetweenStartsMs * 2)
    if (Is-PortListening 8765) {
        Write-Host '  cortex webapp: started ✓' -ForegroundColor Green
    } else {
        Write-Host "  cortex webapp: FAILED — check log: $cortexLogOut" -ForegroundColor Red
    }
} else {
    Write-Host "  cortex webapp: Python not found at $cortexPython" -ForegroundColor Red
}

# ── 3. mercury gateway ───────────────────────────────────────────────────────
Write-Host '[ensure-running] Checking mercury gateway...' -ForegroundColor Cyan

# Mercury gateway detection: look for mercury_cli in running python processes
$gatewayRunning = Get-Process -Name 'python*' -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*mercury_cli*gateway*' } |
    Select-Object -First 1

if ($gatewayRunning) {
    Write-Host '  mercury gateway: already running ✓' -ForegroundColor Green
} elseif (Test-Path $mercuryExe) {
    Write-Host '  mercury gateway: starting via supervisor (auto-restart on crash)...' -ForegroundColor Yellow
    Ensure-Dir $mercuryLogDir
    # Use the supervisor instead of bare `python -m mercury_cli` (which is
    # broken — mercury_cli has no __main__.py). The supervisor restarts the
    # gateway with exponential backoff on crash and runs a config preflight.
    if (Test-Path $supervisorPs1) {
        $supArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$supervisorPs1`"")
        Start-Detached -Exe 'powershell.exe' -Args $supArgs -WorkDir $mercuryAppDir -LogFile $mercuryLogOut | Out-Null
    } else {
        # Fallback: launch mercury directly without supervision.
        Start-Detached -Exe $mercuryExe -Args @('gateway', 'run', '-v') -WorkDir $mercuryAppDir -LogFile $mercuryLogOut | Out-Null
    }
    Start-Sleep -Milliseconds $WaitBetweenStartsMs
    Write-Host '  mercury gateway: started (check log for errors)' -ForegroundColor Green
} else {
    Write-Host "  mercury gateway: mercury.exe not found at $mercuryExe" -ForegroundColor Red
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '=== RTK Stack Status ===' -ForegroundColor Green
Write-Host ("  cloudflared     : {0}" -f $(if (Is-ProcessRunning 'cloudflared') { 'running' } else { 'STOPPED' }))
Write-Host ("  cortex webapp   : {0}" -f $(if (Is-PortListening 8765) { 'running (:8765)' } else { 'STOPPED' }))
Write-Host ("  mercury gateway : {0}" -f $(if ((Get-Process -Name 'python*' -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like '*mercury_cli*'}).Count -gt 0) { 'running' } else { 'unknown (check log)' }))
Write-Host ''
Write-Host "Logs: $userProfile\\.cloudflared\\tunnel.log"
Write-Host "      $cortexLogOut"
Write-Host "      $mercuryLogOut"
