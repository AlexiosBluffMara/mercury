<#
.SYNOPSIS
  Install rtk-* Windows services (NSSM-wrapped) for the Red Team Kitchen 5090 stack.

.DESCRIPTION
  Idempotent installer. Wraps three long-running processes into Windows services:
    - rtk-cloudflared       cloudflared tunnel for mercury.redteamkitchen.com
    - rtk-cortex-webapp     uvicorn webapp.server:app on port 8765
    - rtk-mercury-gateway   mercury gateway (Discord bot + agent)

  All three are SERVICE_AUTO_START (start at boot), restart-on-failure with a
  60s throttle, max 5 restarts per hour. Each runs as the current interactive
  user so they have access to ~/.cloudflared, ~/.cortex, ~/.mercury.

  Re-running this script is safe: if a service already exists with the desired
  configuration, NSSM commands are no-ops; mismatched values are corrected.

.NOTES
  Requires admin. Self-elevates via Start-Process -Verb RunAs.
#>

[CmdletBinding()]
param(
    [string]$NssmDir = 'C:\Program Files\nssm',
    [string]$NssmZipUrl = 'https://nssm.cc/release/nssm-2.24.zip'
)

$ErrorActionPreference = 'Stop'

# --- Self-elevate -----------------------------------------------------------
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host '[install-services] Not elevated. Re-launching as Administrator...' -ForegroundColor Yellow
    $argList = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath)
    foreach ($k in $PSBoundParameters.Keys) {
        $argList += @("-$k", $PSBoundParameters[$k])
    }
    Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs
    exit
}

# --- Resolve NSSM -----------------------------------------------------------
function Resolve-Nssm {
    param([string]$NssmDir, [string]$NssmZipUrl)

    $existing = (Get-Command nssm -ErrorAction SilentlyContinue).Source
    if ($existing) { return $existing }

    $candidate = Join-Path $NssmDir 'nssm.exe'
    if (Test-Path $candidate) {
        $env:PATH = "$NssmDir;$env:PATH"
        return $candidate
    }

    Write-Host "[install-services] NSSM not found. Downloading from $NssmZipUrl..." -ForegroundColor Cyan
    $tmpZip = Join-Path $env:TEMP 'nssm-2.24.zip'
    $tmpExtract = Join-Path $env:TEMP 'nssm-2.24-extracted'

    Invoke-WebRequest -Uri $NssmZipUrl -OutFile $tmpZip -UseBasicParsing
    if (Test-Path $tmpExtract) { Remove-Item $tmpExtract -Recurse -Force }
    Expand-Archive -Path $tmpZip -DestinationPath $tmpExtract -Force

    $arch = if ([Environment]::Is64BitOperatingSystem) { 'win64' } else { 'win32' }
    $src = Get-ChildItem -Path $tmpExtract -Recurse -Filter 'nssm.exe' |
           Where-Object { $_.FullName -match "\\$arch\\" } | Select-Object -First 1

    if (-not $src) { throw "Could not locate nssm.exe ($arch) inside extracted zip." }

    if (-not (Test-Path $NssmDir)) { New-Item -ItemType Directory -Path $NssmDir -Force | Out-Null }
    Copy-Item $src.FullName -Destination (Join-Path $NssmDir 'nssm.exe') -Force

    # Add to PATH for this session and persist machine-wide
    $env:PATH = "$NssmDir;$env:PATH"
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if ($machinePath -notlike "*$NssmDir*") {
        [Environment]::SetEnvironmentVariable('Path', "$machinePath;$NssmDir", 'Machine')
    }

    Remove-Item $tmpZip -Force -ErrorAction SilentlyContinue
    return (Join-Path $NssmDir 'nssm.exe')
}

$nssm = Resolve-Nssm -NssmDir $NssmDir -NssmZipUrl $NssmZipUrl
Write-Host "[install-services] Using NSSM at: $nssm" -ForegroundColor Green

# --- Helpers ----------------------------------------------------------------
function Test-ServiceExists {
    param([string]$Name)
    return [bool](Get-Service -Name $Name -ErrorAction SilentlyContinue)
}

function Set-NssmParam {
    param([string]$Service, [string]$Key, [string]$Value)
    $current = & $nssm get $Service $Key 2>$null
    if ($LASTEXITCODE -ne 0 -or "$current".Trim() -ne $Value) {
        & $nssm set $Service $Key $Value | Out-Null
    }
}

