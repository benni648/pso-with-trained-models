"""
=====================================================================
 PSO Smart Traffic Signal Optimization — PSO Integration Bridge
=====================================================================
 This module shows exactly HOW to:
   1. Call the ML predictor each simulation tick
   2. Feed predictions into your PSO optimizer
   3. Run PSO proactively on FUTURE traffic
=====================================================================
"""

import numpy as np
from predict_traffic import TrafficPredictor

# ──────────────────────────────────────────────────────────────────
# STEP A — Wrap your existing PSO fitness function
# ──────────────────────────────────────────────────────────────────

def pso_fitness(signal_timings: np.ndarray, predicted_vehicles: dict) -> float:
    """
    Your existing PSO fitness function — adapted to accept predictions.

    Parameters
    ----------
    signal_timings  : np.ndarray  shape (4,)  — [north_green, south_green,
                                                   east_green, west_green]
                      Values represent green-light durations (seconds).
    predicted_vehicles : dict     output from TrafficPredictor.predict()

    Returns
    -------
    float — lower is better (total weighted wait time estimate)
    """
    north_green, south_green, east_green, west_green = signal_timings

    # Pull predicted vehicle counts
    n = predicted_vehicles["north_vehicles"]
    s = predicted_vehicles["south_vehicles"]
    e = predicted_vehicles["east_vehicles"]
    w = predicted_vehicles["west_vehicles"]

    # Simple weighted wait-time heuristic
    # (replace with your actual fitness formula)
    cycle_time = north_green + south_green + east_green + west_green
    if cycle_time == 0:
        return float("inf")

    wait_n = n * (cycle_time - north_green) / north_green if north_green > 0 else n * 999
    wait_s = s * (cycle_time - south_green) / south_green if south_green > 0 else s * 999
    wait_e = e * (cycle_time - east_green)  / east_green  if east_green  > 0 else e * 999
    wait_w = w * (cycle_time - west_green)  / west_green  if west_green  > 0 else w * 999

    return wait_n + wait_s + wait_e + wait_w


# ──────────────────────────────────────────────────────────────────
# STEP B — Minimal PSO Optimizer (drop-in if you need one)
# ──────────────────────────────────────────────────────────────────

class PSOOptimizer:
    """
    Minimal Particle Swarm Optimizer for signal timing.
    Replace with your own full PSO if you already have one.
    """

    def __init__(
        self,
        n_particles: int = 30,
        n_iterations: int = 50,
        bounds: tuple = (5, 60),   # min/max green time in seconds
        w: float = 0.7,
        c1: float = 1.5,
        c2: float = 1.5,
    ):
        self.n_particles  = n_particles
        self.n_iterations = n_iterations
        self.bounds       = bounds
        self.w, self.c1, self.c2 = w, c1, c2
        self.n_dims = 4    # north, south, east, west

    def optimize(self, predicted_vehicles: dict) -> dict:
        """
        Run PSO using ML-predicted traffic as input.

        Returns best signal timings + fitness score.
        """
        low, high = self.bounds

        # Initialise particles & velocities
        pos = np.random.uniform(low, high, (self.n_particles, self.n_dims))
        vel = np.zeros_like(pos)

        p_best_pos = pos.copy()
        p_best_fit = np.array([
            pso_fitness(p, predicted_vehicles) for p in pos
        ])

        g_best_idx = np.argmin(p_best_fit)
        g_best_pos = p_best_pos[g_best_idx].copy()
        g_best_fit = p_best_fit[g_best_idx]

        for iteration in range(self.n_iterations):
            r1 = np.random.rand(self.n_particles, self.n_dims)
            r2 = np.random.rand(self.n_particles, self.n_dims)

            vel = (
                self.w  * vel
                + self.c1 * r1 * (p_best_pos - pos)
                + self.c2 * r2 * (g_best_pos  - pos)
            )
            pos = np.clip(pos + vel, low, high)

            fits = np.array([pso_fitness(p, predicted_vehicles) for p in pos])

            improved = fits < p_best_fit
            p_best_pos[improved] = pos[improved]
            p_best_fit[improved] = fits[improved]

            best_idx = np.argmin(p_best_fit)
            if p_best_fit[best_idx] < g_best_fit:
                g_best_fit = p_best_fit[best_idx]
                g_best_pos = p_best_pos[best_idx].copy()

        return {
            "north_green": round(float(g_best_pos[0]), 1),
            "south_green": round(float(g_best_pos[1]), 1),
            "east_green":  round(float(g_best_pos[2]), 1),
            "west_green":  round(float(g_best_pos[3]), 1),
            "fitness":     round(float(g_best_fit), 4),
        }


