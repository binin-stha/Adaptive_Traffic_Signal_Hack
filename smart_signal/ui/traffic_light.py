"""Reusable traffic-signal renderer (3-lamp housing with glow + yellow phase)."""

SIGNAL_COLORS = {
    "red":    ("#FF453A", "#2E1414"),
    "yellow": ("#FFD60A", "#2E2A12"),
    "green":  ("#30D158", "#12301C"),
}


def effective_lamp(state: str, remaining: float = None) -> str:
    """Green flips to yellow in the last 3 seconds before a phase change."""
    if state == "green" and remaining is not None and remaining < 3.0:
        return "yellow"
    return state if state in SIGNAL_COLORS else "red"


def traffic_light_html(state: str, scale: float = 1.0, horizontal: bool = False) -> str:
    """Return HTML for a signal housing with the active lamp lit and glowing."""
    state = state if state in SIGNAL_COLORS else "red"
    lamp = int(15 * scale)
    gap = int(5 * scale)
    pad = int(6 * scale)
    radius = int(9 * scale)

    lamps_html = ""
    for name in ("red", "yellow", "green"):
        on = name == state
        color = SIGNAL_COLORS[name][0] if on else SIGNAL_COLORS[name][1]
        if on:
            glow = (f"box-shadow:0 0 {int(11*scale)}px {int(2*scale)}px "
                    f"{SIGNAL_COLORS[name][0]}99, inset 0 0 {int(4*scale)}px #ffffff55;")
        else:
            glow = f"box-shadow:inset 0 0 {int(4*scale)}px #000000aa;"
        lamps_html += (
            f'<div style="width:{lamp}px;height:{lamp}px;border-radius:50%;'
            f'background:radial-gradient(circle at 35% 30%, {color}, {color} 55%, #00000066);'
            f'{glow}transition:all .35s ease;"></div>'
        )

    direction = "row" if horizontal else "column"
    return (
        f'<div style="display:flex;flex-direction:{direction};gap:{gap}px;'
        f'padding:{pad}px;background:linear-gradient(180deg,#1B212B,#0C1015);'
        f'border:1px solid #2C3542;border-radius:{radius}px;'
        f'box-shadow:0 4px 14px #00000077, inset 0 1px 0 #ffffff10;">'
        f'{lamps_html}</div>'
    )