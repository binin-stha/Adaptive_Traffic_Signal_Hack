"""Rule-based signal decision engine — per-direction signals with realistic phases.

Each of the four approaches (NORTH, SOUTH, EAST, WEST) owns its own signal head.
Exactly one direction is released at a time; every change sequences through
green → yellow → red before the next direction goes green.

Rules evaluated while green, in priority order:
  1. Starvation guard       — a direction waiting > MAX_WAIT is forced green.
  2. Max-hold rotate        — a direction green ≥ MAX_HOLD_TIME yields to the longest-waiting other.
  3. Low-traffic fast-track — a direction ≤ LOW_THRESHOLD with fewer vehicles clears first.
  4. Default demand         — switch only to a direction with strictly fewer vehicles.
A minimum green time (MIN_GREEN_TIME) stops counts from flipping the light too fast,
and pedestrian safety overrides any change (never cut off a crossing mid-walk).
"""

from typing import Any, Dict, List

from config.constants import DIRECTIONS, DIR_META

LOW_THRESHOLD   = 5
HIGH_THRESHOLD  = 15
MAX_HOLD_TIME   = 40
MAX_WAIT        = 90
MIN_GREEN_TIME  = 15   # a direction holds at least this long before counts may switch it
YELLOW_TIME     = 3    # seconds of amber between green and red


def _label(d: str) -> str:
    return DIR_META.get(d, {}).get("label", d.upper())


def decide_green(counts: dict, wait_time: dict, current_green: str, green_held_for: float) -> str:
    """
    counts[d]       = vehicle count on direction d (all four approaches)
    wait_time[d]    = seconds since d last had green
    current_green   = direction currently green
    green_held_for  = seconds current_green has been green
    returns: direction that should be green next
    """
    # 1. Starvation — a direction waiting too long is forced green no matter what
    starved = [d for d, w in wait_time.items() if w > MAX_WAIT]
    if starved:
        return max(starved, key=lambda d: wait_time[d])

    others = [d for d in counts if d != current_green]
    if not others:
        return current_green

    # 2. Max-hold fairness — held too long, yield to the longest-waiting other
    if green_held_for >= MAX_HOLD_TIME:
        return max(others, key=lambda d: wait_time.get(d, 0))

    # 3. Low-traffic fast-track — a quiet direction clears first
    low = [d for d in others if counts[d] <= LOW_THRESHOLD]
    if low:
        quietest = min(low, key=lambda d: counts[d])
        if counts[quietest] < counts.get(current_green, 0):
            return quietest

    # 4. Default — switch only to a direction with strictly fewer vehicles
    fewest = min(others, key=lambda d: counts[d])
    if counts[fewest] < counts.get(current_green, 0):
        return fewest
    return current_green


def _which_rule(counts, wait_time, current_green, green_held_for, nxt):
    """Report WHICH rule fired (for the reasoning chain)."""
    if nxt == current_green:
        return "HOLD", f"{_label(current_green)} retains green (heaviest or tied demand)"
    starved = [d for d, w in wait_time.items() if w > MAX_WAIT]
    if nxt in starved:
        return "STARVATION GUARD", f"{_label(nxt)} waited {wait_time[nxt]:.0f}s (> {MAX_WAIT}s) — forced green"
    if green_held_for >= MAX_HOLD_TIME:
        return "MAX HOLD ROTATE", f"{_label(current_green)} held {green_held_for:.0f}s — rotate to {_label(nxt)}"
    if counts.get(nxt, 0) <= LOW_THRESHOLD:
        return "LOW-TRAFFIC FAST-TRACK", f"{_label(nxt)} ≤ {LOW_THRESHOLD} vehicles — clear it first"
    return "DEMAND — CLEAR FASTEST", (
        f"{_label(nxt)} has fewer ({counts.get(nxt, 0)} vs {counts.get(current_green, 0)}) — goes first"
    )


