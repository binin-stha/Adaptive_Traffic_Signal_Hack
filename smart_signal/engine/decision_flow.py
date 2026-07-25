"""Rule-based signal decision engine with realistic phase transitions.

The junction is two competing AXES (NS = north+south, EW = east+west) that
cross inside the junction — exactly one axis is ever released.

Phase lifecycle (like a real signal head):
    GREEN → (decision to change) → YELLOW → RED, while the next axis goes GREEN.

Rules evaluated while GREEN, in priority order:
  1. Starvation guard      — a side waiting > MAX_WAIT is forced green.
  2. Max-hold cap          — a side green ≥ MAX_HOLD_TIME is forced to yield.
  3. Minimum green         — a side holds ≥ MIN_GREEN_TIME before counts may switch it.
  4. Congestion fairness   — both sides ≥ HIGH_THRESHOLD rotate on the cap.
  5. Low-traffic fast-track — a side ≤ LOW_THRESHOLD with fewer vehicles clears first.
  6. Default               — the side with fewer vehicles goes first.
Pedestrian safety overrides any change: never cut off an axis mid-crossing.
"""


from typing import Any, Dict, List

LOW_THRESHOLD   = 5
HIGH_THRESHOLD  = 15
MAX_HOLD_TIME   = 40
MAX_WAIT        = 90
MIN_GREEN_TIME  = 10   # a phase holds at least this long before counts may switch it
YELLOW_TIME     = 3    # seconds of amber between green and red

