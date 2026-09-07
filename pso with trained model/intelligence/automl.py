"""
=====================================================================
 AutoML — Phase 4 (Step 4.1)
=====================================================================
 Automated model selection, light hyperparameter tuning, and
 ensembling for the tabular traffic prediction task:

   1. Candidates  : RandomForest, GradientBoosting, Ridge, plus a
                    voting ensemble of the top performers
   2. Tuning      : small randomized search per candidate
                    (fast, CPU-friendly)
   3. Selection   : best model by mean R² across the 4 direction
                    targets; writes saved_models/automl_report.json
                    and saves the winner as
                    saved_models/automl_best_model.pkl

 The production API keeps loading rf_model.pkl; this module is the
 offline tool that justifies (or replaces) that choice.

 Usage:
     python -m intelligence.automl                 # full run
     python -m intelligence.automl --quick         # lighter search
=====================================================================
"""

import argparse
import itertools
import json
import os
import pickle
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import (GradientBoostingRegressor,
                              RandomForestRegressor,
                              VotingRegressor)
from sklearn.linear_model import Ridge
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "pso_traffic_preprocessed.csv")
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")
REPORT_PATH = os.path.join(MODEL_DIR, "automl_report.json")
BEST_MODEL_PATH = os.path.join(MODEL_DIR, "automl_best_model.pkl")

FEATURES = ["time_step", "hour", "density", "avg_wait_time", "congestion_level_enc"]
TARGETS = ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]
CONGESTION_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

RANDOM_SEED = 42
TEST_SIZE = 0.2

# Light randomized-search grids (kept small for CPU runs)
GRIDS = {
    "random_forest": {
        "n_estimators": [80, 120, 150],
        "min_samples_leaf": [1, 2, 4],
    },
    "gradient_boosting": {
        "n_estimators": [100, 150],
        "learning_rate": [0.05, 0.1],
        "max_depth": [2, 3],
    },
    "ridge": {
        "alpha": [0.1, 1.0, 10.0],
    },
}


# ── DATA ───────────────────────────────────────────────────────

def load_data():
    """Load features/targets from the training CSV."""
    df = pd.read_csv(DATA_FILE)
    if "congestion_level_enc" not in df.columns and "congestion_level" in df.columns:
        if not pd.api.types.is_numeric_dtype(df["congestion_level"]):
            df["congestion_level_enc"] = df["congestion_level"].map(CONGESTION_MAP)
    missing = [c for c in FEATURES + TARGETS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    X = df[FEATURES].values
    y = df[TARGETS].values
    return train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_SEED)


# ── MODEL FACTORY ──────────────────────────────────────────────

def _make_base(name: str, params: Dict[str, Any]):
    """Raw single-output estimator (usable inside VotingRegressor)."""
    if name == "random_forest":
        return RandomForestRegressor(random_state=RANDOM_SEED, n_jobs=-1, **params)
    if name == "gradient_boosting":
        return GradientBoostingRegressor(random_state=RANDOM_SEED, **params)
    if name == "ridge":
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import make_pipeline
        return make_pipeline(StandardScaler(), Ridge(**params))
    raise ValueError(f"Unknown candidate family: {name}")


def _make_candidate(name: str, params: Dict[str, Any]):
    """Instantiate a multi-output candidate by family name."""
    if name == "ensemble":
        # members: list of (family_name, params). VotingRegressor works
        # on 1-D targets, so wrap it once for the 4 directions and keep
        # the members as raw single-output estimators.
        members = params.pop("members")
        estimators = [
            (fam, _make_base(fam, dict(prms))) for fam, prms in members
        ]
        return _MultiOutput(VotingRegressor(estimators))
    return _MultiOutput(_make_base(name, params))


class _MultiOutput(RegressorMixin, BaseEstimator):
    """Multi-output wrapper for single-output regressors.

    Inherits sklearn's estimator protocol (tags, cloning, get/set
    params) so it can be nested inside VotingRegressor.
    """

    def __init__(self, base=None):
        self.base = base
        self.models_ = []

    def fit(self, X, y):
        import copy
        self.models_ = []
        for i in range(y.shape[1]):
            m = copy.deepcopy(self.base)
            m.fit(X, y[:, i])
            self.models_.append(m)
        return self

    def predict(self, X):
        cols = [m.predict(X) for m in self.models_]
        return np.column_stack(cols)


# ── SEARCH ─────────────────────────────────────────────────────

