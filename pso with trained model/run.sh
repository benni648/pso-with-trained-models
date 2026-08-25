#!/bin/bash
# =====================================================================
# PSO Traffic Signal Optimization - Run Script (Linux/Mac)
# =====================================================================
# This script sets up and runs the application

echo "====================================================================="
echo "PSO Smart Traffic Signal Optimization"
echo "Professional Edition v1.0"
echo "====================================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

echo "[*] Checking virtual environment..."
if [ ! -d venv ]; then
    echo "[*] Creating virtual environment..."
    python3 -m venv venv
fi

echo "[*] Activating virtual environment..."
source venv/bin/activate

echo "[*] Installing/updating dependencies..."
pip install -r requirements.txt -q

echo ""
echo "====================================================================="
echo "Starting PSO Traffic API Server"
echo "====================================================================="
echo ""
echo "Dashboard:  http://localhost:5000"
echo "API Docs:   http://localhost:5000/docs"
echo "API:        http://localhost:5000/api/health"
echo ""
echo "Credentials:"
echo "  Admin:    admin@pso.com / admin123"
echo "  Operator: operator@pso.com / operator123"
echo "  Viewer:   viewer@pso.com / viewer123"
echo ""
echo "Press CTRL+C to stop"
echo "====================================================================="
echo ""

python3 api/app.py
