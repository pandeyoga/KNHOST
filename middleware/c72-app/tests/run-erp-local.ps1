param([Parameter(Mandatory = $true)][string]$ToolRoot, [string]$BaseUrl = 'http://127.0.0.1:8071', [string]$Container = 'kn-tmp-g-be')
# Uji integrasi klien Java C72 → ERP LOKAL (backend uji sementara, BUKAN produksi). Langkah: seed dunia uji di dalam
# kontainer backend (seed_erp_local.py: site, gudang, perangkat ber-key acak, operator ber-sandi acak, PA terkirim, roll
# tanpa tag) → kompilasi kelas inti + ErpLocalTest → jalankan → bersihkan. seed.json (berisi key & sandi acak) dihapus.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$host_ = ([uri]$BaseUrl).Host
if ($host_ -ne '127.0.0.1' -and $host_ -ne 'localhost') { throw 'Base URL wajib lokal (backend uji).' }
$jdk = Join-Path $ToolRoot 'jdk'
$jar = Join-Path $ToolRoot 'json-20240303.jar'
$out = Join-Path $root 'tests/build/erp-local'
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null
$seedFile = Join-Path $out 'seed.json'
$env:MSYS_NO_PATHCONV = '1'
$seed = docker exec $Container python /app/middleware/c72-app/tests/seed_erp_local.py seed
if ($LASTEXITCODE -ne 0) { throw 'Seed gagal.' }
[System.IO.File]::WriteAllText($seedFile, ($seed | Select-Object -Last 1), [System.Text.UTF8Encoding]::new($false))
$tag = (Get-Content $seedFile -Raw | ConvertFrom-Json).tag
try {
    $core = Get-ChildItem (Join-Path $root 'app/src/main/java/id/kainnusantara/handheld/core') -Filter *.java | ForEach-Object { $_.FullName }
    & "$jdk/bin/javac.exe" -encoding UTF-8 -cp $jar -d $out @core (Join-Path $root 'tests/ErpLocalTest.java')
    if ($LASTEXITCODE -ne 0) { throw 'Kompilasi gagal.' }
    & "$jdk/bin/java.exe" -cp "$out;$jar" id.kainnusantara.handheld.core.ErpLocalTest $BaseUrl $seedFile
    $code = $LASTEXITCODE
} finally {
    Remove-Item -Force $seedFile -ErrorAction SilentlyContinue
    docker exec $Container python /app/middleware/c72-app/tests/seed_erp_local.py clean $tag | Write-Output
}
if ($code -ne 0) { throw "ErpLocalTest gagal (exit $code)." }
