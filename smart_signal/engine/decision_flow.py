"""Rule-based signal decision engine.

The junction is two competing AXES:
    NS = north + south   (opposing directions share one signal)
    EW = east  + west    (opposing directions share one signal)
The two axes cross inside the junction, so they are mutually exclusive —
exactly one axis is ever green.

Priority rules, evaluated in this exact order:
  1. Starvation guard       — a side waiting > MAX_WAIT is forced green.
  2. Congestion fairness    — both sides >= HIGH_THRESHOLD: rotate on MAX_HOLD_TIME.
  3. Low-traffic fast-track — a side <= LOW_THRESHOLD with fewer vehicles clears first.
  4. Default                — the side with fewer vehicles goes first.
"""

from typing import Any, Dict, List

LOW_THRESHOLD   = 5
HIGH_THRESHOLD  = 15
MAX_HOLD_TIME   = 40
MAX_WAIT        = 90

AXES = {"NS": ["north", "south"], "EW": ["east", "west"]}
AXIS_LABEL = {"NS": "NORTH–SOUTH", "EW": "EAST–WEST"}
# Crossing axes — giving one green necessarily locks the other.
AXIS_CONFLICTS = {"NS": "EW", "EW": "NS"}


def decide_green(counts: dict, wait_time: dict, current_green: str, green_held_for: int) -> str:
    """
    counts[d]       = vehicle count on direction d
    wait_time[d]    = seconds since d last had green
    current_green   = direction currently green
    green_held_for  = seconds current_green has been green
    returns: direction that should be green next
    """
    # 1. Starvation — a side waiting too long is forced green no matter what
    for d, w in wait_time.items():
        if w > MAX_WAIT:
            return d

    a, b = counts.keys()  # two directions being compared

    # 2. Both sides congested -> ignore counts, use time-based fairness only
    if counts[a] >= HIGH_THRESHOLD and counts[b] >= HIGH_THRESHOLD:
        if green_held_for >= MAX_HOLD_TIME:
            return b if current_green == a else a   # force switch
        return current_green                          # still within its turn, keep it

    # 3. One side clearly light -> clear it first regardless of the other side's count
    if counts[a] <= LOW_THRESHOLD and counts[a] < counts[b]:
        return a
    if counts[b] <= LOW_THRESHOLD and counts[b] < counts[a]:
        return b

    # 4. Default — lower count goes first (assumption: clears the junction faster)
    return a if counts[a] <= counts[b] else b


def _which_rule(counts, wait_time, current_green, green_held_for):
    """Mirror decide_green to report WHICH rule fired (for the reasoning chain)."""
    for d, w in wait_time.items():
        if w > MAX_WAIT:
            return "STARVATION GUARD", f"{AXIS_LABEL[d]} waited {w:.0f}s (> {MAX_WAIT}s) — forced green"
    a, b = counts.keys()
    if counts[a] >= HIGH_THRESHOLD and counts[b] >= HIGH_THRESHOLD:
        if green_held_for >= MAX_HOLD_TIME:
            other = b if current_green == a else a
            return "CONGESTION ROTATE", f"both axes ≥ {HIGH_THRESHOLD}, held {green_held_for:.0f}s — rotate to {AXIS_LABEL[other]}"
        return "CONGESTION HOLD", f"both axes ≥ {HIGH_THRESHOLD}, held {green_held_for:.0f}s < {MAX_HOLD_TIME}s — keep {AXIS_LABEL[current_green]}"
    if counts[a] <= LOW_THRESHOLD and counts[a] < counts[b]:
        return "LOW-TRAFFIC FAST-TRACK", f"{AXIS_LABEL[a]} ≤ {LOW_THRESHOLD} & fewer — clear it first"
    if counts[b] <= LOW_THRESHOLD and counts[b] < counts[a]:
        return "LOW-TRAFFIC FAST-TRACK", f"{AXIS_LABEL[b]} ≤ {LOW_THRESHOLD} & fewer — clear it first"
    winner = a if counts[a] <= counts[b] else b
    loser = b if winner == a else a
    return "DEFAULT — CLEAR FASTEST", f"{AXIS_LABEL[winner]} has fewer ({counts[winner]} vs {counts[loser]}) — goes first"


