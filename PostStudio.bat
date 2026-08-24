@echo off
REM Double-click this to open Post Studio. Nothing to type.
REM
REM Everything you write is saved in agent.db, so closing this window loses
REM nothing. It just stops the server until you open it again.

cd /d "%~dp0"
title Post Studio

echo.
echo   Starting Post Studio...
echo.

REM Configuration is checked before the browser is opened. Without this the
REM browser would open at a server that is about to exit, and "cannot connect"
REM looks identical whether the server is slow to start or never started.
python scripts\serve.py --check
if errorlevel 1 goto :failed

REM Opened before the server, because serve.py blocks once running and nothing
REM after it would execute. The browser retries on its own during the second
REM or so the server takes to bind.
start "" http://127.0.0.1:8765

echo   Leave this window open while you use it.
echo   Close it, or press Ctrl-C, when you are done.
echo.

python scripts\serve.py

echo.
echo   Post Studio has stopped.
pause
exit /b 0

:failed
echo.
echo   Fix the above, then run this again. START_HERE.md walks through it.
echo.
pause
exit /b 1
