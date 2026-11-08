param([switch]$Lint, [string]$ToolRoot, [switch]$Offline, [switch]$Deliver)
# Build APK debug KN Handheld C72 (+ lint). Pola sama dengan middleware/u300-agent/build-debug.ps1 (paket E).
# Toolchain: -ToolRoot <folder android-build> | env KN_ANDROID_TOOLS. local.properties dibuat di sini dan TIDAK di-commit.
# -Deliver: salin APK ke delivery/KN-C72-Handheld-<versi>-debug.apk + tulis SHA256SUMS.txt.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if (-not $ToolRoot) { $ToolRoot = $env:KN_ANDROID_TOOLS }
if (-not $ToolRoot) { throw 'Isi -ToolRoot <folder android-build> atau env KN_ANDROID_TOOLS.' }
$jdkPath = Join-Path $ToolRoot 'jdk'
$sdkPath = Join-Path $ToolRoot 'sdk'
if (-not (Test-Path -LiteralPath (Join-Path $jdkPath 'bin/java.exe'))) { throw 'JDK lokal belum tersedia.' }
if (-not (Test-Path -LiteralPath (Join-Path $sdkPath 'platforms/android-34/android.jar'))) { throw 'SDK Android 34 belum tersedia.' }
$aar = Join-Path $projectRoot '../u300-agent/app/libs/DeviceAPI_ver20251103_release.aar'
if (-not (Test-Path -LiteralPath $aar)) { throw 'SDK vendor tidak ditemukan di ../u300-agent/app/libs (dirujuk, tidak digandakan).' }
$old = @{ JAVA_HOME = $env:JAVA_HOME; GRADLE_USER_HOME = $env:GRADLE_USER_HOME; ANDROID_USER_HOME = $env:ANDROID_USER_HOME }
try {
    $env:JAVA_HOME = $jdkPath
    $env:GRADLE_USER_HOME = Join-Path $ToolRoot 'gradle-home'
    $env:ANDROID_USER_HOME = Join-Path $ToolRoot 'android-user'
    New-Item -ItemType Directory -Force -Path $env:ANDROID_USER_HOME | Out-Null
    $sdkProperty = 'sdk.dir=' + $sdkPath.Replace('\', '/')
    [System.IO.File]::WriteAllText((Join-Path $projectRoot 'local.properties'), $sdkProperty + "`n", [System.Text.UTF8Encoding]::new($false))
    $tasks = @(':app:assembleDebug')
    if ($Lint) { $tasks += ':app:lintDebug' }
    $flags = @('--no-daemon', '--console=plain')
    if ($Offline) { $flags += '--offline' }
    & (Join-Path $projectRoot 'gradlew.bat') -p $projectRoot @tasks @flags
    if ($LASTEXITCODE -ne 0) { throw "Build gagal (exit $LASTEXITCODE)." }
    if ($Deliver) {
        $apk = Join-Path $projectRoot 'app/build/outputs/apk/debug/app-debug.apk'
        $name = 'KN-C72-Handheld-0.1.0-lab-debug.apk'
        $dest = Join-Path $projectRoot "delivery/$name"
        Copy-Item -LiteralPath $apk -Destination $dest -Force
        $hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower()
        [System.IO.File]::WriteAllText((Join-Path $projectRoot 'delivery/SHA256SUMS.txt'), "$hash  $name`n", [System.Text.UTF8Encoding]::new($false))
        Write-Output "APK: $dest`nSHA256: $hash"
    }
} finally {
    $env:JAVA_HOME = $old.JAVA_HOME
    $env:GRADLE_USER_HOME = $old.GRADLE_USER_HOME
    $env:ANDROID_USER_HOME = $old.ANDROID_USER_HOME
}
