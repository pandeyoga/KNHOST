param([string]$ToolRoot, [string]$JavaHome, [string]$JsonJar, [string]$Contract)
# Tes host agent 0.5.0 (tanpa perangkat/Android): kelas inti, state machine, pipeline ujung-ke-ujung, kebijakan
# keputusan, HTTPS loopback, validasi skema kontrak 2.1, integritas snapshot.
# Toolchain: -ToolRoot <folder android-build> | env KN_ANDROID_TOOLS | <workspace>/work/android-build (pola 0.4).
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
if (-not $ToolRoot) { $ToolRoot=$env:KN_ANDROID_TOOLS }
if (-not $ToolRoot) { $ToolRoot=Join-Path (Get-Item $root).Parent.Parent.Parent.FullName 'work/android-build' }
if (-not $JavaHome) { $JavaHome=Join-Path $ToolRoot 'jdk' }
if (-not $JsonJar) { $JsonJar=Join-Path $ToolRoot 'json-20240303.jar' }
if (-not $Contract) { $Contract=Join-Path $root 'contracts/OPENAPI_RFID_V2.json' }
if ((Get-FileHash $JsonJar -Algorithm SHA256).Hash -ne '3CF6CD6892E32E2B4C1C39E0F52F5248A2F5B37646FDFBB79A66B46B618414ED') { throw 'Hash dependency JSON tidak cocok.' }
$source=Join-Path $root 'app/src/main/java/id/kubusteknologi/kn/u300'
$classes=Join-Path $root 'tests/build'
New-Item -ItemType Directory -Force $classes | Out-Null
$core=Get-ChildItem (Join-Path $source 'core') -Filter *.java | ForEach-Object { $_.FullName }
$main=@('Json.java','Config.java','Api.java','DecisionPolicy.java','Telemetry.java') | ForEach-Object { Join-Path $source $_ }
$tests=@('SafetyTest.java','CoreTest.java','PassageMachineTest.java','HostTest.java','PipelineTest.java','DecisionPolicyTest.java','TransportTest.java') | ForEach-Object { Join-Path $root "tests/$_" }
& "$JavaHome/bin/javac.exe" -encoding UTF-8 -cp $JsonJar -d $classes @core @main @tests
if ($LASTEXITCODE -ne 0) { throw 'Kompilasi tes gagal.' }
$cp="$classes;$JsonJar"
$fixtures=Join-Path $root 'tests/contract-fixtures.json'
foreach ($t in @(@('SafetyTest'),@('CoreTest'),@('PassageMachineTest'),@('id.kubusteknologi.kn.u300.HostTest',$fixtures),@('id.kubusteknologi.kn.u300.PipelineTest',$fixtures),@('id.kubusteknologi.kn.u300.DecisionPolicyTest'))) {
    & "$JavaHome/bin/java.exe" -cp $cp @t
    if ($LASTEXITCODE -ne 0) { throw "$($t[0]) gagal." }
}
$testStore=Join-Path $classes ('loopback-'+[guid]::NewGuid().ToString()+'.p12')
& "$JavaHome/bin/keytool.exe" -genkeypair -alias localhost -keyalg RSA -keysize 2048 -validity 2 -dname 'CN=localhost' -ext 'SAN=DNS:localhost,IP:127.0.0.1' -storetype PKCS12 -keystore $testStore -storepass test-local-only -keypass test-local-only -noprompt
if ($LASTEXITCODE -ne 0) { throw 'Sertifikat pengujian lokal gagal dibuat.' }
& "$JavaHome/bin/java.exe" -cp $cp id.kubusteknologi.kn.u300.TransportTest $testStore
if ($LASTEXITCODE -ne 0) { throw 'HTTPS loopback test gagal.' }
$oldPython=$env:PYTHONPATH
try {
    $env:PYTHONPATH=Join-Path $ToolRoot 'test-python'
    python "$root/tests/validate_contract.py" $Contract
    if ($LASTEXITCODE -ne 0) { throw 'Schema test gagal.' }
    python "$root/tests/test_snapshot.py"
    if ($LASTEXITCODE -ne 0) { throw 'Snapshot test gagal.' }
} finally { $env:PYTHONPATH=$oldPython }
