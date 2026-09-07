"""
=====================================================================
 Deep Sequence Model (LSTM) — Phase 4 (Step 4.1, optional)
=====================================================================
 A companion to the Random Forest predictor: a small LSTM that learns
 temporal patterns over sequences of traffic observations and predicts
 the next step's per-direction vehicle counts.

 This module is OPTIONAL and standalone — it imports torch lazily and
 is NOT imported by the application at startup. The default runtime
 forecaster (intelligence/forecaster.py) uses Holt smoothing, and this
 module is the reference implementation for switching to deep
 sequence models.

 Usage:
     python -m intelligence.deep_model          # train + evaluate
     python -m intelligence.deep_model --epochs 15

 Input  : last N observations of [time_step, hour, density,
                                  avg_wait_time, congestion_level_enc]
 Output : next-step [north, south, east, west] vehicle counts
=====================================================================
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, "pso_traffic_preprocessed.csv")
MODEL_DIR = os.path.join(BASE_DIR, "saved_models")

FEATURES = ["time_step", "hour", "density", "avg_wait_time", "congestion_level_enc"]
TARGETS = ["north_vehicles", "south_vehicles", "east_vehicles", "west_vehicles"]
CONGESTION_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

WINDOW = 30      # observations of context
HIDDEN = 32
LAYERS = 1
HEADS = 4        # attention heads (transformer)

# Supported architectures: "lstm" (default) and "transformer"
MODEL_TYPES = ("lstm", "transformer")
MODEL_FILES = {
    "lstm": "lstm_model.pt",
    "transformer": "transformer_model.pt",
}


def load_sequences(seq_len: int = WINDOW, test_size: float = 0.2, seed: int = 42):
    """
    Build sliding-window sequences from the training CSV.

    Rows are sorted by time_step so windows capture real temporal
    continuity.

    Returns
    -------
    tuple
        (X_train, y_train, X_test, y_test) numpy arrays.
    """
    df = pd.read_csv(DATA_FILE)

    # Encode congestion level if present as text (works with both the
    # legacy object dtype and pandas >= 3.0 str dtype).
    if "congestion_level_enc" not in df.columns and "congestion_level" in df.columns:
        if not pd.api.types.is_numeric_dtype(df["congestion_level"]):
            df["congestion_level_enc"] = (
                df["congestion_level"].map(CONGESTION_MAP)
            )
            if df["congestion_level_enc"].isna().any():
                raise ValueError(
                    "Unmapped congestion_level values in dataset: "
                    f"{sorted(df.loc[df['congestion_level_enc'].isna(),
                                    'congestion_level'].unique())}"
                )
    if "congestion_level_enc" not in df.columns:
        raise ValueError("congestion_level_enc column missing from dataset")

    df = df.sort_values("time_step").reset_index(drop=True)

    X_all = df[FEATURES].values.astype(np.float32)
    y_all = df[TARGETS].values.astype(np.float32)

    xs, ys = [], []
    for i in range(seq_len, len(X_all)):
        xs.append(X_all[i - seq_len:i])
        ys.append(y_all[i])
    xs = np.asarray(xs)
    ys = np.asarray(ys)

    n_test = int(len(xs) * test_size)
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(xs))
    test_idx = idx[:n_test]
    train_idx = idx[n_test:]
    return xs[train_idx], ys[train_idx], xs[test_idx], ys[test_idx]


def build_model(device=None, model_type: str = "lstm"):
    """Build the sequence model (torch imported lazily).

    model_type: "lstm" (recurrent baseline) or "transformer"
    (multi-head self-attention over the observation window).
    """
    import torch
    import torch.nn as nn

    model_type = model_type.lower()
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unknown model_type '{model_type}' — choose from {MODEL_TYPES}")

    if model_type == "lstm":
        class LSTMForecaster(nn.Module):
            def __init__(self, n_features: int, hidden: int, n_layers: int, n_targets: int):
                super().__init__()
                self.lstm = nn.LSTM(
                    n_features, hidden, n_layers,
                    batch_first=True,
                )
                self.head = nn.Linear(hidden, n_targets)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :])

        model = LSTMForecaster(len(FEATURES), HIDDEN, LAYERS, len(TARGETS))
    else:
        class TransformerForecaster(nn.Module):
            """Self-attention over the observation window (Step 4.1).

            Input projection → TransformerEncoder (multi-head attention
            captures long-range dependencies across the window) →
            mean-pool over time → linear head to the 4 targets.
            """
            def __init__(self, n_features: int, d_model: int, n_heads: int,
                         n_layers: int, n_targets: int):
                super().__init__()
                self.input_proj = nn.Linear(n_features, d_model)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=n_heads,
                    dim_feedforward=d_model * 4,
                    dropout=0.1,
                    batch_first=True,
                )
                self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
                self.head = nn.Linear(d_model, n_targets)

            def forward(self, x):
                h = self.input_proj(x)
                h = self.encoder(h)
                return self.head(h.mean(dim=1))

        model = TransformerForecaster(
            len(FEATURES), HIDDEN, HEADS, LAYERS, len(TARGETS)
        )

    model.to(device or ("cuda" if torch.cuda.is_available() else "cpu"))
    return model


def train(epochs: int = 10, batch_size: int = 256, seq_len: int = WINDOW,
          model_type: str = "lstm"):
    """Train and evaluate a sequence model, saving to saved_models/.

    model_type: "lstm" → lstm_model.pt, "transformer" → transformer_model.pt
    """
    try:
        import torch
        import torch.nn as nn
    except ImportError:
        print("torch is not installed — deep sequence model unavailable.")
        print("Install with: pip install torch  (CPU build is sufficient)")
        return None

    model_type = model_type.lower()
    if model_type not in MODEL_TYPES:
        raise ValueError(f"Unknown model_type '{model_type}' — choose from {MODEL_TYPES}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[{model_type.upper()}] Loading sequences (window={seq_len}) from {DATA_FILE}")
    X_train, y_train, X_test, y_test = load_sequences(seq_len)
    print(f"  Train sequences: {len(X_train)}  Test sequences: {len(X_test)}")

    model = build_model(device, model_type=model_type)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()

    X_tr = torch.tensor(X_train, device=device)
    y_tr = torch.tensor(y_train, device=device)
    X_te = torch.tensor(X_test, device=device)

    dataset = torch.utils.data.TensorDataset(X_tr, y_tr)
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model.train()
    for epoch in range(epochs):
        total_loss = 0.0
        for xb, yb in loader:
            optimizer.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(xb)
        print(f"  Epoch {epoch + 1}/{epochs}  loss={total_loss / len(X_train):.4f}")

    # Evaluate on the test split
    model.eval()
    with torch.no_grad():
        pred = model(X_te).cpu().numpy()
    mae_per_target = np.mean(np.abs(pred - y_test), axis=0)
    avg_mae = float(np.mean(mae_per_target))
    print("\nTest MAE per direction:")
    for i, target in enumerate(TARGETS):
        print(f"  {target:<22} MAE={mae_per_target[i]:.4f}")
    print(f"  {'AVERAGE':<22} MAE={avg_mae:.4f}")

    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, MODEL_FILES[model_type])
    torch.save({
        "state_dict": model.state_dict(),
        "config": {"model_type": model_type,
                   "n_features": len(FEATURES), "hidden": HIDDEN,
                   "heads": HEADS if model_type == "transformer" else None,
                   "layers": LAYERS, "n_targets": len(TARGETS),
                   "window": seq_len, "features": FEATURES,
                   "targets": TARGETS},
        "metrics": {"avg_mae": round(avg_mae, 4),
                    "mae_per_target": [round(m, 4) for m in mae_per_target]},
    }, path)
    print(f"\nModel saved: {path}")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the traffic sequence forecaster")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--window", type=int, default=WINDOW)
    parser.add_argument("--model-type", choices=MODEL_TYPES, default="lstm",
                        help="Architecture to train (default: lstm)")
    args = parser.parse_args()
    train(epochs=args.epochs, seq_len=args.window, model_type=args.model_type)