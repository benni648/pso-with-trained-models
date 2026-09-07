"""
=====================================================================
 Intelligence Package — Phase 4 (Advanced Intelligence)
=====================================================================
 Beyond basic counting and single-intersection optimization:

   anomaly.py     → AnomalyDetector (surge / accident / road closure /
                    sensor failure + Isolation Forest pattern checks)
   forecaster.py  → TrafficForecaster (Holt trend forecast +
                    congestion horizons at 5/10/15 minutes)
   coordinator.py → IntersectionCoordinator (global PSO across
                    intersections + green-wave offsets +
                    emergency preemption)
   controller.py  → SignalControllerClient (push timings to real
                    controllers with fixed-timing fallback)
   tmc.py         → TrafficManagementCenterClient (city TMC REST
                    data exchange + webhook alert notifications)
   deep_model.py  → optional torch LSTM companion model (standalone;
                    not imported at startup)

 All modules are pure numpy / sklearn / stdlib — no heavy runtime
 dependencies are required by the running application.
=====================================================================
"""

from intelligence.anomaly import AnomalyDetector
from intelligence.forecaster import TrafficForecaster
from intelligence.coordinator import IntersectionCoordinator
from intelligence.controller import SignalControllerClient
from intelligence.tmc import TrafficManagementCenterClient

__all__ = [
    "AnomalyDetector",
    "TrafficForecaster",
    "IntersectionCoordinator",
    "SignalControllerClient",
    "TrafficManagementCenterClient",
]