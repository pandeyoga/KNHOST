param([switch]$IncludeAndroidTests, [switch]$Lint)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$workspaceRoot = (Get-Item -LiteralPath $projectRoot).Parent.Parent.Parent.FullName
$toolRoot = Join-Path $workspaceRoot 'work/android-build'
$jdkPath = Join-Path $toolRoot 'jdk'
$sdkPath = Join-Path $toolRoot 'sdk'
if (-not (Test-Path -LiteralPath (Join-Path $jdkPath 'bin/java.exe'))) { throw 'JDK lokal belum tersedia. Lihat README.' }
if (-not (Test-Path -LiteralPath (Join-Path $sdkPath 'platforms/android-34/android.jar'))) { throw 'SDK Android 34 belum tersedia.' }
$oldJavaHome = $env:JAVA_HOME
$oldGradleHome = $env:GRADLE_USER_HOME
$oldAndroidUserHome = $env:ANDROID_USER_HOME
try {
    $env:JAVA_HOME = $jdkPath
    $env:GRADLE_USER_HOME = Join-Path $toolRoot 'gradle-home'
    $env:ANDROID_USER_HOME = Join-Path $toolRoot 'android-user'
    New-Item -ItemType Directory -Force -Path $env:ANDROID_USER_HOME | Out-Null
    $sdkProperty = 'sdk.dir=' + $sdkPath.Replace('\', '/')
    [System.IO.File]::WriteAllText((Join-Path $projectRoot 'local.properties'), $sdkProperty + "`n", [System.Text.UTF8Encoding]::new($false))
    $tasks=@(':app:assembleDebug')
    if ($IncludeAndroidTests) { $tasks += ':app:assembleDebugAndroidTest' }
    if ($Lint) { $tasks += ':app:lintDebug' }
    & (Join-Path $projectRoot 'gradlew.bat') -p $projectRoot @tasks --no-daemon --console=plain
    if ($LASTEXITCODE -ne 0) { throw "Build gagal (exit $LASTEXITCODE)." }
} finally {
    $env:JAVA_HOME = $oldJavaHome
    $env:GRADLE_USER_HOME = $oldGradleHome
    $env:ANDROID_USER_HOME = $oldAndroidUserHome
}
