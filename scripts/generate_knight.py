#!/usr/bin/env python3
"""
Generates an animated SVG of a chess knight + bishop hopping across a
GitHub-style contribution grid, landing only on days with real contributions.

The knight (♞) can reach any square and visits every contribution day.
The bishop (♝) obeys real chess rules and only ever lands on squares of one
color, so it visits whichever contribution days share its starting square's
color.

Usage:
    GH_TOKEN=xxx GH_USER=aswinwrites python3 generate_knight.py --theme light --out dist/knight-light.svg
    GH_TOKEN=xxx GH_USER=aswinwrites python3 generate_knight.py --theme dark  --out dist/knight-dark.svg

If GH_TOKEN / GH_USER are not set, falls back to synthetic sample data so the
script can be run and previewed locally without network access.
"""
import argparse
import json
import os
import random
import urllib.request
from collections import deque

CELL = 15            # px per cell (bump this up for a bigger board/pieces)
GAP = 3               # px gap between cells
RADIUS = 2             # rect corner radius
MARGIN = 22            # svg margin
ROWS = 7               # Sun - Sat
GLYPH_SIZE = CELL + 12  # piece font-size, scales with CELL
SECONDS_PER_MOVE = 0.55  # higher = slower animation
MIN_DUR = 18
MAX_DUR = 70

PALETTES = {
    "light": {
        "bg": "#ffffff",
        "empty": "#ebedf0",
        "scale": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "knight": "#1f2328",
        "knight_highlight": "#ffd60a",
        "bishop": "#8250df",
        "bishop_highlight": "#54aeff",
        "text": "#57606a",
    },
    "dark": {
        "bg": "#0d1117",
        "empty": "#161b22",
        "scale": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "knight": "#f0f6fc",
        "knight_highlight": "#ffd60a",
        "bishop": "#d2a8ff",
        "bishop_highlight": "#79c0ff",
        "text": "#8b949e",
    },
}

