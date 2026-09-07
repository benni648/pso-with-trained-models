"""
=====================================================================
 Route Optimization — Phase 4 (Step 4.4)
=====================================================================
 Suggests alternative routes to drivers around congestion.
 Given a road network graph (intersections + travel times) and an
 origin/destination pair, returns the top-K routes ranked by
 estimated travel time, flagging which routes avoid congested
 intersections.

 The network can be supplied by the caller or seeded from the live
 congestion forecaster (per-intersection congestion levels at the
 requested horizon).

 Uses the stdlib heapq for Dijkstra/Yen-style k-shortest-paths
 (simplified superset elimination) — no extra runtime dependency.
=====================================================================
"""

import heapq
import itertools
import threading
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import LoggerManager

logger = LoggerManager.get_logger(__name__)

# Free-flow speed in km/h used to derive travel times from distances
DEFAULT_SPEED_KMH = 40.0

# Congestion multipliers applied to free-flow travel time
LEVEL_MULTIPLIER = {
    "LOW": 1.0,
    "MEDIUM": 1.5,
    "HIGH": 2.2,
}


class RouteAdvisor:
    """
    Alternative-route advisor over a weighted intersection graph.

    Usage:
        advisor = RouteAdvisor(network)
        routes = advisor.suggest_routes("A", "D", k=3)
    """

    def __init__(self, network: Optional[Dict[str, Any]] = None,
                 speed_kmh: float = DEFAULT_SPEED_KMH):
        """
        Parameters
        ----------
        network : dict, optional
            {"intersections": {
                "INT_001": {"name": "...", "congestion": "LOW"},
                ...
             },
             "roads": [
                {"from": "INT_001", "to": "INT_002",
                 "distance_km": 1.2, "name": "Main St"},
                ...
             ]}
            Congestion levels may also be numbers (0=LOW .. 2=HIGH).
        speed_kmh : float
            Free-flow speed for distance → time conversion.
        """
        self.speed_kmh = max(1.0, float(speed_kmh))
        self._lock = threading.Lock()
        self.intersections: Dict[str, Dict[str, Any]] = {}
        self.adjacency: Dict[str, List[Tuple[str, float, str]]] = {}
        if network:
            self.load_network(network)

    # ── NETWORK MANAGEMENT ────────────────────────────────────

    def load_network(self, network: Dict[str, Any]) -> None:
        """
        Load (or replace) the road network.

        Raises
        ------
        ValueError
            If the network shape is invalid.
        """
        if not isinstance(network, dict):
            raise ValueError("network must be a dict")
        intersections = network.get("intersections") or {}
        roads = network.get("roads") or []
        if not intersections or not roads:
            raise ValueError(
                "network requires 'intersections' and 'roads'"
            )

        with self._lock:
            self.intersections = {
                str(node): dict(info) if isinstance(info, dict) else {}
                for node, info in intersections.items()
            }
            self.adjacency = {node: [] for node in self.intersections}

            for road in roads:
                src = str(road.get("from", ""))
                dst = str(road.get("to", ""))
                distance = self._as_distance(road.get("distance_km"))
                if src not in self.intersections or dst not in self.intersections:
                    raise ValueError(
                        f"road references unknown intersection: {src}→{dst}"
                    )
                if distance is None or distance <= 0:
                    raise ValueError(
                        f"road {src}→{dst} needs a positive distance_km"
                    )
                name = str(road.get("name", f"{src}→{dst}"))
                base_minutes = distance / self.speed_kmh * 60.0
                self.adjacency[src].append((dst, base_minutes, name))
                # Roads are two-way by default unless oneway is set
                if not road.get("oneway", False):
                    self.adjacency[dst].append((src, base_minutes, name))

            # Nodes that appear only as road endpoints
            for node in list(self.adjacency):
                self.intersections.setdefault(node, {})

        logger.info(
            f"Route network loaded: {len(self.intersections)} intersections, "
            f"{len(roads)} roads"
        )

    def update_congestion(self, levels: Dict[str, Any]) -> None:
        """
        Update congestion levels per intersection.

        Parameters
        ----------
        levels : dict
            {intersection_id: "LOW"|"MEDIUM"|"HIGH" or 0|1|2}
        """
        with self._lock:
            for node, level in levels.items():
                if node in self.intersections:
                    self.intersections[node]["congestion"] = self._normalise_level(level)

    def _apply_forecaster(self, forecaster, minutes: int = 10) -> None:
        """
        Seed congestion levels from a TrafficForecaster's congestion
        prediction (best-effort; intersections not in the forecast
        keep their previous level).
        """
        try:
            horizons = forecaster.predict_congestion(minutes)["horizons"]
            key = str(minutes) if str(minutes) in horizons else next(iter(horizons))
            per_dir = horizons[key].get("per_direction", {})
            predicted = horizons[key].get("predicted_total", 0.0)
            level = horizons[key].get("level", "LOW")
            # Single-intersection deployment: apply the level globally
            # weighted by each direction share where names match.
            levels = {}
            for node in self.intersections:
                levels[node] = level
            if per_dir:
                # Allow caller-named intersections matching directions
                for direction, value in per_dir.items():
                    if direction in self.intersections:
                        total = sum(per_dir.values()) or 1.0
                        share = value / total
                        # Slightly decongest below-average directions
                        if share < 0.2 and level == "HIGH":
                            levels[direction] = "MEDIUM"
            self.update_congestion(levels)
        except Exception as e:
            logger.debug(f"Forecaster seeding skipped: {str(e)}")

    # ── ROUTE SUGGESTION ──────────────────────────────────────

    def suggest_routes(self, origin: str, destination: str,
                       k: int = 3, avoid: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Return the top-k routes between origin and destination.

        Parameters
        ----------
        origin, destination : str
            Intersection IDs.
        k : int
            Number of alternatives (1-5).
        avoid : list[str], optional
            Intersections to avoid (e.g. incident sites).

        Returns
        -------
        dict
            {"origin", "destination", "routes": [...], "recommended"}
            Each route: {"rank", "eta_minutes", "distance_km",
                         "congestion_level", "roads", "intersections"}
        """
        k = max(1, min(5, int(k)))
        origin, destination = str(origin), str(destination)

        with self._lock:
            if origin not in self.intersections:
                raise ValueError(f"unknown origin intersection: {origin}")
            if destination not in self.intersections:
                raise ValueError(f"unknown destination intersection: {destination}")
            if origin == destination:
                raise ValueError("origin and destination must differ")

            avoid_set = {str(a) for a in (avoid or [])}
            candidates = self._k_shortest_paths(
                origin, destination, k, avoid_set
            )

        routes = []
        for i, (path, minutes, distance, roads) in enumerate(candidates):
            level = self._route_level(path)
            routes.append({
                "rank": i + 1,
                "eta_minutes": round(minutes, 1),
                "distance_km": round(distance, 2),
                "congestion_level": level,
                "roads": roads,
                "intersections": path,
            })

        recommended = routes[0]["rank"] if routes else None
        if routes and avoid_set:
            # Prefer routes that avoid the excluded nodes when their
            # ETA penalty is small (< 25%)
            clean = [r for r in routes
                     if not (avoid_set & set(r["intersections"]))]
            if clean:
                best_clean = clean[0]
                if best_clean["eta_minutes"] <= routes[0]["eta_minutes"] * 1.25:
                    recommended = best_clean["rank"]

        return {
            "origin": origin,
            "destination": destination,
            "routes": routes,
            "recommended": recommended,
            "network": {
                "intersections": len(self.intersections),
            },
        }

    def fastest_route(self, origin: str, destination: str) -> Optional[Dict[str, Any]]:
        """Convenience: the single fastest route (or None)."""
        result = self.suggest_routes(origin, destination, k=1)
        return result["routes"][0] if result["routes"] else None

    def get_status(self) -> Dict[str, Any]:
        """Advisor metadata for status endpoints."""
        with self._lock:
            congested = [
                node for node, info in self.intersections.items()
                if self._normalise_level(info.get("congestion", "LOW")) == "HIGH"
            ]
            return {
                "intersections": len(self.intersections),
                "roads": sum(len(v) for v in self.adjacency.values()) // 2,
                "congested_intersections": congested,
                "speed_kmh": self.speed_kmh,
            }

    # ── GRAPH ALGORITHMS ──────────────────────────────────────

    def _k_shortest_paths(self, origin: str, destination: str,
                          k: int, avoid: set) -> List[Tuple[list, float, float, list]]:
        """
        Yen-style k shortest paths using Dijkstra expansions.
        Returns [(path, minutes, distance_km, road_names), ...].
        """
        blocked = avoid - {origin, destination}

        def dijkstra(banned_edges: set, banned_nodes: set):
            dist = {origin: 0.0}
            prev: Dict[str, Tuple[str, float, str]] = {}
            pq = [(0.0, origin)]
            visited = set()
            while pq:
                d, node = heapq.heappop(pq)
                if node in visited:
                    continue
                visited.add(node)
                if node == destination:
                    break
                for nxt, base_minutes, name in self.adjacency.get(node, []):
                    if nxt in banned_nodes or (node, nxt, name) in banned_edges:
                        continue
                    weight = base_minutes * self._node_multiplier(nxt)
                    nd = d + weight
                    if nd < dist.get(nxt, float("inf")):
                        dist[nxt] = nd
                        prev[nxt] = (node, base_minutes, name)
                        heapq.heappush(pq, (nd, nxt))
            if destination not in dist:
                return None
            # Reconstruct path and road names
            path, roads = [destination], []
            node = destination
            while node != origin:
                src, base, name = prev[node]
                roads.append(name)
                path.append(src)
                node = src
            path.reverse()
            roads.reverse()
            return path, dist[destination], roads

        first = dijkstra(set(), blocked)
        if first is None:
            return []
        best_path, best_cost, best_roads = first
        results = [(best_path, best_cost, best_roads)]
        seen = {tuple(best_path)}

        # Yen expansions
        candidate_pool = []
        for i in range(1, len(best_path)):
            spur_node = best_path[i - 1]
            root_path = best_path[:i]
            banned_edges = set()
            for path_p, _, _ in results:
                if path_p[:i] == root_path and len(path_p) > i:
                    nxt = path_p[i]
                    for edge in self.adjacency.get(spur_node, []):
                        if edge[0] == nxt:
                            banned_edges.add((spur_node, nxt, edge[2]))
            spur_result = dijkstra(banned_edges, blocked)
            if spur_result is not None:
                p, c, r = spur_result
                if tuple(p) not in seen:
                    seen.add(tuple(p))
                    heapq.heappush(candidate_pool, (c, p, r))

        while candidate_pool and len(results) < k:
            cost, path, roads = heapq.heappop(candidate_pool)
            results.append((path, cost, roads))

        # Convert to output tuples with distance
        out = []
        for path, cost, roads in results:
            distance = self._path_distance(path)
            out.append((path, cost, distance, roads))
        out.sort(key=lambda item: item[1])
        return out

    # ── HELPERS ───────────────────────────────────────────────

    def _node_multiplier(self, node: str) -> float:
        info = self.intersections.get(node, {})
        level = self._normalise_level(info.get("congestion", "LOW"))
        return LEVEL_MULTIPLIER[level]

    def _route_level(self, path: list) -> str:
        """Worst congestion level along the path."""
        worst = "LOW"
        rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        for node in path:
            info = self.intersections.get(node, {})
            level = self._normalise_level(info.get("congestion", "LOW"))
            if rank[level] > rank[worst]:
                worst = level
        return worst

    def _path_distance(self, path: list) -> float:
        """Sum road distances (km) along a path via base minutes."""
        total = 0.0
        for i in range(len(path) - 1):
            src, dst = path[i], path[i + 1]
            for nxt, base_minutes, _ in self.adjacency.get(src, []):
                if nxt == dst:
                    total += base_minutes / 60.0 * self.speed_kmh
                    break
        return total

    @staticmethod
    def _normalise_level(value: Any) -> str:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if value >= 2:
                return "HIGH"
            if value >= 1:
                return "MEDIUM"
            return "LOW"
        text = str(value or "").upper()
        if text in ("HIGH", "2"):
            return "HIGH"
        if text in ("MEDIUM", "MED", "1"):
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _as_distance(raw: Any) -> Optional[float]:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
