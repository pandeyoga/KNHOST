param([string]$ToolRoot, [string]$JavaHome, [string]$JsonJar)
# Tes host KN Handheld C72 0.1.0-lab (tanpa perangkat/Android): logika inti, alur radio tiruan (pemicu, tulis+baca ulang,
# uji meja), antrean offline + sinkron, transport HTTP nyata ke server lokal JDK. Pola: middleware/u300-agent/test-host.ps1.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
if (-not $ToolRoot) { $ToolRoot = $env:KN_ANDROID_TOOLS }
if (-not $ToolRoot) { throw 'Isi -ToolRoot <folder android-build> atau env KN_ANDROID_TOOLS.' }
if (-not $JavaHome) { $JavaHome = Join-Path $ToolRoot 'jdk' }
if (-not $JsonJar) { $JsonJar = Join-Path $ToolRoot 'json-20240303.jar' }
if ((Get-FileHash $JsonJar -Algorithm SHA256).Hash -ne '3CF6CD6892E32E2B4C1C39E0F52F5248A2F5B37646FDFBB79A66B46B618414ED') { throw 'Hash dependency JSON tidak cocok.' }
$classes = Join-Path $root 'tests/build/host'
if (Test-Path $classes) { Remove-Item -Recurse -Force $classes }
New-Item -ItemType Directory -Force $classes | Out-Null
$core = Get-ChildItem (Join-Path $root 'app/src/main/java/id/kainnusantara/handheld/core') -Filter *.java | ForEach-Object { $_.FullName }
$tests = @('CoreTest.java', 'FlowTest.java', 'SyncTest.java', 'ApiTest.java') | ForEach-Object { Join-Path $root "tests/$_" }
& "$JavaHome/bin/javac.exe" -encoding UTF-8 -Xlint:unchecked -cp $JsonJar -d $classes @core @tests
if ($LASTEXITCODE -ne 0) { throw 'Kompilasi tes gagal.' }
$cp = "$classes;$JsonJar"
$total = 0
foreach ($t in @('CoreTest', 'FlowTest', 'SyncTest', 'ApiTest')) {
    $out = & "$JavaHome/bin/java.exe" -cp $cp "id.kainnusantara.handheld.core.$t" 2>&1
    $out | ForEach-Object { Write-Output $_ }
    if ($LASTEXITCODE -ne 0) { throw "$t gagal." }
    $total += ($out | Where-Object { $_ -match '^PASS ' }).Count
}
Write-Output "TES HOST C72: $total PASS, 0 FAIL"
