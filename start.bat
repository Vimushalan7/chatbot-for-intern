@echo off
REM ══════════════════════════════════════════════════════════════════════
REM  PaperMind — Windows Quick-Start Script
REM  Run this from the project root: start.bat
REM ══════════════════════════════════════════════════════════════════════

echo.
echo  ██████╗  █████╗ ██████╗ ███████╗██████╗ ███╗   ███╗██╗███╗   ██╗██████╗
echo  ██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗████╗ ████║██║████╗  ██║██╔══██╗
echo  ██████╔╝███████║██████╔╝█████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║██║  ██║
echo  ██╔═══╝ ██╔══██║██╔═══╝ ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║██║  ██║
echo  ██║     ██║  ██║██║     ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║██████╔╝
echo  ╚═╝     ╚═╝  ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝
echo.
echo  AI Research Paper Assistant
echo ═══════════════════════════════════════════════════════════════════════
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ from https://python.org
    pause & exit /b 1
)

REM Check Ollama
ollama --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Ollama not found. Download from https://ollama.ai
    echo           The app will start but LLM features will not work.
    echo.
)

cd backend

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo [1/4] Creating Python virtual environment...
    python -m venv venv
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo [3/4] Installing dependencies (this may take a few minutes)...
pip install -r requirements.txt -q

echo [4/4] Starting FastAPI backend on http://localhost:8000
echo.
echo  Open frontend\index.html in your browser to use the app.
echo  API docs available at: http://localhost:8000/docs
echo.
echo  Press Ctrl+C to stop the server.
echo ═══════════════════════════════════════════════════════════════════════
echo.

uvicorn main:app --reload --host 0.0.0.0 --port 8000
