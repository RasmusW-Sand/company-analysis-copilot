@echo off
setlocal

set "PROJ=C:\Programmering\Finans\AI agents for market research"
set "LOGFILE=%PROJ%\watchlist\monitor.log"
set "PYTHON=%PROJ%\.venv\Scripts\python.exe"

cd /d "%PROJ%"

echo. >> "%LOGFILE%"
echo [%DATE% %TIME%] === Monitor startet === >> "%LOGFILE%"

call "%PROJ%\.venv\Scripts\activate.bat" >> "%LOGFILE%" 2>&1

"%PYTHON%" -m watchlist.monitor >> "%LOGFILE%" 2>&1

if %ERRORLEVEL% neq 0 (
    echo [%DATE% %TIME%] FEIL: monitor.py avsluttet med kode %ERRORLEVEL% >> "%LOGFILE%"
    exit /b %ERRORLEVEL%
)

echo [%DATE% %TIME%] === Monitor fullfort OK === >> "%LOGFILE%"
endlocal
