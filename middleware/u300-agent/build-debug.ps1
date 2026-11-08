param([switch]$IncludeAndroidTests, [switch]$Lint, [string]$ToolRoot, [switch]$Offline)
# Build APK debug (+ APK androidTest, + lint). Toolchain: -ToolRoot <folder android-build> | env KN_ANDROID_TOOLS |
# <workspace>/work/android-build (pola 0.4). local.properties dibuat di sini dan TIDAK di-commit.
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if (-not $ToolRoot) { $ToolRoot = $env:KN_ANDROID_TOOLS }
if (-not $ToolRoot) { $ToolRoot = Join-Path (Get-Item -LiteralPath $projectRoot).Parent.Parent.Parent.FullName 'work/android-build' }
$jdkPath = Join-Path $ToolRoot 'jdk'
$sdkPath = Join-Path $ToolRoot 'sdk'
if (-not (Test-Path -LiteralPath (Join-Path $jdkPath 'bin/java.exe'))) { throw 'JDK lokal belum tersedia. Lihat README.' }
if (-not (Test-Path -LiteralPath (Join-Path $sdkPath 'platforms/android-34/android.jar'))) { throw 'SDK Android 34 belum tersedia.' }
$oldJavaHome = $env:JAVA_HOME
$oldGradleHome = $env:GRADLE_USER_HOME
$oldAndroidUserHome = $env:ANDROID_USER_HOME
try {
    $env:JAVA_HOME = $jdkPath
    $env:GRADLE_USER_HOME = Join-Path $ToolRoot 'gradle-home'
    $env:ANDROID_USER_HOME = Join-Path $ToolRoot 'android-user'
    New-Item -ItemType Directory -Force -Path $env:ANDROID_USER_HOME | Out-Null
    $sdkProperty = 'sdk.dir=' + $sdkPath.Replace('\', '/')
    [System.IO.File]::WriteAllText((Join-Path $projectRoot 'local.properties'), $sdkProperty + "`n", [System.Text.UTF8Encoding]::new($false))
    $tasks=@(':app:assembleDebug')
    if ($IncludeAndroidTests) { $tasks += ':app:assembleDebugAndroidTest' }
    if ($Lint) { $tasks += ':app:lintDebug' }
    $flags=@('--no-daemon','--console=plain')
    if ($Offline) { $flags += '--offline' }
    & (Join-Path $projectRoot 'gradlew.bat') -p $projectRoot @tasks @flags
    if ($LASTEXITCODE -ne 0) { throw "Build gagal (exit $LASTEXITCODE)." }
} finally {
    $env:JAVA_HOME = $oldJavaHome
    $env:GRADLE_USER_HOME = $oldGradleHome
    $env:ANDROID_USER_HOME = $oldAndroidUserHome
}