KNIGHT_MOVES = [
    (1, 2), (2, 1), (-1, 2), (-2, 1),
    (1, -2), (2, -1), (-1, -2), (-2, -1),
]
BISHOP_MOVES = [(1, 1), (1, -1), (-1, 1), (-1, -1)]

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            weekday
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_calendar(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": GRAPHQL_QUERY, "variables": {"login": user}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    grid = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            grid.append((col, day["weekday"], day["contributionCount"]))
    return grid


def synthetic_calendar(cols=53):
    """Deterministic fake data so the script is runnable/testable offline."""
    random.seed(7)
    grid = []
    for col in range(cols):
        for row in range(ROWS):
            count = 0
            if random.random() < 0.42:
                count = random.choice([1, 1, 2, 3, 5, 8])
            grid.append((col, row, count))
    return grid


def bucket(count, scale):
    if count == 0:
        return scale[0]
    if count <= 2:
        return scale[1]
    if count <= 4:
        return scale[2]
    if count <= 7:
        return scale[3]
    return scale[4]


def bfs_path(start, goal, cols, rows, moves):
    """Shortest legal path from start to goal on a cols x rows board, using
    the given move set (knight-move deltas or bishop-step deltas)."""
    if start == goal:
        return [start]
    seen = {start}
    q = deque([[start]])
    while q:
        path = q.popleft()
        c, r = path[-1]
        for dc, dr in moves:
            nc, nr = c + dc, r + dr
            if 0 <= nc < cols and 0 <= nr < rows and (nc, nr) not in seen:
                new_path = path + [(nc, nr)]
                if (nc, nr) == goal:
                    return new_path
                seen.add((nc, nr))
                q.append(new_path)
    return [start, goal]  # fallback: shouldn't happen on a well-connected board


def build_path(filled_cells, cols, rows, moves, max_stops=90):
    """Chronological filled cells -> full hop path (with intermediate hops)."""
    if not filled_cells:
        return [(0, 0)]
    if len(filled_cells) > max_stops:
        step = len(filled_cells) / max_stops
        sampled = [filled_cells[int(i * step)] for i in range(max_stops)]
        filled_cells = sampled

    path = [filled_cells[0]]
    for target in filled_cells[1:]:
        hop_path = bfs_path(path[-1], target, cols, rows, moves)
        path.extend(hop_path[1:])
    return path


def piece_animation(path, cell_xy, dur, glyph, color):
    n = len(path)
    positions = [cell_xy(c, r) for c, r in path]
    xs = ";".join(f"{x + CELL/2:.1f}" for x, y in positions)
    ys = ";".join(f"{y + CELL/2:.1f}" for x, y in positions)
    kt = ";".join(f"{i/max(1, n-1):.4f}" for i in range(n))
    return (
        f'<text font-size="{GLYPH_SIZE}" text-anchor="middle" dominant-baseline="central" '
        f'fill="{color}" stroke="#ffffff" stroke-width="0.6" paint-order="stroke">{glyph}'
        f'<animate attributeName="x" values="{xs}" keyTimes="{kt}" dur="{dur}s" '
        f'repeatCount="indefinite" calcMode="discrete"/>'
        f'<animate attributeName="y" values="{ys}" keyTimes="{kt}" dur="{dur}s" '
        f'repeatCount="indefinite" calcMode="discrete"/>'
        f'</text>'
    )


def landing_glow(rect_id, x, y, base, highlight, path, target_cell, overall_dur, n):
    landing_times = [i for i, p in enumerate(path) if p == target_cell]
    if not landing_times:
        return ""
    t = landing_times[0] / max(1, n - 1)
    eps = min(0.01, 1 / max(1, n))
    kt = sorted(set([0.0, max(0.0, t - eps), t, min(1.0, t + eps * 2), 1.0]))
    vals = ";".join(highlight if abs(k - t) < 1e-9 else base for k in kt)
    kt_str = ";".join(f"{k:.4f}" for k in kt)
    return (
        f'<animate attributeName="fill" values="{vals}" keyTimes="{kt_str}" '
        f'dur="{overall_dur}s" repeatCount="indefinite"/>'
    )


def render_svg(grid, palette, out_path, user_label):
    cols = max(c for c, r, cnt in grid) + 1
    rows = ROWS
    filled_chrono = [(c, r) for c, r, cnt in grid if cnt > 0]

    knight_path = build_path(filled_chrono, cols, rows, KNIGHT_MOVES)

    if filled_chrono:
        bishop_parity = (filled_chrono[0][0] + filled_chrono[0][1]) % 2
    else:
        bishop_parity = 0
    bishop_cells = [p for p in filled_chrono if (p[0] + p[1]) % 2 == bishop_parity]
    bishop_path = build_path(bishop_cells, cols, rows, BISHOP_MOVES)

    n_k, n_b = len(knight_path), len(bishop_path)
    overall_dur = max(
        MIN_DUR, min(MAX_DUR, round(max(n_k, n_b) * SECONDS_PER_MOVE, 1))
    )

    width = MARGIN * 2 + cols * (CELL + GAP)
    height = MARGIN * 2 + rows * (CELL + GAP) + 24

    def cell_xy(c, r):
        return MARGIN + c * (CELL + GAP), MARGIN + r * (CELL + GAP)

    svg = []
    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
    )
    svg.append(f'<rect width="100%" height="100%" fill="{palette["bg"]}" rx="6"/>')

    for c, r, cnt in grid:
        x, y = cell_xy(c, r)
        base = bucket(cnt, palette["scale"])
        rect_id = f"c{c}_{r}"
        anim = ""
        if cnt > 0:
            if (c, r) in bishop_cells:
                anim = landing_glow(rect_id, x, y, base, palette["bishop_highlight"],
                                     bishop_path, (c, r), overall_dur, n_b)
            if not anim:
                anim = landing_glow(rect_id, x, y, base, palette["knight_highlight"],
                                     knight_path, (c, r), overall_dur, n_k)
        svg.append(
            f'<rect id="{rect_id}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
            f'rx="{RADIUS}" ry="{RADIUS}" fill="{base}">{anim}</rect>'
        )

    svg.append(piece_animation(knight_path, cell_xy, overall_dur, "♞", palette["knight"]))
    svg.append(piece_animation(bishop_path, cell_xy, overall_dur, "♝", palette["bishop"]))

    caption_y = height - 8
    svg.append(
        f'<text x="{MARGIN}" y="{caption_y}" font-size="11" fill="{palette["text"]}">'
        f'♞ {user_label} — knight visits every contribution day, '
        f'♝ bishop stays on its color</text>'
    )
    svg.append("</svg>")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write("\n".join(svg))
    print(f"wrote {out_path} | cells={len(grid)} filled={len(filled_chrono)} "
          f"knight_path={n_k} bishop_path={n_b} dur={overall_dur}s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=["light", "dark"], default="light")
    ap.add_argument("--out", default="dist/knight-light.svg")
    args = ap.parse_args()

    user = os.environ.get("GH_USER")
    token = os.environ.get("GH_TOKEN")

    if user and token:
        grid = fetch_calendar(user, token)
        label = user
    else:
        print("GH_USER / GH_TOKEN not set - using synthetic sample data for a local preview.")
        grid = synthetic_calendar()
        label = "sample data"

    render_svg(grid, PALETTES[args.theme], args.out, label)


if __name__ == "__main__":
    main()
