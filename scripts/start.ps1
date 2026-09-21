param([switch]$Build, [switch]$Web)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $Root
$LogDir = Join-Path $Root 'runtime\logs'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Start-Transcript -Path (Join-Path $LogDir 'startup.log') -Append | Out-Null
function Find-Python {
    $candidates = @()
    foreach ($name in @('py','python','python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $candidates += $cmd.Source }
    }
    $candidates += Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
    $candidates += "$env:LOCALAPPDATA\Programs\LogisticsPython312\python.exe"
    foreach ($exe in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $exe)) { continue }
        $prefix = @(); if ((Split-Path $exe -Leaf) -eq 'py.exe') { $prefix = @('-3') }
        try {
            $actual = & $exe @prefix -c 'import sys; assert (3,11) <= sys.version_info[:2] < (3,14); print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $actual -and (Test-Path -LiteralPath "$actual")) { return "$actual" }
        } catch { }
    }
    return $null
}
try {
    Write-Host 'Preparing Logistics. First source launch needs internet.' -ForegroundColor Cyan
    $Python = Find-Python
    if (-not $Python) {
        Write-Host 'Installing Python 3.12 for this user (no administrator required)...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $Setup = Join-Path $Root 'runtime\python-setup.exe'
        Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $Setup -UseBasicParsing
        $Signature = Get-AuthenticodeSignature -FilePath $Setup
        if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notlike '*Python Software Foundation*') { throw 'Python installer signature verification failed.' }
        $Target = "$env:LOCALAPPDATA\Programs\LogisticsPython312"
        $Args = '/quiet InstallAllUsers=0 Include_pip=1 Include_test=0 Include_launcher=0 PrependPath=0 TargetDir="' + $Target + '"'
        $Process = Start-Process -FilePath $Setup -ArgumentList $Args -Wait -PassThru
        if ($Process.ExitCode -notin @(0,3010)) { throw "Python install failed: $($Process.ExitCode)" }
        $Python = Find-Python
        if (-not $Python) { throw 'Python 3.11-3.13 was not found after installation.' }
    }
    $Venv = Join-Path $Root '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $Venv)) {
        & $Python -m venv (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the isolated Python environment.' }
    }
    $Requirements = if ($Build) { 'requirements\build.txt' } elseif ($Web) { 'requirements.txt' } else { 'requirements\desktop.txt' }
    $Stamp = Join-Path $Root 'runtime\dependencies.sha256'
    $Hash = ((Get-FileHash requirements.txt).Hash + (Get-FileHash $Requirements).Hash)
    $Verify = if ($Web) { 'import flask,openpyxl,docx,PIL,tzdata,waitress' } else { 'import flask,openpyxl,docx,PIL,tzdata,waitress,webview' }
    $Ready = $false
    try { & $Venv -c $Verify 2>$null; $Ready = $LASTEXITCODE -eq 0 } catch { $Ready = $false }
    if ($Build -or -not $Ready -or -not (Test-Path $Stamp) -or (Get-Content $Stamp -Raw).Trim() -ne $Hash) {
        & $Venv -m pip install --disable-pip-version-check -r $Requirements
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the internet connection and startup.log.' }
        & $Venv -c $Verify
        if ($LASTEXITCODE -ne 0) { throw 'A required library still cannot be imported.' }
        Set-Content -LiteralPath $Stamp -Value $Hash
    }
    if ($Build) { & (Join-Path $PSScriptRoot 'build-installer.ps1') -Python $Venv }
    elseif ($Web) { & $Venv app.py; if ($LASTEXITCODE -ne 0) { throw 'Web server stopped with an error.' } }
    else { & $Venv -m desktop; if ($LASTEXITCODE -ne 0) { throw 'Desktop launch failed. Check runtime\logs\desktop.log.' } }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Log file: $LogDir\startup.log" -ForegroundColor Yellow
    Stop-Transcript | Out-Null
    exit 1
}
Stop-Transcript | Out-Null
exit 0
