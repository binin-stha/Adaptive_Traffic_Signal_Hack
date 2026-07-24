"""Transparent decision engine — full step-by-step reasoning chain."""

from typing import Any, Dict, List, Optional

from config.constants import (
    DIRECTIONS, WEIGHTS, BASE_TIME, MIN_GREEN, MAX_GREEN, MAX_WAIT,
)


class DecisionFlow:
    """Produces a fully auditable, step-by-step signal decision every tick.

    Mirrors how a traffic officer reasons:
    see the traffic -> weigh the load -> check who has waited too long
    -> protect crossing pedestrians -> pick a direction -> justify it.
    """

    def __init__(self):
        self.current_green: Optional[str] = None
        self.green_remaining: float = 0.0
        self.wait_times: Dict[str, float] = {d: 0.0 for d in DIRECTIONS}
        self.decision_log: List[Dict[str, Any]] = []
        self.total_elapsed: float = 0.0

    def evaluate(
        self,
        counts_by_dir: Dict[str, Dict[str, Any]],
        dt: float,
        force: bool = False,
    ) -> Dict[str, Any]:
        """Run the full reasoning chain. Returns steps + decision + state."""

        self.total_elapsed += dt

        # Red directions accumulate wait; green direction's wait resets.
        for d in DIRECTIONS:
            if d == self.current_green:
                self.wait_times[d] = 0.0
            elif d in counts_by_dir:
                self.wait_times[d] += dt

        steps: List[Dict[str, Any]] = []

        # ── STEP 1 · PERCEPTION ───────────────────────────────────────────
        perception = {
            d: {
                "vehicles": c["vehicle"],
                "waiting_vehicles": c["waiting_vehicles"],
                "pedestrians": c["pedestrian"],
                "waiting_peds": c["waiting_pedestrians"],
                "crossing_peds": c["crossing_pedestrians"],
            }
            for d, c in counts_by_dir.items()
        }
        steps.append({"name": "PERCEPTION", "detail": perception})

        # ── STEP 2 · WEIGHTED LOAD ────────────────────────────────────────
        loads = {
            d: c["vehicle"] * WEIGHTS["vehicle"]
            + c["pedestrian"] * WEIGHTS["pedestrian"]
            for d, c in counts_by_dir.items()
        }
        steps.append({
            "name": "WEIGHTED LOAD",
            "formula": "vehicles×1.5 + pedestrians×1.2",
            "detail": {d: round(loads.get(d, 0.0), 1) for d in DIRECTIONS},
        })

        # ── STEP 3 · STARVATION CHECK ─────────────────────────────────────
        starved = [
            d for d in DIRECTIONS
            if d in counts_by_dir and self.wait_times.get(d, 0.0) > MAX_WAIT
        ]
        steps.append({
            "name": "STARVATION CHECK",
            "threshold": MAX_WAIT,
            "detail": {d: round(self.wait_times.get(d, 0.0), 1) for d in DIRECTIONS},
            "alert": starved,
        })

        # ── STEP 4 · PEDESTRIAN SAFETY ────────────────────────────────────
        crossing_now = [
            d for d, c in counts_by_dir.items() if c["crossing_pedestrians"] > 0
        ]
        steps.append({
            "name": "PEDESTRIAN SAFETY",
            "detail": {
                d: counts_by_dir[d]["crossing_pedestrians"] for d in counts_by_dir
            },
            "alert": crossing_now,
        })

        # ── STEP 5 · DECISION ─────────────────────────────────────────────
        self.green_remaining -= dt

        need_decision = (
            force
            or self.current_green is None
            or self.green_remaining <= 0
            or (starved and self.current_green not in starved)
        )

        if need_decision:
            if starved:
                nxt = max(starved, key=lambda d: self.wait_times.get(d, 0.0))
                reason = (
                    f"STARVATION GUARD — {nxt.upper()} waited "
                    f"{self.wait_times[nxt]:.0f}s (> {MAX_WAIT}s)"
                )
                green_time = float(MAX_GREEN)
            else:
                candidates = [d for d in counts_by_dir if loads.get(d, 0.0) > 0]
                if not candidates:
                    nxt = self.current_green or DIRECTIONS[0]
                    reason = "No demand detected — holding current phase"
                    green_time = float(MIN_GREEN)
                else:
                    nxt = max(candidates, key=lambda d: loads.get(d, 0.0))
                    total_load = sum(loads.values()) or 1.0
                    share = BASE_TIME + (loads[nxt] / total_load) * (MAX_GREEN - BASE_TIME)
                    green_time = float(max(MIN_GREEN, min(MAX_GREEN, round(share))))
                    reason = f"Highest weighted load ({loads[nxt]:.1f})"

            # SAFETY HOLD: never cut off a direction while its pedestrians
            # are mid-crossing — extend until they clear.
            if (
                self.current_green
                and self.current_green in crossing_now
                and nxt != self.current_green
            ):
                nxt = self.current_green
                reason = (
                    f"HOLDING — pedestrians still crossing at "
                    f"{self.current_green.upper()}"
                )
                green_time = max(self.green_remaining, 5.0)

            prev = self.current_green
            self.current_green = nxt
            self.green_remaining = green_time
            self.wait_times[nxt] = 0.0

            self.decision_log.append({
                "time": round(self.total_elapsed, 1),
                "from": prev,
                "to": nxt,
                "reason": reason,
                "green_time": green_time,
            })
            self.decision_log = self.decision_log[-40:]

        steps.append({
            "name": "DECISION",
            "detail": {
                "green": self.current_green,
                "remaining": round(max(self.green_remaining, 0.0), 1),
                "reason": self.decision_log[-1]["reason"] if self.decision_log else "—",
            },
        })

        # ── STEP 6 · SIGNAL STATE ─────────────────────────────────────────
        signal_state = {
            d: ("green" if d == self.current_green else "red") for d in DIRECTIONS
        }
        steps.append({"name": "SIGNAL STATE", "detail": signal_state})

        return {
            "steps": steps,
            "signal_state": signal_state,
            "current_green": self.current_green,
            "green_remaining": max(self.green_remaining, 0.0),
            "wait_times": dict(self.wait_times),
            "loads": loads,
            "decision_log": list(self.decision_log),
        }