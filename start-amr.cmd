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
set "AMR_INPUT=.local\amr"
if exist "%AMR_INPUT%\verified.csv" goto launch
if exist "%USERPROFILE%\Downloads\fao-amr-pptx-builder-main\.local\amr\verified.csv" set "AMR_INPUT=%USERPROFILE%\Downloads\fao-amr-pptx-builder-main\.local\amr"
:launch
if not "%~1"=="" set "AMR_INPUT=%~1"
echo Corpus: "%AMR_INPUT%"
if exist "%AMR_INPUT%\verified.csv" goto serve
echo To download and verify the source presentations, run this in a second PowerShell window from this project folder:
echo .\.venv\Scripts\python.exe scripts\fetch_public_corpus.py --catalog examples\public_corpus\amr\catalog.csv --corpus-dir "%AMR_INPUT%"
:serve
echo Open http://127.0.0.1:8765 in your browser. Press Ctrl+C here to stop.
".venv\Scripts\python.exe" scripts\serve_amr_brief.py --corpus-dir "%AMR_INPUT%"
if not errorlevel 1 exit /b 0
goto failed
:python_failed
echo A Python 3.11 or later virtual environment is required. Check installed versions with py -0p.
echo If .venv uses an older interpreter, rename it and run this launcher again.
:failed
echo Review the message above.
pause
exit /b 1
