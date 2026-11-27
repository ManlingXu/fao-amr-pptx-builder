@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto deps
py -3.12 -m venv .venv
if not errorlevel 1 goto deps
py -3.11 -m venv .venv
if not errorlevel 1 goto deps
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if errorlevel 1 goto python_failed
py -3 -m venv .venv
if errorlevel 1 goto failed

:deps
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 11))"
if errorlevel 1 goto python_failed
".venv\Scripts\python.exe" -m pip show presentation-search-backend >nul 2>&1
if errorlevel 1 goto install
".venv\Scripts\python.exe" -c "import uvicorn, python_multipart; from presentation_search.local_brief import build_brief" >nul 2>&1
if not errorlevel 1 goto corpus
:install
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed

:corpus
if "%~1"=="" goto full
if /i "%~1"=="--refresh" goto refresh
echo Opening the explicitly selected corpus: "%~1"
".venv\Scripts\python.exe" scripts\serve_amr_brief.py --corpus-dir "%~1" --open-browser
goto finished
:full
".venv\Scripts\python.exe" scripts\prepare_amr_corpus.py --serve
goto finished
:refresh
".venv\Scripts\python.exe" scripts\prepare_amr_corpus.py --refresh --serve
:finished
if not errorlevel 1 exit /b 0
goto failed
:python_failed
echo A Python 3.11 or later virtual environment is required. Check installed versions with py -0p.
echo If .venv uses an older interpreter, rename it and run this launcher again.
:failed
echo Review the message above.
pause
exit /b 1
