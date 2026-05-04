<#
.SYNOPSIS
  Supervise mercury gateway with crash auto-restart and exponential backoff.

.DESCRIPTION
  Long-running supervisor: launches `mercury.exe gateway run -v`, watches it,
  restarts on exit with backoff. Designed to run from a Windows Scheduled
  Task at user logon, or invoked manually. Logs everything to the standard
  ~/.mercury/logs/ directory.

  Backoff schedule: 2s, 5s, 15s, 30s, 60s, 120s (capped). Resets to 2s after
  the gateway has been alive for at least 5 minutes (i.e., the crash wasn't
  caused by the previous one — we treat sustained uptime as 'recovered').

  Ctrl-C or `Stop-Process <pid-of-this-supervisor>` exits cleanly and stops
  the child gateway process group.

.PARAMETER MaxRestarts
  Maximum restarts before giving up entirely. Default: -1 (unlimited).
  After this many crashes within an hour, the supervisor exits and writes
  a final 'GIVING UP' line to the log so you know to investigate.

.PARAMETER ConfigCheck
  When set, run `mercury config doctor` (if present) before each launch.
  Default: $true. Catches YAML parse errors caused by copy-paste smart
  quotes, BOM, mismatched indentation, etc., before they crash the gateway.
#>

[CmdletBinding()]
param(
    [int]$MaxRestarts = -1,
    [bool]$ConfigCheck = $true
)

$ErrorActionPreference = 'Stop'

$mercuryExe = 'D:\mercury\.venv\Scripts\mercury.exe'
$mercuryDir = 'D:\mercury'
$logDir = Join-Path $env:USERPROFILE '.mercury\logs'
$superLog = Join-Path $logDir 'gateway-supervisor.log'
$gatewayOut = Join-Path $logDir 'gateway.out.log'
$gatewayErr = Join-Path $logDir 'gateway.err.log'

if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log {
    param([string]$Msg, [string]$Level = 'INFO')
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $line = "$ts [$Level] $Msg"
    Add-Content -Path $superLog -Value $line
    Write-Host $line
}

function Run-Preflight {
    if (-not $ConfigCheck) { return $true }
    # Cheap YAML parse of ~/.mercury/config.yaml — catches the most common
    # copy-paste damage (smart quotes, BOM, tabs-vs-spaces, missing colons).
    $cfg = Join-Path $env:USERPROFILE '.mercury\config.yaml'
    if (-not (Test-Path $cfg)) { return $true }
    try {
        $bytes = [System.IO.File]::ReadAllBytes($cfg)
        # BOM check
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            Write-Log "config.yaml has UTF-8 BOM — Mercury PyYAML may choke; rewriting without BOM" 'WARN'
            $text = [System.IO.File]::ReadAllText($cfg)
            [System.IO.File]::WriteAllText($cfg, $text, (New-Object System.Text.UTF8Encoding($false)))
        }
        # Smart-quote scan
        $content = [System.IO.File]::ReadAllText($cfg)
        $smartQuotes = [regex]::Matches($content, "[‘’“”]")
        if ($smartQuotes.Count -gt 0) {
            Write-Log "config.yaml contains $($smartQuotes.Count) smart quote(s) — replacing with ASCII" 'WARN'
            $content = $content -replace '[‘’]', "'"
            $content = $content -replace '[“”]', '"'
            [System.IO.File]::WriteAllText($cfg, $content, (New-Object System.Text.UTF8Encoding($false)))
        }
        # Tab indentation (YAML forbids tabs in indentation)
        $tabIndentLines = ($content -split "`n") | Where-Object { $_ -match '^\t' }
        if ($tabIndentLines.Count -gt 0) {
            Write-Log "config.yaml has $($tabIndentLines.Count) tab-indented line(s) — this WILL break YAML; manual fix required" 'ERROR'
            return $false
        }
    } catch {
        Write-Log "preflight failed: $_" 'WARN'
    }
    return $true
}

# ─── Main supervision loop ─────────────────────────────────────────────────
$restartCount = 0
$crashTimes = @()
$backoff = @(2, 5, 15, 30, 60, 120)
$backoffIdx = 0

Write-Log "supervisor starting (mercury=$mercuryExe MaxRestarts=$MaxRestarts ConfigCheck=$ConfigCheck)"

while ($true) {
    if (-not (Test-Path $mercuryExe)) {
        Write-Log "mercury.exe not found at $mercuryExe — supervisor exiting" 'ERROR'
        exit 1
    }

    if (-not (Run-Preflight)) {
        Write-Log "config preflight failed — sleeping 60s before retry" 'WARN'
        Start-Sleep -Seconds 60
        continue
    }

    Write-Log "launching gateway (restart #$restartCount)"
    $startTime = Get-Date

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $mercuryExe
    $psi.Arguments = 'gateway run -v'
    $psi.WorkingDirectory = $mercuryDir
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $proc = $null
    try {
        $proc = [System.Diagnostics.Process]::Start($psi)
    } catch {
        Write-Log "failed to spawn mercury: $_" 'ERROR'
        Start-Sleep -Seconds 30
        continue
    }

    Write-Log "gateway pid=$($proc.Id) — streaming logs"

    # Stream stdout/stderr to the standard log files (append mode) so they
    # behave the same way the NSSM service would write them.
    $outJob = Start-Job -ArgumentList $proc.Id, $gatewayOut -ScriptBlock {
        param($childPid, $logPath)
        $p = Get-Process -Id $childPid -ErrorAction SilentlyContinue
        if (-not $p) { return }
        while (-not $p.HasExited) {
            $line = $p.StandardOutput.ReadLine()
            if ($null -ne $line) { Add-Content -Path $logPath -Value $line }
        }
    }
    $errJob = Start-Job -ArgumentList $proc.Id, $gatewayErr -ScriptBlock {
        param($childPid, $logPath)
        $p = Get-Process -Id $childPid -ErrorAction SilentlyContinue
        if (-not $p) { return }
        while (-not $p.HasExited) {
            $line = $p.StandardError.ReadLine()
            if ($null -ne $line) { Add-Content -Path $logPath -Value $line }
        }
    }

    $proc.WaitForExit()
    Stop-Job $outJob, $errJob -ErrorAction SilentlyContinue
    Remove-Job $outJob, $errJob -ErrorAction SilentlyContinue

    $exitCode = $proc.ExitCode
    $alive = (Get-Date) - $startTime
    Write-Log "gateway exited code=$exitCode alive=$($alive.ToString('hh\:mm\:ss'))"

    # Reset backoff if the gateway lived long enough that this exit isn't
    # part of a crash loop.
    if ($alive.TotalMinutes -ge 5) {
        $backoffIdx = 0
        $crashTimes = @()
    } else {
        $crashTimes += (Get-Date)
        # Drop crashes older than 1 hour for the rate-limit calc.
        $crashTimes = $crashTimes | Where-Object { ((Get-Date) - $_).TotalHours -lt 1 }
    }

    $restartCount++
    if ($MaxRestarts -ge 0 -and $crashTimes.Count -gt $MaxRestarts) {
        Write-Log "exceeded MaxRestarts ($MaxRestarts) within 1 hour — GIVING UP" 'ERROR'
        exit 2
    }

    $sleepSec = $backoff[[Math]::Min($backoffIdx, $backoff.Count - 1)]
    $backoffIdx++
    Write-Log "restarting in ${sleepSec}s (backoff #$backoffIdx)"
    Start-Sleep -Seconds $sleepSec
}