class DecisionFlow:
    """Drives the junction: picks a direction, then sequences green → yellow → red."""

    def __init__(self):
        self.current_dir = None
        self.phase = "green"          # "green" | "yellow"
        self.pending_dir = None       # direction waiting to go green during yellow
        self.yellow_timer = 0.0
        self.green_held_for = 0.0
        self.dir_wait = {d: 0.0 for d in DIRECTIONS}
        self.decision_log: List[Dict[str, Any]] = []
        self.total_elapsed = 0.0
        self.last_rule = ""
        self.last_reason = ""

    # ── signal mapping + safety invariant ─────────────────────────────────
    def _signal_state(self) -> Dict[str, str]:
        state = {}
        for d in DIRECTIONS:
            if d == self.current_dir:
                state[d] = "yellow" if self.phase == "yellow" else "green"
            else:
                state[d] = "red"
        return self._enforce_conflict_lock(state)

    def _enforce_conflict_lock(self, state: Dict[str, str]) -> Dict[str, str]:
        """At most one direction may show a releasing colour (green or yellow)."""
        releasing = [d for d in DIRECTIONS if state.get(d) in ("green", "yellow")]
        if len(releasing) > 1:
            for d in releasing:
                if d != self.current_dir:
                    state[d] = "red"
        return state

    # ── phase transitions ─────────────────────────────────────────────────
    def _begin_yellow(self, nxt, rule, reason):
        self.phase = "yellow"
        self.pending_dir = nxt
        self.yellow_timer = 0.0
        self.last_rule, self.last_reason = rule, reason
        self.decision_log.append({
            "time": round(self.total_elapsed, 1),
            "from": self.current_dir, "to": nxt, "rule": rule, "reason": reason,
        })
        self.decision_log = self.decision_log[-40:]

    def _complete_transition(self):
        self.current_dir = self.pending_dir
        self.phase = "green"
        self.pending_dir = None
        self.yellow_timer = 0.0
        self.green_held_for = 0.0
        self.dir_wait[self.current_dir] = 0.0

    # ── the rules (only run while green) ──────────────────────────────────
    def _decide(self, dir_counts, crossing_dirs):
        if self.current_dir is None:
            nxt = decide_green(dir_counts, self.dir_wait, DIRECTIONS[0], 0)
            self.current_dir = nxt
            self.green_held_for = 0.0
            self.dir_wait[nxt] = 0.0
            self.last_rule, self.last_reason = "INITIAL PHASE", f"opening with {_label(nxt)}"
            self.decision_log.append({
                "time": round(self.total_elapsed, 1), "from": None, "to": nxt,
                "rule": "INITIAL PHASE", "reason": f"opening with {_label(nxt)}",
            })
            return

        nxt = decide_green(dir_counts, self.dir_wait, self.current_dir, self.green_held_for)
        rule, reason = _which_rule(dir_counts, self.dir_wait, self.current_dir, self.green_held_for, nxt)
        forced = rule in ("STARVATION GUARD", "MAX HOLD ROTATE")

        # minimum green — stop counts from flipping the light too fast
        if not forced and self.green_held_for < MIN_GREEN_TIME and nxt != self.current_dir:
            nxt = self.current_dir
            rule, reason = "MINIMUM GREEN", (
                f"{_label(self.current_dir)} within minimum green "
                f"({self.green_held_for:.0f}s < {MIN_GREEN_TIME}s) — hold"
            )

        # pedestrian safety — never cut off a crossing mid-walk
        if self.current_dir in crossing_dirs and nxt != self.current_dir:
            nxt = self.current_dir
            rule, reason = "PEDESTRIAN HOLD", f"pedestrians crossing on {_label(self.current_dir)} — hold green"

        if nxt != self.current_dir:
            self._begin_yellow(nxt, rule, reason)   # start amber, switch later
        else:
            self.last_rule, self.last_reason = rule, reason

    # ── main tick ─────────────────────────────────────────────────────────
    def evaluate(self, counts_by_dir, dt, force=False):
        self.total_elapsed += dt

        dir_counts = {d: counts_by_dir.get(d, {}).get("vehicle", 0) for d in DIRECTIONS}
        crossing_dirs = set()
        for d, c in counts_by_dir.items():
            if c.get("crossing_pedestrians", 0) > 0:
                crossing_dirs.add(d)

        # the released direction is held at zero wait; the others accumulate
        for d in DIRECTIONS:
            if d == self.current_dir:
                self.dir_wait[d] = 0.0
            else:
                self.dir_wait[d] += dt

        if self.phase == "yellow":
            self.yellow_timer += dt
            if self.yellow_timer >= YELLOW_TIME:
                self._complete_transition()
        else:
            self.green_held_for += dt
            self._decide(dir_counts, crossing_dirs)

        signal_state = self._signal_state()
        starved = [d for d, w in self.dir_wait.items() if w > MAX_WAIT]
        congested = [d for d, c in dir_counts.items() if c >= HIGH_THRESHOLD]

        steps = [
            {"name": "VEHICLE COUNTS", "detail": dict(dir_counts)},
            {"name": "CONGESTION", "alert": bool(congested),
             "detail": ", ".join(_label(d) for d in congested) if congested else "normal flow"},
            {"name": "STARVATION", "alert": starved,
             "detail": {d: round(self.dir_wait[d], 1) for d in DIRECTIONS}},
            {"name": "PEDESTRIANS", "alert": bool(crossing_dirs),
             "detail": ", ".join(_label(d) for d in crossing_dirs) if crossing_dirs else "none crossing"},
            {"name": "PHASE", "alert": self.phase == "yellow",
             "detail": (f"{_label(self.current_dir)} YELLOW → {_label(self.pending_dir)}"
                        if self.phase == "yellow" else f"{_label(self.current_dir)} GREEN")},
            {"name": "DECISION", "detail": {"dir": self.current_dir,
                                            "rule": self.last_rule, "reason": self.last_reason}},
            {"name": "SIGNAL STATE", "detail": signal_state},
        ]

        return {
            "steps": steps,
            "signal_state": signal_state,
            "current_dir": self.current_dir,
            "phase": self.phase,
            "pending_dir": self.pending_dir,
            "green_held_for": self.green_held_for,
            "yellow_timer": self.yellow_timer,
            "hold_remaining": max(0.0, MAX_HOLD_TIME - self.green_held_for),
            "dir_counts": dir_counts,
            "dir_wait": dict(self.dir_wait),
            "last_rule": self.last_rule,
            "last_reason": self.last_reason,
            "decision_log": list(self.decision_log),
        }