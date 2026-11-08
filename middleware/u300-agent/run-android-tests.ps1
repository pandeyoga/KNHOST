param([Parameter(Mandatory=$true)][string]$Adb, [Parameter(Mandatory=$true)][string]$Serial)
$ErrorActionPreference='Stop'
# An explicit serial prevents installation on an unintended connected device.
& $Adb -s $Serial get-state
if($LASTEXITCODE -ne 0){throw 'Perangkat/emulator tidak tersedia.'}
$app=Join-Path $PSScriptRoot 'app/build/outputs/apk/debug/app-debug.apk'
$test=Join-Path $PSScriptRoot 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'
if(!(Test-Path $app)){$app=Join-Path $PSScriptRoot 'delivery/KN-U300-Agent-0.3.0-lab-debug.apk'}
if(!(Test-Path $test)){$test=Join-Path $PSScriptRoot 'delivery/KN-U300-Agent-0.3.0-androidTest.apk'}
if(!(Test-Path $app) -or !(Test-Path $test)){throw 'Jalankan build-debug.ps1 -IncludeAndroidTests terlebih dahulu.'}
& $Adb -s $Serial install -r $app
if($LASTEXITCODE -ne 0){throw 'Instal APK gagal; periksa ABI/Android/signature.'}
& $Adb -s $Serial install -r $test
if($LASTEXITCODE -ne 0){throw 'Instal APK pengujian gagal.'}
$result=& $Adb -s $Serial shell am instrument -w id.kubusteknologi.kn.u300.agent.test/id.kubusteknologi.kn.u300.ReaderTestRunner
$result | Set-Content (Join-Path $PSScriptRoot 'tests/android-runtime-results.log')
$result
if(($result -join "`n") -notmatch 'PASS Android SQLite:'){throw 'Runtime test belum lulus; periksa log.'}
