param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$Stage = 'preparing build tools'
function Write-BuildError([string]$Message) {
    $Message = $Message.Replace('%', '%25').Replace("`r", '%0D').Replace("`n", '%0A')
    Write-Host "::error title=Windows build::$Message"
}
trap {
    Write-BuildError ("Stage: " + $Stage + ". " + $_.Exception.Message)
    exit 1
}
$Root = Split-Path $PSScriptRoot -Parent
Set-Location -LiteralPath $Root
$ISCC = Get-Command 'ISCC.exe' -ErrorAction SilentlyContinue
if ($ISCC) { $Compiler = $ISCC.Source }
else { $Compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Install Inno Setup 6 first (https://jrsoftware.org/isinfo.php), then rebuild.' }
$Prereqs = Join-Path $Root 'runtime\installer'
New-Item -ItemType Directory -Force -Path $Prereqs | Out-Null
$WebView = Join-Path $Prereqs 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
$Stage = 'download Microsoft WebView2'
if (-not (Test-Path -LiteralPath $WebView)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest 'https://go.microsoft.com/fwlink/?linkid=2124701' -OutFile $WebView -UseBasicParsing
}
$Stage = 'verify Microsoft signature'
$Signature = Get-AuthenticodeSignature -FilePath $WebView
if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notlike '*Microsoft Corporation*') {
    throw 'The WebView2 installer signature is invalid; refusing to bundle it.'
}
$Stage = 'Python acceptance tests'
$TestReport = Join-Path $Root 'runtime\pytest.xml'
& $Python -m pytest tests -q "--junitxml=$TestReport"
if ($LASTEXITCODE -ne 0) {
    if (Test-Path $TestReport) {
        [xml]$Results = Get-Content -LiteralPath $TestReport -Raw
        foreach ($Case in $Results.SelectNodes('//testcase[failure or error]')) {
            $Failure = $Case.SelectSingleNode('failure | error')
            Write-BuildError ($Case.classname + '.' + $Case.name + ': ' + $Failure.GetAttribute('message'))
        }
    }
    throw 'Tests failed; no installer will be built.'
}
$Stage = 'freeze application'
$BundleLog = Join-Path $Root 'runtime\bundle.log'
& $Python -m PyInstaller --noconfirm --clean scripts\installer\Logistics.spec 2>&1 | Tee-Object -FilePath $BundleLog
if ($LASTEXITCODE -ne 0) { Write-BuildError ((Get-Content $BundleLog -Tail 20) -join "`n"); throw 'Application bundling failed.' }
$Stage = 'frozen executable smoke test'
$Smoke = Join-Path $Root 'runtime\packaged-smoke.txt'
Remove-Item $Smoke -ErrorAction SilentlyContinue
$Process = Start-Process -FilePath (Join-Path $Root 'dist\Logistics\Logistics.exe') -ArgumentList ('--smoke-test "' + $Smoke + '"') -Wait -PassThru
if ($Process.ExitCode -ne 0 -or -not (Test-Path $Smoke) -or (Get-Content $Smoke -Raw) -ne 'SMOKE_OK') { if (Test-Path $Smoke) { Write-BuildError (Get-Content $Smoke -Raw) }; throw 'The packaged executable failed its smoke test.' }
$Stage = 'compile setup installer'
$InstallerLog = Join-Path $Root 'runtime\installer-build.log'
& $Compiler "/DSourceRoot=$Root" (Join-Path $Root 'scripts\installer\Logistics.iss') 2>&1 | Tee-Object -FilePath $InstallerLog
if ($LASTEXITCODE -ne 0) { Write-BuildError ((Get-Content $InstallerLog -Tail 20) -join "`n"); throw 'Installer compilation failed.' }
$Stage = 'installer checksum'
$Setup = Join-Path $Root 'dist\Logistics-Setup-2.1.0.exe'
Get-FileHash $Setup -Algorithm SHA256 | Format-List | Out-File (Join-Path $Root 'dist\SHA256.txt')
Write-Host "Installer ready: $Setup" -ForegroundColor Green
