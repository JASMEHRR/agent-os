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

REM Python is found before anything else is attempted. Without this the first
REM thing a person without Python sees is
REM   'python' is not recognized as an internal or external command
REM which says nothing about what to do next. Both names are tried because the
REM official Windows installer provides the "py" launcher and the Microsoft
REM Store build provides "python", and a given machine may have only one.
set PY=
where python >nul 2>&1 && set PY=python
if not defined PY where py >nul 2>&1 && set PY=py
if not defined PY goto :nopython

REM Configuration is checked before the browser is opened. Without this the
REM browser would open at a server that is about to exit, and "cannot connect"
REM looks identical whether the server is slow to start or never started.
%PY% scripts\serve.py --check
if errorlevel 1 goto :failed

REM Launched in the background because serve.py blocks once running and nothing
REM after it would execute. open_studio.ps1 waits for the port to answer before
REM opening anything, so there is no "cannot connect" while the server binds,
REM and it opens an app window rather than a browser tab where it can.
start "" /b powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open_studio.ps1"

echo   Leave this window open while you use it.
echo   Close it, or press Ctrl-C, when you are done.
echo.

%PY% scripts\serve.py

echo.
echo   Post Studio has stopped.
pause
exit /b 0

:nopython
echo.
echo   Python is not installed on this computer, and this needs it.
echo.
echo   Get it from  https://www.python.org/downloads/
echo   On the first screen of the installer, tick
echo.
echo       Add python.exe to PATH
echo.
echo   before pressing Install. That tick box is the whole difference
echo   between this working and this message appearing again.
echo.
echo   Then close this window and double-click PostStudio again.
echo.
pause
exit /b 1

:failed
echo.
echo   Fix the above, then run this again. START_HERE.md walks through it.
echo.
pause
exit /b 1
