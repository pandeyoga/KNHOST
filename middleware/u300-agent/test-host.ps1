param([string]$JavaHome, [string]$JsonJar, [string]$Contract)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$workspace=(Get-Item $root).Parent.Parent.Parent.FullName
if (-not $JavaHome) { $JavaHome=Join-Path $workspace 'work/android-build/jdk' }
if (-not $JsonJar) { $JsonJar=Join-Path $workspace 'work/android-build/json-20240303.jar' }
if (-not $Contract) { $Contract=Join-Path $root 'contracts/OPENAPI_RFID_V2.json' }
if ((Get-FileHash $JsonJar -Algorithm SHA256).Hash -ne '3CF6CD6892E32E2B4C1C39E0F52F5248A2F5B37646FDFBB79A66B46B618414ED') { throw 'Hash dependency JSON tidak cocok.' }
$source=Join-Path $root 'app/src/main/java/id/kubusteknologi/kn/u300'
$classes=Join-Path $root 'tests/build'
New-Item -ItemType Directory -Force $classes | Out-Null
& "$JavaHome/bin/javac.exe" -cp $JsonJar -d $classes "$source/core/Safety.java" "$source/Json.java" "$source/Config.java" "$source/Api.java" "$source/DecisionPolicy.java" "$root/tests/SafetyTest.java" "$root/tests/HostTest.java" "$root/tests/DecisionPolicyTest.java" "$root/tests/TransportTest.java"
if ($LASTEXITCODE -ne 0) { throw 'Kompilasi tes gagal.' }
& "$JavaHome/bin/java.exe" -cp $classes SafetyTest
if ($LASTEXITCODE -ne 0) { throw 'Safety test gagal.' }
& "$JavaHome/bin/java.exe" -cp "$classes;$JsonJar" id.kubusteknologi.kn.u300.HostTest "$root/tests/contract-fixtures.json"
if ($LASTEXITCODE -ne 0) { throw 'Host test gagal.' }
& "$JavaHome/bin/java.exe" -cp "$classes;$JsonJar" id.kubusteknologi.kn.u300.DecisionPolicyTest
if ($LASTEXITCODE -ne 0) { throw 'Decision policy test gagal.' }
$testStore=Join-Path $classes ('loopback-'+[guid]::NewGuid().ToString()+'.p12')
& "$JavaHome/bin/keytool.exe" -genkeypair -alias localhost -keyalg RSA -keysize 2048 -validity 2 -dname 'CN=localhost' -ext 'SAN=DNS:localhost,IP:127.0.0.1' -storetype PKCS12 -keystore $testStore -storepass test-local-only -keypass test-local-only -noprompt
if ($LASTEXITCODE -ne 0) { throw 'Sertifikat pengujian lokal gagal dibuat.' }
& "$JavaHome/bin/java.exe" -cp "$classes;$JsonJar" id.kubusteknologi.kn.u300.TransportTest $testStore
if ($LASTEXITCODE -ne 0) { throw 'HTTPS loopback test gagal.' }
$oldPython=$env:PYTHONPATH
try {
    $env:PYTHONPATH=Join-Path $workspace 'work/android-build/test-python'
    python "$root/tests/validate_contract.py" $Contract
    if ($LASTEXITCODE -ne 0) { throw 'Schema test gagal.' }
    python "$root/tests/test_snapshot.py"
    if ($LASTEXITCODE -ne 0) { throw 'Snapshot test gagal.' }
} finally { $env:PYTHONPATH=$oldPython }