function Install-RtkService {
    param(
        [Parameter(Mandatory)] [string]$Name,
        [Parameter(Mandatory)] [string]$Application,
        [Parameter(Mandatory)] [string]$Arguments,
        [Parameter(Mandatory)] [string]$AppDirectory,
        [Parameter(Mandatory)] [string]$StdoutLog,
        [Parameter(Mandatory)] [string]$StderrLog,
        [string]$Description = ''
    )

    Write-Host "[install-services] Configuring $Name..." -ForegroundColor Cyan

    $logDir = Split-Path $StdoutLog -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $logDir2 = Split-Path $StderrLog -Parent
    if (-not (Test-Path $logDir2)) { New-Item -ItemType Directory -Path $logDir2 -Force | Out-Null }

    if (-not (Test-ServiceExists -Name $Name)) {
        & $nssm install $Name $Application | Out-Null
    }

    Set-NssmParam $Name 'Application'   $Application
    Set-NssmParam $Name 'AppParameters' $Arguments
    Set-NssmParam $Name 'AppDirectory'  $AppDirectory
    Set-NssmParam $Name 'DisplayName'   $Name
    if ($Description) { Set-NssmParam $Name 'Description' $Description }

    Set-NssmParam $Name 'AppStdout' $StdoutLog
    Set-NssmParam $Name 'AppStderr' $StderrLog
    # Rotate logs at 10 MB so the disk doesn't fill
    Set-NssmParam $Name 'AppRotateFiles'    '1'
    Set-NssmParam $Name 'AppRotateOnline'   '1'
    Set-NssmParam $Name 'AppRotateBytes'    '10485760'

    # Auto-start at boot
    Set-NssmParam $Name 'Start' 'SERVICE_AUTO_START'

    # Restart-on-failure: throttle 60s, give up after 5 attempts in an hour
    # AppExit Default requires 3-arg form: nssm set <svc> AppExit Default Restart
    & $nssm set $Name AppExit Default Restart | Out-Null
    Set-NssmParam $Name 'AppRestartDelay'   '60000'
    Set-NssmParam $Name 'AppThrottle'       '60000'
    Set-NssmParam $Name 'AppStopMethodSkip' '0'
    Set-NssmParam $Name 'AppStopMethodConsole' '15000'
    # Throttle window of 1 hour = 3600000 ms; max 5 restarts before giving up
    Set-NssmParam $Name 'AppRestartCount'  '5'
    Set-NssmParam $Name 'AppRestartWindow' '3600000'

    # Run as the current interactive user (preserves $HOME-relative paths)
    $userName = "$env:USERDOMAIN\$env:USERNAME"
    $existingUser = & $nssm get $Name 'ObjectName' 2>$null
    if ("$existingUser".Trim() -ne $userName) {
        Write-Host "  -> setting service to run as $userName (you may be prompted for your password)" -ForegroundColor Yellow
        & $nssm set $Name 'ObjectName' $userName | Out-Null
    }
}

# --- Resolve absolute paths -------------------------------------------------
$userProfile = $env:USERPROFILE
$cloudflaredExe = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflaredExe) {
    $candidate = Join-Path $userProfile '.cloudflared\cloudflared.exe'
    if (Test-Path $candidate) { $cloudflaredExe = $candidate }
    else { $cloudflaredExe = 'cloudflared.exe' }  # rely on PATH at service-start time
}

$cloudflaredConfig = Join-Path $userProfile '.cloudflared\config.yml'
$cloudflaredLogDir = Join-Path $userProfile '.cloudflared'

$cortexVenvPython  = 'C:\Users\soumi\cortex\.venv\Scripts\python.exe'
$cortexAppDir      = 'D:\cortex'
$cortexLogDir      = Join-Path $userProfile '.cortex\logs'

# Mercury venv lives inside the repo (D:\mercury\.venv) on this host.
$mercuryVenvPython = 'D:\mercury\.venv\Scripts\python.exe'
$mercuryAppDir     = 'D:\mercury'
$mercuryLogDir     = Join-Path $userProfile '.mercury\logs'

# --- Install three services -------------------------------------------------
Install-RtkService `
    -Name 'rtk-cloudflared' `
    -Application $cloudflaredExe `
    -Arguments "tunnel --config `"$cloudflaredConfig`" run rtk-5090" `
    -AppDirectory $userProfile `
    -StdoutLog (Join-Path $cloudflaredLogDir 'service.log') `
    -StderrLog (Join-Path $cloudflaredLogDir 'service.log') `
    -Description 'Cloudflare tunnel exposing mercury.redteamkitchen.com / ollama.redteamkitchen.com'

Install-RtkService `
    -Name 'rtk-cortex-webapp' `
    -Application $cortexVenvPython `
    -Arguments '-m uvicorn webapp.server:app --host 0.0.0.0 --port 8765' `
    -AppDirectory $cortexAppDir `
    -StdoutLog (Join-Path $cortexLogDir 'webapp.out.log') `
    -StderrLog (Join-Path $cortexLogDir 'webapp.err.log') `
    -Description 'Cortex hackathon webapp (uvicorn on :8765)'

Install-RtkService `
    -Name 'rtk-mercury-gateway' `
    -Application $mercuryVenvPython `
    -Arguments '-m mercury_cli gateway run -v' `
    -AppDirectory $mercuryAppDir `
    -StdoutLog (Join-Path $mercuryLogDir 'gateway.out.log') `
    -StderrLog (Join-Path $mercuryLogDir 'gateway.err.log') `
    -Description 'Mercury gateway (Hermes-fork agent + Discord bot)'

# --- Start + verify ---------------------------------------------------------
$services = @('rtk-cloudflared','rtk-cortex-webapp','rtk-mercury-gateway')
foreach ($svc in $services) {
    Write-Host "[install-services] Starting $svc..." -ForegroundColor Cyan
    try {
        Start-Service -Name $svc -ErrorAction Stop
    } catch {
        Write-Host "  start failed: $($_.Exception.Message)" -ForegroundColor Red
    }
}

Start-Sleep -Seconds 2

Write-Host ''
Write-Host '=== Service status ===' -ForegroundColor Green
foreach ($svc in $services) {
    $status = (Get-Service -Name $svc -ErrorAction SilentlyContinue).Status
    $nssmStatus = & $nssm status $svc 2>$null
    "{0,-22}  Get-Service={1,-10}  nssm={2}" -f $svc, $status, "$nssmStatus".Trim() | Write-Host
}

Write-Host ''
Write-Host 'Logs:' -ForegroundColor Green
Write-Host "  cloudflared:     $cloudflaredLogDir\service.log"
Write-Host "  cortex webapp:   $cortexLogDir\webapp.{out,err}.log"
Write-Host "  mercury gateway: $mercuryLogDir\gateway.{out,err}.log"
Write-Host ''
Write-Host 'Tail a log live with:' -ForegroundColor Green
Write-Host "  Get-Content -Path '$mercuryLogDir\gateway.out.log' -Tail 50 -Wait"