# ──────────────────────────────────────────────────────────────────
# STEP C — Main Simulation Loop
# ──────────────────────────────────────────────────────────────────

def run_simulation(total_steps: int = 10):
    """
    Full proactive optimization loop:
        1. Observe current traffic state
        2. Predict NEXT step with ML
        3. Run PSO on that prediction
        4. Apply optimized signal timings
        5. Advance to next step
    """
    predictor = TrafficPredictor()
    pso       = PSOOptimizer(n_particles=30, n_iterations=50)

    # Simulated starting state — replace with real sensor readings
    state = {
        "time_step":       0,
        "hour":            8,
        "density":         0.65,
        "avg_wait_time":   30.0,
        "congestion_level": "MEDIUM",
    }

    print("\n" + "="*65)
    print("  PSO SMART TRAFFIC — PROACTIVE OPTIMIZATION SIMULATION")
    print("="*65)

    for step in range(total_steps):
        state["time_step"] = step
        state["hour"]      = step % 24     # wrap hour for demo

        # ── 1. Predict next-step traffic ──────
        predicted = predictor.predict(state)

        # ── 2. Run PSO on predicted traffic ───
        best_timing = pso.optimize(predicted)

        # ── 3. Display results ─────────────────
        print(f"\n[Step {step:3d}]  hour={state['hour']:02d}  "
              f"density={state['density']:.2f}  "
              f"congestion={state['congestion_level']}")
        print(f"  Predicted  →  N={predicted['north_vehicles']:.2f}  "
              f"S={predicted['south_vehicles']:.2f}  "
              f"E={predicted['east_vehicles']:.2f}  "
              f"W={predicted['west_vehicles']:.2f}  "
              f"(total={predicted['total_vehicles']:.2f})")
        print(f"  PSO timing →  N_green={best_timing['north_green']}s  "
              f"S_green={best_timing['south_green']}s  "
              f"E_green={best_timing['east_green']}s  "
              f"W_green={best_timing['west_green']}s  "
              f"(fitness={best_timing['fitness']:.2f})")

        # ── 4. Update simulated state ──────────
        # In your real system: read new sensor values here
        state["density"]       = np.clip(state["density"] + np.random.uniform(-0.05, 0.05), 0.05, 1.0)
        state["avg_wait_time"] = max(2.0, state["avg_wait_time"] + np.random.uniform(-3, 3))

        levels = ["LOW", "MEDIUM", "HIGH"]
        curr   = levels.index(state["congestion_level"])
        state["congestion_level"] = levels[np.clip(curr + np.random.randint(-1, 2), 0, 2)]

    print("\n✅  Simulation complete!\n")


# ──────────────────────────────────────────────────────────────────
# STEP D — JavaScript / Web Bridge (for Flask / FastAPI)
# ──────────────────────────────────────────────────────────────────

FLASK_EXAMPLE = '''
# ── app.py (Flask) ────────────────────────────────────────────────
from flask import Flask, request, jsonify
from predict_traffic import TrafficPredictor

app = Flask(__name__)
predictor = TrafficPredictor()   # load once at startup

@app.route("/predict", methods=["POST"])
def predict():
    """
    POST /predict
    Body (JSON):
    {
        "time_step": 45,
        "hour": 8,
        "density": 0.72,
        "avg_wait_time": 38.5,
        "congestion_level": "HIGH"
    }
    """
    data = request.get_json()
    result = predictor.predict(data)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, port=5000)

# ── Your JavaScript dashboard (fetch call) ────────────────────────
# const response = await fetch("http://localhost:5000/predict", {
#     method: "POST",
#     headers: { "Content-Type": "application/json" },
#     body: JSON.stringify({
#         time_step: currentStep,
#         hour: new Date().getHours(),
#         density: currentDensity,
#         avg_wait_time: avgWait,
#         congestion_level: congestionLevel
#     })
# });
# const predicted = await response.json();
# // predicted.north_vehicles, predicted.south_vehicles, etc.
# // → pass into your PSO runner
'''

if __name__ == "__main__":
    run_simulation(total_steps=5)
    print("\n── Flask integration template ──")
    print(FLASK_EXAMPLE)
