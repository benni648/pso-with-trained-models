"""
=====================================================================
 Intersection Coordination — Phase 4 (Step 4.3)
=====================================================================
 Optimizes signal timings across MULTIPLE intersections with a single
 global Particle Swarm Optimization run:

   - Global fitness = summed weighted-wait across all intersections,
     which discourages cascading gridlock (a blocked downstream
     intersection raises the cost of upstream green time).
   - Green wave: for a list of arterial intersections, recommends
     staggered phase offsets so a platoon progressing along the
     artery meets consecutive greens.
   - Emergency preemption: an emergency approach is given extended
     green (held at the maximum bound) while cross-streets are scaled
     back.

 Pure numpy — no extra dependencies.
=====================================================================
"""

import numpy as np

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

DIRECTIONS = ["north", "south", "east", "west"]
DIRECTION_KEYS = {
    "north": "north_green",
    "south": "south_green",
    "east": "east_green",
    "west": "west_green",
}


class IntersectionCoordinator:
    """
    Global PSO coordinator for multiple intersections.

    Usage:
        coordinator = IntersectionCoordinator()
        result = coordinator.optimize({
            "INT_001": {"north_vehicles": 12, "south_vehicles": 8, ...},
            "INT_002": {"north_vehicles": 9, ...},
        }, arterial=["INT_001", "INT_002"],
           emergency={"intersection_id": "INT_001",
                      "directions": ["north"], "duration": 30})
    """

    def __init__(self, n_particles: int = 40, n_iterations: int = 60,
                 bounds=(5, 60), w: float = 0.7, c1: float = 1.5,
                 c2: float = 1.5, seed: int = 42):
        self.n_particles = n_particles
        self.n_iterations = n_iterations
        self.bounds = bounds
        self.w, self.c1, self.c2 = w, c1, c2
        self._rng = np.random.default_rng(seed)

    # ── PUBLIC API ─────────────────────────────────────────────

    def optimize(self, demands: dict, arterial: list = None,
                 emergency: dict = None) -> dict:
        """
        Run global PSO over all intersections.

        Parameters
        ----------
        demands : dict
            {"INT_001": {"north_vehicles"/"north": 12, ...}, ...}
        arterial : list[str], optional
            Ordered intersection ids along an artery (for green wave).
        emergency : dict, optional
            {"intersection_id": str, "directions": [str], "duration": float}

        Returns
        -------
        dict
            Per-intersection timings, global fitness, green wave and
            emergency metadata.
        """
        if not demands:
            raise ValueError("demands must define at least one intersection")

        intersection_ids = list(demands.keys())
        demand_vectors = {
            iid: self._demand_vector(demands[iid]) for iid in intersection_ids
        }
        n_dims = 4 * len(intersection_ids)

        # ── Global PSO ────────────────────────────────────────
        low, high = self.bounds
        pos = self._rng.uniform(low, high, (self.n_particles, n_dims))
        vel = np.zeros_like(pos)

        p_best_pos = pos.copy()
        p_best_fit = np.array([
            self._global_fitness(p, demand_vectors, intersection_ids)
            for p in pos
        ])

        g_best_idx = int(np.argmin(p_best_fit))
        g_best_pos = p_best_pos[g_best_idx].copy()
        g_best_fit = float(p_best_fit[g_best_idx])

        for _ in range(self.n_iterations):
            r1 = self._rng.random((self.n_particles, n_dims))
            r2 = self._rng.random((self.n_particles, n_dims))

            vel = (
                self.w * vel
                + self.c1 * r1 * (p_best_pos - pos)
                + self.c2 * r2 * (g_best_pos - pos)
            )
            pos = np.clip(pos + vel, low, high)

            fits = np.array([
                self._global_fitness(p, demand_vectors, intersection_ids)
                for p in pos
            ])
            improved = fits < p_best_fit
            p_best_pos[improved] = pos[improved]
            p_best_fit[improved] = fits[improved]

            best_idx = int(np.argmin(p_best_fit))
            if p_best_fit[best_idx] < g_best_fit:
                g_best_fit = float(p_best_fit[best_idx])
                g_best_pos = p_best_pos[best_idx].copy()

        # ── Build per-intersection results ────────────────────
        intersections = {}
        for i, iid in enumerate(intersection_ids):
            timings = g_best_pos[i * 4:(i + 1) * 4]
            intersections[iid] = self._timing_dict(
                timings,
                demand_vectors[iid],
            )

        result = {
            "intersections": intersections,
            "global_fitness": round(g_best_fit, 4),
            "cycle_time": round(float(np.sum(g_best_pos)), 1),
            "method": "global_pso",
            "n_intersections": len(intersection_ids),
        }

        # ── Green wave offsets ────────────────────────────────
        if arterial and len(arterial) > 1:
            offsets, wave = self.green_wave_offsets(arterial, float(np.sum(g_best_pos)))
            result["green_wave"] = {
                "enabled": True,
                "arterial": arterial,
                "offsets": offsets,
                "description": wave,
            }

        # ── Emergency preemption ──────────────────────────────
        if emergency and emergency.get("intersection_id") in intersections:
            result["emergency"] = self._apply_emergency(
                intersections,
                emergency,
                low,
                high,
            )

        return result

    def green_wave_offsets(self, arterial: list, cycle_time: float):
        """
        Recommend staggered offsets for an ordered arterial list.

        Each downstream intersection starts its through-green offset by
        cycle/N, producing a progression wave along the artery.

        Returns
        -------
        tuple
            (offsets_dict, description_str)
        """
        n = len(arterial)
        step = cycle_time / n if n else 0
        offsets = {}
        for i, iid in enumerate(arterial):
            offsets[iid] = round((i * step) % cycle_time, 1)
        description = (
            f"Staggered offsets (cycle {cycle_time:.0f}s / {n} junctions) "
            f"for green-wave progression along {', '.join(arterial)}"
        )
        return offsets, description

    # ── INTERNALS ─────────────────────────────────────────────

    @staticmethod
    def _global_fitness(signal_timings: np.ndarray,
                        demand_vectors: dict,
                        intersection_ids: list) -> float:
        """Sum of per-intersection weighted-wait estimates (lower is better)."""
        total = 0.0
        for i, iid in enumerate(intersection_ids):
            timings = signal_timings[i * 4:(i + 1) * 4]
            total += IntersectionCoordinator._intersection_wait(
                timings, demand_vectors[iid]
            )
        return total

    @staticmethod
    def _intersection_wait(timings: np.ndarray, demand: np.ndarray) -> float:
        """Weighted wait heuristic for one intersection (mirrors PSO)."""
        cycle = float(np.sum(timings))
        if cycle <= 0:
            return float("inf")
        wait = 0.0
        for d, green in enumerate(timings):
            if green > 0:
                wait += demand[d] * (cycle - green) / green
            elif demand[d] > 0:
                wait += demand[d] * 999.0
        return wait

    @staticmethod
    def _timing_dict(timings: np.ndarray, demand: np.ndarray) -> dict:
        entry = {
            DIRECTION_KEYS[d]: round(float(timings[i]), 1)
            for i, d in enumerate(DIRECTIONS)
        }
        entry["fitness"] = round(
            IntersectionCoordinator._intersection_wait(timings, demand), 4
        )
        return entry

    @staticmethod
    def _demand_vector(demand: dict) -> np.ndarray:
        """Normalise a per-intersection demand dict to a 4-vector."""
        vector = np.zeros(4)
        for i, direction in enumerate(DIRECTIONS):
            raw = demand.get(f"{direction}_vehicles",
                             demand.get(direction, 0))
            try:
                vector[i] = max(0.0, float(raw))
            except (TypeError, ValueError):
                vector[i] = 0.0
        return vector

    @staticmethod
    def _apply_emergency(intersections: dict, emergency: dict,
                         low: float, high: float) -> dict:
        """
        Force extended green for an emergency approach and scale back
        the remaining approaches.
        """
        iid = emergency["intersection_id"]
        directions = emergency.get("directions", []) or []
        duration = float(emergency.get("duration", 30))

        target = intersections[iid]
        indices = [DIRECTIONS.index(d.lower()) for d in directions
                   if d.lower() in DIRECTIONS]

        timings = np.array([target[DIRECTION_KEYS[d]] for d in DIRECTIONS])
        for idx in indices:
            timings[idx] = high  # emergency approach held at max

        # Cross streets share the remaining cycle proportionally
        others = [i for i in range(4) if i not in indices]
        if others:
            current_other_sum = float(np.sum(timings[others])) or 1.0
            other_budget = max(4 * low, duration + float(np.sum(timings[indices])))
            scale = other_budget / current_other_sum
            for i in others:
                timings[i] = np.clip(timings[i] * scale, low, high)

        for i, d in enumerate(DIRECTIONS):
            target[DIRECTION_KEYS[d]] = round(float(timings[i]), 1)

        return {
            "active": True,
            "intersection_id": iid,
            "directions": [DIRECTIONS[i] for i in indices],
            "duration_s": duration,
            "held_at_max_s": float(high),
        }