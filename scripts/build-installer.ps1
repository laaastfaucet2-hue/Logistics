param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $Root
$ISCC = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
if ($ISCC) { $Compiler = $ISCC.Source }
else { $Compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 6 first (https://jrsoftware.org/isinfo.php), then rebuild.' }
$Prereqs = Join-Path $Root 'runtime\installer'
New-Item -ItemType Directory -Force -Path $Prereqs | Out-Null
$WebView = Join-Path $Prereqs 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
if (-not (Test-Path -LiteralPath $WebView)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest 'https://go.microsoft.com/fwlink/?linkid=2124701' -OutFile $WebView -UseBasicParsing
}
$Signature = Get-AuthenticodeSignature -FilePath $WebView
if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notlike '*Microsoft Corporation*') {
    throw 'The WebView2 installer signature is invalid; refusing to bundle it.'
}
& $Python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; no installer will be built.' }
& $Python -m PyInstaller --noconfirm --clean scripts\installer\Logistics.spec
if ($LASTEXITCODE -ne 0) { throw 'Application bundling failed.' }
$Smoke = Join-Path $Root 'runtime\packaged-smoke.txt'
Remove-Item $Smoke -ErrorAction SilentlyContinue
$Process = Start-Process -FilePath (Join-Path $Root 'dist\Logistics\Logistics.exe') -ArgumentList ('--smoke-test "' + $Smoke + '"') -Wait -PassThru
if ($Process.ExitCode -ne 0 -or -not (Test-Path $Smoke) -or (Get-Content $Smoke -Raw) -ne 'SMOKE_OK') { throw 'The packaged executable failed its smoke test.' }
& $Compiler "/DSourceRoot=$Root" (Join-Path $Root 'scripts\installer\Logistics.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
$Setup = Join-Path $Root 'dist\Logistics-Setup-2.0.0.exe'
Get-FileHash $Setup -Algorithm SHA256 | Format-List | Out-File (Join-Path $Root 'dist\SHA256.txt')
Write-Host "Installer ready: $Setup" -ForegroundColor Green