class DecisionFlow:
    """Drives the junction by running decide_green on the NS vs EW axis counts."""

    def __init__(self):
        self.current_axis = None
        self.green_held_for = 0.0
        self.axis_wait = {ax: 0.0 for ax in AXES}
        self.decision_log: List[Dict[str, Any]] = []
        self.total_elapsed = 0.0
        self.last_rule = ""
        self.last_reason = ""

    def _switch(self, axis, rule, reason):
        prev = self.current_axis
        self.current_axis = axis
        self.green_held_for = 0.0
        self.axis_wait[axis] = 0.0
        self.last_rule, self.last_reason = rule, reason
        self.decision_log.append({
            "time": round(self.total_elapsed, 1),
            "from": prev, "to": axis, "rule": rule, "reason": reason,
        })
        self.decision_log = self.decision_log[-40:]

    # ── signal mapping + safety invariant ─────────────────────────────────
    def _signal_state(self) -> Dict[str, str]:
        """Opposing directions share one signal; the crossing axis is locked red."""
        state = {
            d: ("green" if ax == self.current_axis else "red")
            for ax, dirs in AXES.items() for d in dirs
        }
        return self._enforce_conflict_lock(state)

    def _enforce_conflict_lock(self, state: Dict[str, str]) -> Dict[str, str]:
        """Hard invariant: the two crossing axes are NEVER green at the same time.

        The axis model already guarantees this, but we clamp defensively so a
        conflicting state can never reach the lamps no matter how it arose.
        """
        green_axes = {
            ax for ax, dirs in AXES.items()
            if any(state.get(d) == "green" for d in dirs)
        }
        if len(green_axes) > 1:
            for ax, dirs in AXES.items():
                if ax != self.current_axis:
                    for d in dirs:
                        state[d] = "red"
        return state

    def evaluate(self, counts_by_dir, dt, force=False):
        self.total_elapsed += dt
        self.green_held_for += dt

        # aggregate vehicle counts per axis (opposing lanes summed together)
        axis_counts = {
            ax: sum(counts_by_dir.get(d, {}).get("vehicle", 0) for d in dirs)
            for ax, dirs in AXES.items()
        }

        # red axis accumulates wait; the green axis resets
        for ax in AXES:
            if ax == self.current_axis:
                self.axis_wait[ax] = 0.0
            else:
                self.axis_wait[ax] += dt

        # pedestrian crossings per axis (safety overlay)
        crossing_axes = set()
        for d, c in counts_by_dir.items():
            if c.get("crossing_pedestrians", 0) > 0:
                for ax, dirs in AXES.items():
                    if d in dirs:
                        crossing_axes.add(ax)

        # ── run the rules ─────────────────────────────────────────────────
        else:
            nxt = decide_green(axis_counts, self.axis_wait, self.current_axis, self.green_held_for)
            rule, reason = _which_rule(axis_counts, self.axis_wait, self.current_axis, self.green_held_for)

            # HARD CAP — no axis may hold green beyond MAX_HOLD_TIME; force rotation
            if self.green_held_for >= MAX_HOLD_TIME:
                other = AXIS_CONFLICTS[self.current_axis]
                nxt = other
                rule, reason = "MAX HOLD REACHED", (
                    f"{AXIS_LABEL[self.current_axis]} held {self.green_held_for:.0f}s "
                    f"(≥ {MAX_HOLD_TIME}s) — rotate to {AXIS_LABEL[other]}"
                )

            # SAFETY — never cut off an axis while its pedestrians are mid-crossing
            if self.current_axis in crossing_axes and nxt != self.current_axis:
                nxt = self.current_axis
                rule, reason = "PEDESTRIAN HOLD", f"pedestrians crossing on {AXIS_LABEL[self.current_axis]} — hold green"

            if nxt != self.current_axis:
                self._switch(nxt, rule, reason)
            else:
                self.last_rule, self.last_reason = rule, reason
        signal_state = self._signal_state()

        a, b = list(axis_counts.keys())
        both_congested = axis_counts[a] >= HIGH_THRESHOLD and axis_counts[b] >= HIGH_THRESHOLD
        starved = [ax for ax, w in self.axis_wait.items() if w > MAX_WAIT]
        locked = AXIS_CONFLICTS.get(self.current_axis)

        steps = [
            {"name": "VEHICLE COUNTS", "detail": dict(axis_counts)},
            {"name": "CONGESTION", "alert": both_congested,
             "detail": "BOTH AXES CONGESTED" if both_congested else "normal flow"},
            {"name": "STARVATION", "alert": starved,
             "detail": {ax: round(self.axis_wait[ax], 1) for ax in AXES}},
            {"name": "PEDESTRIANS", "alert": bool(crossing_axes),
             "detail": sorted(crossing_axes) if crossing_axes else "none crossing"},
            {"name": "CONFLICT LOCK", "alert": False,
             "detail": f"{self.current_axis} green · {locked} locked red"},
            {"name": "DECISION", "detail": {"axis": self.current_axis,
                                            "rule": self.last_rule, "reason": self.last_reason}},
            {"name": "SIGNAL STATE", "detail": signal_state},
        ]

        return {
            "steps": steps,
            "signal_state": signal_state,
            "current_axis": self.current_axis,
            "axis_lock": {"green_axis": self.current_axis, "locked_axis": locked},
            "green_held_for": self.green_held_for,
            "hold_remaining": max(0.0, MAX_HOLD_TIME - self.green_held_for),
            "axis_counts": axis_counts,
            "axis_wait": dict(self.axis_wait),
            "last_rule": self.last_rule,
            "last_reason": self.last_reason,
            "decision_log": list(self.decision_log),
        }