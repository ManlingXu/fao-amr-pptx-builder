@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto deps
py -3 -m venv .venv
if errorlevel 1 goto fail
:deps
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3,11))"
if errorlevel 1 goto version
".venv\Scripts\python.exe" -c "import fastapi,uvicorn,pptx,msal,pydantic_settings,multipart,xlsxwriter" >nul 2>&1
if not errorlevel 1 goto run
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto fail
:run
".venv\Scripts\python.exe" scripts\serve_studio.py %*
exit /b %errorlevel%
:version
echo Select Python 3.11+ with the Windows Python launcher and recreate .venv.
:fail
echo Studio could not start. Check the message above.
exit /b 1
