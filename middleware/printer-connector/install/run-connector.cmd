@echo off
rem Dipakai Task Scheduler (alternatif NSSM): jalankan connector, ulangi bila berhenti tak terduga.
rem Atur PYTHON dan KN_CONNECTOR_CONFIG sesuai PC gudang.
setlocal
if "%PYTHON%"=="" set PYTHON=C:\Program Files\Python311\python.exe
if "%KN_CONNECTOR_CONFIG%"=="" set KN_CONNECTOR_CONFIG=C:\ProgramData\KN-Printer-Connector\config.json
cd /d "%~dp0.."
:loop
"%PYTHON%" -m kn_printer_connector run --config "%KN_CONNECTOR_CONFIG%"
echo Connector berhenti (kode %ERRORLEVEL%) - mulai ulang dalam 10 detik...
timeout /t 10 /nobreak >nul
goto loop
