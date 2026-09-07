"""
=====================================================================
 PSO Smart Traffic — Model Training Script
=====================================================================
 Trains a Random Forest model on the preprocessed traffic data
 and saves it to saved_models/rf_model.pkl.

 Usage:
    python train_model.py

 Output:
    saved_models/rf_model.pkl
    saved_models/model_meta.json
=====================================================================
"""

import os
import json
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

# ── PATHS ───────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "pso_traffic_preprocessed.csv")
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
RF_MODEL_PATH = os.path.join(MODEL_DIR, "rf_model.pkl")
META_PATH = os.path.join(MODEL_DIR, "model_meta.json")

# ── CONFIGURATION ───────────────────────────────────────────────

TEST_SIZE = 0.20
RANDOM_SEED = 42

FEATURES = ["time_step", "hour", "density", "avg_wait_time", "congestion_level_enc"]
TARGETS = ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]
CONGESTION_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Random Forest hyperparameters
RF_PARAMS = {
    "n_estimators": 150,
    "max_depth": None,
    "min_samples_split": 5,
    "min_samples_leaf": 2,
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
}


def load_and_prepare_data():
    """Load CSV and prepare features/targets."""
    print(f"Loading data from: {DATA_FILE}")

    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Training data not found: {DATA_FILE}")

    df = pd.read_csv(DATA_FILE)
    print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

    # Encode congestion_level if it's a string column
    if "congestion_level" in df.columns:
        if df["congestion_level"].dtype == object or str(df["congestion_level"].dtype) == "str":
            df["congestion_level_enc"] = df["congestion_level"].map(CONGESTION_MAP)
        else:
            # Already numeric, just rename
            df["congestion_level_enc"] = df["congestion_level"]
    elif "congestion_level_enc" not in df.columns:
        # Try to find any congestion column
        for col in df.columns:
            if "congestion" in col.lower():
                if df[col].dtype == object or str(df[col].dtype) == "str":
                    df["congestion_level_enc"] = df[col].map(CONGESTION_MAP)
                else:
                    df["congestion_level_enc"] = df[col]
                break

    # Verify all required columns exist
    missing_features = [f for f in FEATURES if f not in df.columns]
    missing_targets = [t for t in TARGETS if t not in df.columns]

    if missing_features:
        raise ValueError(f"Missing feature columns: {missing_features}")
    if missing_targets:
        raise ValueError(f"Missing target columns: {missing_targets}")

    X = df[FEATURES].values
    y = df[TARGETS].values

    print(f"  Features: {FEATURES}")
    print(f"  Targets: {TARGETS}")
    print(f"  X shape: {X.shape}, y shape: {y.shape}")

    return X, y, df


def train_model(X, y):
    """Train Random Forest model."""
    print("\nTraining Random Forest model...")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED
    )

    print(f"  Train samples: {len(X_train)}")
    print(f"  Test samples:  {len(X_test)}")

    model = RandomForestRegressor(**RF_PARAMS)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)

    metrics = {}
    print("\n  Model Performance:")
    print("  " + "=" * 50)

    for i, target in enumerate(TARGETS):
        mae = mean_absolute_error(y_test[:, i], y_pred[:, i])
        r2 = r2_score(y_test[:, i], y_pred[:, i])
        metrics[target] = {"mae": round(mae, 4), "r2": round(r2, 4)}
        print(f"  {target:<22} MAE={mae:.4f}  R²={r2:.4f}")

    avg_r2 = np.mean([m["r2"] for m in metrics.values()])
    avg_mae = np.mean([m["mae"] for m in metrics.values()])
    print("  " + "=" * 50)
    print(f"  {'AVERAGE':<22} MAE={avg_mae:.4f}  R²={avg_r2:.4f}")

    return model, metrics, len(X_train), len(X_test)


def save_model(model, metrics, train_rows, test_rows):
    """Save model and metadata."""
    os.makedirs(MODEL_DIR, exist_ok=True)

    # Save model
    with open(RF_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"\n  Model saved: {RF_MODEL_PATH}")

    # Save metadata
    meta = {
        "features": FEATURES,
        "targets": TARGETS,
        "congestion_map": CONGESTION_MAP,
        "test_size": TEST_SIZE,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "random_forest_metrics": metrics,
        "random_forest_params": RF_PARAMS,
        "recommended_model": "rf_model.pkl",
    }

    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)
    print(f"  Metadata saved: {META_PATH}")


def main():
    """Main training pipeline."""
    print("=" * 60)
    print("  PSO Smart Traffic — Model Training")
    print("=" * 60)

    X, y, df = load_and_prepare_data()
    model, metrics, train_rows, test_rows = train_model(X, y)
    save_model(model, metrics, train_rows, test_rows)

    print("\n" + "=" * 60)
    print("  Training complete!")
    print(f"  Model: {RF_MODEL_PATH}")
    print(f"  R² Score (avg): {np.mean([m['r2'] for m in metrics.values()]):.4f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
