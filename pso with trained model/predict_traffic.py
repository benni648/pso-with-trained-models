"""
=====================================================================
 PSO Smart Traffic Signal Optimization — Prediction Module
=====================================================================
 Usage:
    from predict_traffic import TrafficPredictor

    predictor = TrafficPredictor()
    result = predictor.predict({
        "time_step": 45,
        "hour": 8,
        "density": 0.72,
        "avg_wait_time": 38.5,
        "congestion_level": "HIGH"
    })
    print(result)
=====================================================================
"""

import os
import json
import pickle
import numpy as np
from typing import Union

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
MODEL_DIR       = "saved_models"
CONGESTION_MAP  = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
FEATURES        = ["time_step", "hour", "density", "avg_wait_time", "congestion_level_enc"]
TARGETS         = ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]


# ──────────────────────────────────────────────
# PREDICTOR CLASS
# ──────────────────────────────────────────────
class TrafficPredictor:
    """
    Wraps the trained Random Forest model.
    Exposes a single `.predict()` method for easy integration.
    """

    def __init__(self, model_name: str = "rf_model.pkl", model_dir: str = MODEL_DIR):
        model_path = os.path.join(model_dir, model_name)
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Model not found at '{model_path}'.\n"
                "Please run  python train_model.py  first."
            )
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

        meta_path = os.path.join(model_dir, "model_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                self.meta = json.load(f)
        else:
            self.meta = {}

        print(f"[TrafficPredictor] Loaded model: {model_name}")

    # ── Public API ────────────────────────────
    def predict(self, current_data: dict) -> dict:
        """
        Predict vehicle counts for the next time step.

        Parameters
        ----------
        current_data : dict with keys:
            - time_step        (int)   current simulation step
            - hour             (int)   hour of day  0–23
            - density          (float) traffic density  0.0–1.0
            - avg_wait_time    (float) average vehicle wait time in seconds
            - congestion_level (str)   "LOW" | "MEDIUM" | "HIGH"

        Returns
        -------
        dict with keys:
            - north_vehicles   (float)
            - south_vehicles   (float)
            - east_vehicles    (float)
            - west_vehicles    (float)
            - total_vehicles   (float)
            - input_snapshot   (dict)  echo of processed input
        """
        X = self._build_feature_vector(current_data)
        raw = self.model.predict(X)[0]                # shape (4,)
        raw = np.clip(raw, 0, None)                   # no negative vehicles

        result = {target: round(float(v), 4) for target, v in zip(TARGETS, raw)}
        result["total_vehicles"] = round(sum(result[t] for t in TARGETS), 4)
        result["input_snapshot"] = {k: current_data[k] for k in current_data}
        return result

    def predict_batch(self, records: list) -> list:
        """Predict for a list of dicts. Returns list of result dicts."""
        return [self.predict(r) for r in records]

    # ── Internal helpers ──────────────────────
    def _build_feature_vector(self, data: dict) -> np.ndarray:
        """Validate and encode one input dict into a 2-D numpy array."""
        required = {"time_step", "hour", "density", "avg_wait_time", "congestion_level"}
        missing = required - set(data.keys())
        if missing:
            raise ValueError(f"Missing input keys: {missing}")

        cong = str(data["congestion_level"]).upper()
        if cong not in CONGESTION_MAP:
            raise ValueError(
                f"congestion_level must be 'LOW', 'MEDIUM', or 'HIGH'. Got: '{cong}'"
            )

        row = [
            int(data["time_step"]),
            int(data["hour"]),
            float(data["density"]),
            float(data["avg_wait_time"]),
            CONGESTION_MAP[cong],
        ]
        return np.array([row])  # shape (1, 5)


# ──────────────────────────────────────────────
# STANDALONE DEMO
# ──────────────────────────────────────────────
if __name__ == "__main__":
    predictor = TrafficPredictor()

    # ── Example 1: Morning rush hour ──────────
    example_input = {
        "time_step": 45,
        "hour": 8,
        "density": 0.72,
        "avg_wait_time": 38.5,
        "congestion_level": "HIGH"
    }

    print("\n" + "="*55)
    print("  EXAMPLE PREDICTION — Morning Rush Hour")
    print("="*55)
    print(f"  Input : {example_input}")
    result = predictor.predict(example_input)
    print(f"\n  Predicted next-step vehicle counts:")
    for direction in ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]:
        print(f"    {direction:<22} {result[direction]:.2f}")
    print(f"    {'total_vehicles':<22} {result['total_vehicles']:.2f}")

    # ── Example 2: Low traffic midnight ───────
    example_input_2 = {
        "time_step": 10,
        "hour": 0,
        "density": 0.12,
        "avg_wait_time": 5.0,
        "congestion_level": "LOW"
    }

    print("\n" + "="*55)
    print("  EXAMPLE PREDICTION — Low Traffic (Midnight)")
    print("="*55)
    print(f"  Input : {example_input_2}")
    result2 = predictor.predict(example_input_2)
    print(f"\n  Predicted next-step vehicle counts:")
    for direction in ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]:
        print(f"    {direction:<22} {result2[direction]:.2f}")
    print(f"    {'total_vehicles':<22} {result2['total_vehicles']:.2f}")

    print("\n✅  Prediction demo complete!\n")