def _random_param_configs(family: str, max_configs: int) -> List[Dict[str, Any]]:
    """Enumerate (deterministically shuffled) param grid configs."""
    grid = GRIDS.get(family, {})
    keys = list(grid)
    combos = list(itertools.product(*(grid[k] for k in keys)))
    if not combos:
        return [{}]
    # Deterministic shuffle for variety without a random module import
    order = sorted(range(len(combos)), key=lambda i: (i * 7919) % len(combos))
    combos = [combos[i] for i in order][:max_configs]
    return [dict(zip(keys, combo)) for combo in combos]


def run_automl(quick: bool = False) -> Dict[str, Any]:
    """
    Run candidate tuning + selection; returns the report dict and
    persists it plus the winning model.
    """
    start = time.time()
    X_train, X_test, y_train, y_test = load_data()
    max_configs = 2 if quick else 3
    print(f"Data: {X_train.shape[0]} train / {X_test.shape[0]} test rows")

    results: List[Dict[str, Any]] = []
    fitted: List[Tuple[str, Any, float]] = []

    for family in GRIDS:
        best_for_family = None
        print(f"\n-- {family} --")
        for params in _random_param_configs(family, max_configs):
            try:
                model = _make_candidate(family, dict(params))
                model.fit(X_train, y_train)
                pred = model.predict(X_test)
                r2 = float(np.mean([r2_score(y_test[:, i], pred[:, i])
                                    for i in range(len(TARGETS))]))
                mae = float(np.mean([mean_absolute_error(y_test[:, i], pred[:, i])
                                     for i in range(len(TARGETS))]))
            except Exception as e:
                logger.warning(f"{family} config {params} failed: {e}")
                continue
            print(f"  {params} -> R2={r2:.4f}  MAE={mae:.4f}")
            if best_for_family is None or r2 > best_for_family[1]:
                best_for_family = (params, r2, mae, model)

        if best_for_family:
            params, r2, mae, model = best_for_family
            results.append({
                "model": family,
                "params": params,
                "avg_r2": round(r2, 4),
                "avg_mae": round(mae, 4),
            })
            fitted.append((family, model, r2))

    if not results:
        raise RuntimeError("All AutoML candidates failed to train")

    # ── Ensemble of the top-2 families ────────────────────────
    fitted.sort(key=lambda item: item[2], reverse=True)
    if len(fitted) >= 2 and not quick:
        print("\n-- ensemble --")
        try:
            members = []
            for name, _model, _r2 in fitted[:2]:
                params_for = next(
                    (r["params"] for r in results if r["model"] == name), {}
                )
                members.append((name, params_for))
            ens = _make_candidate("ensemble", {"members": members})
            ens.fit(X_train, y_train)
            pred = ens.predict(X_test)
            r2 = float(np.mean([r2_score(y_test[:, i], pred[:, i])
                                for i in range(len(TARGETS))]))
            mae = float(np.mean([mean_absolute_error(y_test[:, i], pred[:, i])
                                 for i in range(len(TARGETS))]))
            print(f"  top-2 voting ensemble -> R2={r2:.4f}  MAE={mae:.4f}")
            results.append({
                "model": "ensemble(top-2)",
                "params": {"members": [n for n, _ in members]},
                "avg_r2": round(r2, 4),
                "avg_mae": round(mae, 4),
            })
            fitted.append(("ensemble(top-2)", ens, r2))
        except Exception as e:
            logger.warning(f"Ensemble training failed: {e}")

    results.sort(key=lambda r: r["avg_r2"], reverse=True)
    winner_name, winner_model, winner_r2 = fitted[
        max(range(len(fitted)), key=lambda i: fitted[i][2])
    ]

    elapsed = round(time.time() - start, 1)
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_s": elapsed,
        "quick_mode": quick,
        "dataset": {"train_rows": int(X_train.shape[0]),
                    "test_rows": int(X_test.shape[0])},
        "features": FEATURES,
        "targets": TARGETS,
        "results": results,
        "best_model": {
            "name": winner_name,
            "avg_r2": round(winner_r2, 4),
            "saved_as": os.path.basename(BEST_MODEL_PATH),
        },
        "note": "Production API continues to serve rf_model.pkl; "
                "activate the AutoML winner by replacing rf_model.pkl "
                "or updating the prediction service.",
    }

    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    with open(BEST_MODEL_PATH, "wb") as f:
        pickle.dump(winner_model, f)

    print("\n" + "=" * 60)
    print(f"  AutoML winner: {winner_name} (R2={winner_r2:.4f})")
    print(f"  Report: {REPORT_PATH}")
    print(f"  Model:  {BEST_MODEL_PATH}")
    print("=" * 60)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Traffic prediction AutoML")
    parser.add_argument("--quick", action="store_true",
                        help="Lighter search (2 configs/family, no ensemble)")
    args = parser.parse_args()
    run_automl(quick=args.quick)
