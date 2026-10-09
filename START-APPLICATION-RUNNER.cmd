@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run RUN-WINDOWS.cmd first.
 pause
 exit /b 1
)
pushd apps\web
call npx --no-install playwright install chromium
if errorlevel 1 (
 popd
 pause
 exit /b 1
)
popd
.venv\Scripts\python.exe -m careeros.apply_runner --interactive
pause
