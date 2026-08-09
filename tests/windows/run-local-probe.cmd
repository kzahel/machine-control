@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0local-probe.ps1" ^
  -Executable "%ProgramData%\MachineControl\runtime\machine-control-windows.exe"
