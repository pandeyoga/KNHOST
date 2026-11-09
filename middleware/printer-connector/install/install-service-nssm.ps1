# Pasang KN Printer Connector sebagai layanan Windows memakai NSSM (https://nssm.cc).
# Jalankan di PowerShell "Run as Administrator" dari folder printer-connector:
#   .\install\install-service-nssm.ps1 -Python "C:\Program Files\Python311\python.exe" -Nssm "C:\Tools\nssm.exe"
param(
  [Parameter(Mandatory = $true)][string]$Python,
  [Parameter(Mandatory = $true)][string]$Nssm,
  [string]$Config = "C:\ProgramData\KN-Printer-Connector\config.json",
  [string]$ServiceName = "KNPrinterConnector"
)
$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path $Config)) { throw "Konfigurasi tidak ditemukan: $Config (salin dari config.example.json)" }
& $Python -m kn_printer_connector version | Out-Null
& $Nssm install $ServiceName $Python "-m" "kn_printer_connector" "run" "--config" $Config
& $Nssm set $ServiceName AppDirectory $Here
& $Nssm set $ServiceName DisplayName "KN Printer Connector (CP30EN)"
& $Nssm set $ServiceName Description "Jembatan ERP Kain Nusantara ke printer label RFID gudang"
& $Nssm set $ServiceName Start SERVICE_AUTO_START
# berhenti rapi: kirim Ctrl+C dan beri waktu label yang sedang dicetak dicatat ke ledger
& $Nssm set $ServiceName AppStopMethodConsole 60000
& $Nssm set $ServiceName AppExit Default Restart
& $Nssm set $ServiceName AppRestartDelay 10000
& $Nssm set $ServiceName AppStdout "C:\ProgramData\KN-Printer-Connector\logs\service-stdout.log"
& $Nssm set $ServiceName AppStderr "C:\ProgramData\KN-Printer-Connector\logs\service-stderr.log"
& $Nssm set $ServiceName AppRotateFiles 1
& $Nssm set $ServiceName AppRotateBytes 5000000
Write-Host "Layanan $ServiceName terpasang. Atur variabel lingkungan device key (lihat README), lalu:"
Write-Host "  & `"$Nssm`" set $ServiceName AppEnvironmentExtra KN_PRN_RCM1_KEY=<key>   (atau pakai device_key_file)"
Write-Host "  Start-Service $ServiceName"
