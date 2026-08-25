@echo off
REM =====================================================================
REM PSO Traffic Signal Optimization - Run Script (Windows)
REM =====================================================================
REM This script sets up and runs the application

echo =====================================================================
echo PSO Smart Traffic Signal Optimization
echo Professional Edition v1.0
echo =====================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

echo [*] Checking virtual environment...
if not exist venv (
    echo [*] Creating virtual environment...
    python -m venv venv
)

echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

echo [*] Installing/updating dependencies...
pip install -r requirements.txt -q

echo.
echo =====================================================================
echo Starting PSO Traffic API Server
echo =====================================================================
echo.
echo Dashboard:  http://localhost:5000
echo API Docs:   http://localhost:5000/docs
echo API:        http://localhost:5000/api/health
echo.
echo Credentials:
echo   Admin:    admin@pso.com / admin123
echo   Operator: operator@pso.com / operator123
echo   Viewer:   viewer@pso.com / viewer123
echo.
echo Press CTRL+C to stop
echo =====================================================================
echo.

python api/app.py

pause
