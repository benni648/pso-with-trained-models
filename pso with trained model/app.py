"""
=====================================================================
 PSO Smart Traffic — Flask API Server  (app.py)
=====================================================================
 Exposes ML predictions + PSO optimized timings as JSON endpoints.
 The frontend JavaScript calls these endpoints every simulation tick.

 Endpoints:
   POST /predict         → ML prediction for next traffic step
   POST /optimize        → PSO optimized signal timings
   POST /predict-and-optimize → Both in one call (recommended)
   GET  /health          → Server status check

 Run:
   pip install flask flask-cors
   python app.py
 Then open:  http://localhost:5000
=====================================================================
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import numpy as np
import os
import sys

# ── make sure sibling modules are importable ──
sys.path.insert(0, os.path.dirname(__file__))

from predict_traffic import TrafficPredictor
from pso_integration import PSOOptimizer, pso_fitness

# ──────────────────────────────────────────────
# APP SETUP
# ──────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend")
CORS(app)   # allow requests from any origin (needed for local dev)

# Load once at startup — not on every request
predictor = TrafficPredictor()
pso       = PSOOptimizer(n_particles=30, n_iterations=50)

print("[SERVER] TrafficPredictor and PSOOptimizer ready.")


# ──────────────────────────────────────────────
# ROUTES
# ──────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main PSO Traffic dashboard."""
    return send_from_directory("frontend", "pso_traffic_dashboard_connected.html")


@app.route("/health", methods=["GET"])
def health():
    """Quick status check."""
    return jsonify({"status": "ok", "model": "rf_model.pkl"})


@app.route("/predict", methods=["POST"])
def predict():
    """
    Predict next-step vehicle counts from current traffic state.

    Request body (JSON):
    {
        "time_step":       45,
        "hour":            8,
        "density":         0.72,
        "avg_wait_time":   38.5,
        "congestion_level": "HIGH"
    }

    Response (JSON):
    {
        "north_vehicles": 4.55,
        "south_vehicles": 4.35,
        "east_vehicles":  4.31,
        "west_vehicles":  4.34,
        "total_vehicles": 17.55,
        "input_snapshot": { ... }
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    try:
        result = predictor.predict(data)
        return jsonify(result)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 422


@app.route("/optimize", methods=["POST"])
def optimize():
    """
    Run PSO on provided predicted vehicle counts.

    Request body (JSON):
    {
        "north_vehicles": 4.55,
        "south_vehicles": 4.35,
        "east_vehicles":  4.31,
        "west_vehicles":  4.34
    }

    Response (JSON):
    {
        "north_green": 42.0,
        "south_green": 38.5,
        "east_green":  41.0,
        "west_green":  39.5,
        "fitness":     12.34
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    try:
        result = pso.optimize(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/predict-and-optimize", methods=["POST"])
def predict_and_optimize():
    """
    ONE-CALL endpoint: predict traffic → run PSO → return both results.
    This is what the frontend dashboard uses every simulation tick.

    Request body (JSON):
    {
        "time_step":        45,
        "hour":             8,
        "density":          0.72,
        "avg_wait_time":    38.5,
        "congestion_level": "HIGH"
    }

    Response (JSON):
    {
        "prediction": {
            "north_vehicles": 4.55,
            "south_vehicles": 4.35,
            "east_vehicles":  4.31,
            "west_vehicles":  4.34,
            "total_vehicles": 17.55
        },
        "signal_timings": {
            "north_green": 42.0,
            "south_green": 38.5,
            "east_green":  41.0,
            "west_green":  39.5,
            "fitness":     12.34
        },
        "input": { ... }
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400

    try:
        prediction     = predictor.predict(data)
        signal_timings = pso.optimize(prediction)

        return jsonify({
            "prediction":     prediction,
            "signal_timings": signal_timings,
            "input":          data
        })
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 422
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  PSO Traffic API Server")
    print("  http://localhost:5000")
    print("  Press CTRL+C to stop")
    print("="*55 + "\n")
    app.run(debug=True, port=5000)
