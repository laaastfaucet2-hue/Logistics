$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$TestDir = Join-Path $env:RUNNER_TEMP 'Logistics test install'
$Setup = Join-Path $Root 'dist\Logistics-Setup-2.0.0.exe'
$Arguments = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="' + $TestDir + '"'
$Process = Start-Process $Setup -ArgumentList $Arguments -Wait -PassThru
if ($Process.ExitCode -ne 0) { throw "Install failed: $($Process.ExitCode)" }
$Report = Join-Path $env:RUNNER_TEMP 'installed-smoke.txt'
$Process = Start-Process (Join-Path $TestDir 'Logistics.exe') -ArgumentList ('--smoke-test "' + $Report + '"') -Wait -PassThru
if ($Process.ExitCode -ne 0 -or -not (Test-Path $Report) -or (Get-Content $Report -Raw) -ne 'SMOKE_OK') { throw 'Installed program smoke test failed.' }
$UIReport = Join-Path $Root 'runtime\ui-smoke.txt'
$Process = Start-Process (Join-Path $TestDir 'Logistics.exe') -ArgumentList ('--ui-smoke-test "' + $UIReport + '"') -PassThru
if (-not $Process.WaitForExit(120000)) { Stop-Process -Id $Process.Id -Force; throw 'Native window timed out.' }
if ($Process.ExitCode -ne 0 -or -not (Test-Path $UIReport) -or (Get-Content $UIReport -Raw) -ne 'UI_SMOKE_OK') { throw 'Real WebView2 window/login/control test failed. See runtime/ui-smoke.txt and desktop.log.' }
$UserData = Join-Path $env:LOCALAPPDATA 'Logistics\database'
New-Item -ItemType Directory -Force $UserData | Out-Null
Set-Content (Join-Path $UserData 'preservation-sentinel.txt') 'must survive update and uninstall'
$Process = Start-Process $Setup -ArgumentList $Arguments -Wait -PassThru
if ($Process.ExitCode -ne 0) { throw 'Upgrade test failed.' }
$Process = Start-Process (Join-Path $TestDir 'unins000.exe') -ArgumentList '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -Wait -PassThru
if ($Process.ExitCode -ne 0) { throw 'Uninstall test failed.' }
if (-not (Test-Path (Join-Path $UserData 'preservation-sentinel.txt'))) { throw 'Installer removed user data.' }
Write-Host 'Install, upgrade, packaged smoke and preservation tests passed.'