AXES = {"NS": ["north", "south"], "EW": ["east", "west"]}
AXIS_LABEL = {"NS": "NORTH–SOUTH", "EW": "EAST–WEST"}
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
    """Drives the junction: picks an axis, then sequences green → yellow → red."""

    def __init__(self):
        self.current_axis = None
        self.phase = "green"          # "green" | "yellow"
        self.pending_axis = None      # axis waiting to go green during yellow
        self.yellow_timer = 0.0
        self.green_held_for = 0.0
        self.axis_wait = {ax: 0.0 for ax in AXES}
        self.decision_log: List[Dict[str, Any]] = []
        self.total_elapsed = 0.0
        self.last_rule = ""
        self.last_reason = ""

    # ── signal mapping + safety invariant ─────────────────────────────────
    def _signal_state(self) -> Dict[str, str]:
        state = {}
        for ax, dirs in AXES.items():
            if ax == self.current_axis:
                lamp = "yellow" if self.phase == "yellow" else "green"
            else:
                lamp = "red"
            for d in dirs:
                state[d] = lamp
        return self._enforce_conflict_lock(state)

    def _enforce_conflict_lock(self, state: Dict[str, str]) -> Dict[str, str]:
        """At most one axis may show a releasing colour (green or yellow)."""
        releasing = {
            ax for ax, dirs in AXES.items()
            if any(state.get(d) in ("green", "yellow") for d in dirs)
        }
        if len(releasing) > 1:
            for ax, dirs in AXES.items():
                if ax != self.current_axis:
                    for d in dirs:
                        state[d] = "red"
        return state

    # ── phase transitions ─────────────────────────────────────────────────
    def _begin_yellow(self, nxt, rule, reason):
        self.phase = "yellow"
        self.pending_axis = nxt
        self.yellow_timer = 0.0
        self.last_rule, self.last_reason = rule, reason
        self.decision_log.append({
            "time": round(self.total_elapsed, 1),
            "from": self.current_axis, "to": nxt, "rule": rule, "reason": reason,
        })
        self.decision_log = self.decision_log[-40:]

    def _complete_transition(self):
        self.current_axis = self.pending_axis
        self.phase = "green"
        self.pending_axis = None
        self.yellow_timer = 0.0
        self.green_held_for = 0.0
        self.axis_wait[self.current_axis] = 0.0

    # ── the rules (only run while green) ──────────────────────────────────
    def _decide(self, axis_counts, crossing_axes):
        if self.current_axis is None:
            nxt = decide_green(axis_counts, self.axis_wait, "NS", 0)
            self.current_axis = nxt
            self.green_held_for = 0.0
            self.axis_wait[nxt] = 0.0
            self.last_rule, self.last_reason = "INITIAL PHASE", f"opening with {AXIS_LABEL[nxt]}"
            self.decision_log.append({
                "time": round(self.total_elapsed, 1), "from": None, "to": nxt,
                "rule": "INITIAL PHASE", "reason": f"opening with {AXIS_LABEL[nxt]}",
            })
            return

        nxt = decide_green(axis_counts, self.axis_wait, self.current_axis, self.green_held_for)
        rule, reason = _which_rule(axis_counts, self.axis_wait, self.current_axis, self.green_held_for)
        forced = False

        # 1. starvation overrides everything
        if any(w > MAX_WAIT for w in self.axis_wait.values()) and nxt != self.current_axis:
            forced = True

        # 2. max-hold cap — force a yield when open too long
        if self.green_held_for >= MAX_HOLD_TIME:
            nxt = AXIS_CONFLICTS[self.current_axis]
            rule, reason = "MAX HOLD REACHED", (
                f"{AXIS_LABEL[self.current_axis]} held {self.green_held_for:.0f}s "
                f"(≥ {MAX_HOLD_TIME}s) — rotate to {AXIS_LABEL[nxt]}"
            )
            forced = True

        # 3. minimum green — don't let counts flip the light before it has had its turn
        if not forced and self.green_held_for < MIN_GREEN_TIME and nxt != self.current_axis:
            nxt = self.current_axis
            rule, reason = "MINIMUM GREEN", (
                f"{AXIS_LABEL[self.current_axis]} within minimum green "
                f"({self.green_held_for:.0f}s < {MIN_GREEN_TIME}s) — hold"
            )

        # 4. pedestrian safety — never cut off a crossing mid-walk
        if self.current_axis in crossing_axes and nxt != self.current_axis:
            nxt = self.current_axis
            rule, reason = "PEDESTRIAN HOLD", f"pedestrians crossing on {AXIS_LABEL[self.current_axis]} — hold green"

        if nxt != self.current_axis:
            self._begin_yellow(nxt, rule, reason)   # start amber, switch later
        else:
            self.last_rule, self.last_reason = rule, reason

    # ── main tick ─────────────────────────────────────────────────────────
    def evaluate(self, counts_by_dir, dt, force=False):
        self.total_elapsed += dt

        axis_counts = {
            ax: sum(counts_by_dir.get(d, {}).get("vehicle", 0) for d in dirs)
            for ax, dirs in AXES.items()
        }
        crossing_axes = set()
        for d, c in counts_by_dir.items():
            if c.get("crossing_pedestrians", 0) > 0:
                for ax, dirs in AXES.items():
                    if d in dirs:
                        crossing_axes.add(ax)

        # the releasing axis is held at zero wait; the other accumulates
        for ax in AXES:
            if ax == self.current_axis:
                self.axis_wait[ax] = 0.0
            else:
                self.axis_wait[ax] += dt

        if self.phase == "yellow":
            # see the amber through — no new decisions mid-transition
            self.yellow_timer += dt
            if self.yellow_timer >= YELLOW_TIME:
                self._complete_transition()
        else:
            self.green_held_for += dt
            self._decide(axis_counts, crossing_axes)

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
            {"name": "PHASE", "alert": self.phase == "yellow",
             "detail": (f"{self.current_axis} YELLOW → {self.pending_axis}"
                        if self.phase == "yellow" else f"{self.current_axis} GREEN")},
            {"name": "CONFLICT LOCK", "alert": False,
             "detail": f"{self.current_axis} releasing · {locked} locked red"},
            {"name": "DECISION", "detail": {"axis": self.current_axis,
                                            "rule": self.last_rule, "reason": self.last_reason}},
            {"name": "SIGNAL STATE", "detail": signal_state},
        ]

        return {
            "steps": steps,
            "signal_state": signal_state,
            "current_axis": self.current_axis,
            "phase": self.phase,
            "pending_axis": self.pending_axis,
            "axis_lock": {"green_axis": self.current_axis, "locked_axis": locked},
            "green_held_for": self.green_held_for,
            "yellow_timer": self.yellow_timer,
            "hold_remaining": max(0.0, MAX_HOLD_TIME - self.green_held_for),
            "axis_counts": axis_counts,
            "axis_wait": dict(self.axis_wait),
            "last_rule": self.last_rule,
            "last_reason": self.last_reason,
            "decision_log": list(self.decision_log),
        }