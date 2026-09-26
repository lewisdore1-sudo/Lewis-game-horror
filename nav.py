"""Navigation graph the Walker uses to move between areas."""
from __future__ import annotations

import heapq
import math

from .layout import area_at

NODES: dict[str, tuple[float, float]] = {
    # Grand hall
    "H_S": (0.0, 2.5), "H_SW": (-5.0, 3.0), "H_SE": (5.0, 3.0),
    "H_W": (-5.0, 7.75), "H_E": (5.0, 7.75), "H_NW": (-3.0, 11.0), "H_NE": (3.0, 11.0),
    "H_N": (0.0, 14.8), "H_ED": (7.2, 7.75),
    # East wing corridor
    "C_W": (9.2, 7.75), "C_A": (13.0, 7.75), "C_B": (21.0, 7.75), "C_C": (29.0, 7.75),
    "C_END": (31.2, 7.75),
    # Rooms (doorway + inside)
    "A_D": (13.0, 9.9), "A_I": (13.0, 11.3),
    "B_D": (21.0, 9.9), "B_I": (21.0, 11.3),
    "C_D": (29.0, 9.9), "C_I": (29.0, 11.3),
    # Garden
    "G_S": (0.0, 17.3), "G_SW": (-3.2, 19.5), "G_SE": (3.2, 19.5),
    "G_W": (-3.3, 24.0), "G_E": (3.3, 24.0), "G_NW": (-3.0, 28.8), "G_NE": (3.0, 28.8),
    "G_N": (0.0, 30.9),
    "G_FW": (-12.0, 24.0), "G_FE": (12.0, 24.0), "G_FNW": (-12.0, 40.0), "G_FNE": (12.0, 40.0),
    "G_BNW": (-6.0, 47.3), "G_BN": (0.0, 47.3), "G_BNE": (6.0, 47.3),
    # Glasshouse
    "GH_I": (0.0, 33.4), "GH_L": (-3.0, 37.0), "GH_R": (3.0, 37.0),
    "GH_NL": (-3.0, 41.5), "GH_NR": (3.0, 41.5), "GH_N": (0.0, 42.6),
}

EDGES: list[tuple[str, str]] = [
    ("H_S", "H_SW"), ("H_S", "H_SE"), ("H_SW", "H_W"), ("H_SE", "H_E"), ("H_W", "H_NW"),
    ("H_E", "H_NE"), ("H_NW", "H_N"), ("H_NE", "H_N"), ("H_NW", "H_NE"), ("H_E", "H_ED"),
    ("H_ED", "C_W"), ("C_W", "C_A"), ("C_A", "C_B"), ("C_B", "C_C"), ("C_C", "C_END"),
    ("C_A", "A_D"), ("A_D", "A_I"), ("C_B", "B_D"), ("B_D", "B_I"), ("C_C", "C_D"), ("C_D", "C_I"),
    ("H_N", "G_S"), ("G_S", "G_SW"), ("G_S", "G_SE"), ("G_SW", "G_W"), ("G_SE", "G_E"),
    ("G_W", "G_NW"), ("G_E", "G_NE"), ("G_NW", "G_N"), ("G_NE", "G_N"),
    ("G_SW", "G_FW"), ("G_SE", "G_FE"), ("G_W", "G_FW"), ("G_E", "G_FE"),
    ("G_FW", "G_FNW"), ("G_FE", "G_FNE"), ("G_FNW", "G_BNW"), ("G_FNE", "G_BNE"),
    ("G_BNW", "G_BN"), ("G_BN", "G_BNE"),
    ("G_N", "GH_I"), ("GH_I", "GH_L"), ("GH_I", "GH_R"), ("GH_L", "GH_NL"), ("GH_R", "GH_NR"),
    ("GH_NL", "GH_N"), ("GH_NR", "GH_N"),
]

GARDEN_AREAS = {"garden", "glasshouse"}


def _build_adjacency():
    adj: dict[str, list[tuple[str, float]]] = {n: [] for n in NODES}
    for a, b in EDGES:
        (ax, ay), (bx, by) = NODES[a], NODES[b]
        d = math.hypot(bx - ax, by - ay)
        adj[a].append((b, d))
        adj[b].append((a, d))
    return adj


ADJ = _build_adjacency()
NODE_AREA = {n: area_at(*p) for n, p in NODES.items()}


def allowed(node: str, garden_allowed: bool) -> bool:
    return garden_allowed or NODE_AREA[node] not in GARDEN_AREAS


def nearest_node(x: float, y: float, garden_allowed: bool, visible_from=None) -> str | None:
    """Closest allowed node, optionally requiring a clear line (visible_from(x,y,nx,ny))."""
    best, best_d = None, 1e9
    for n, (nx, ny) in NODES.items():
        if not allowed(n, garden_allowed):
            continue
        d = math.hypot(nx - x, ny - y)
        if d < best_d and (visible_from is None or visible_from(x, y, nx, ny)):
            best, best_d = n, d
    return best


def distances_to(goal: str, garden_allowed: bool) -> tuple[dict[str, float], dict[str, str]]:
    """Dijkstra from the goal: cost to goal and next hop toward it, for every node."""
    dist = {goal: 0.0}
    nxt: dict[str, str] = {}
    pq = [(0.0, goal)]
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist.get(n, 1e18):
            continue
        for m, w in ADJ[n]:
            if not allowed(m, garden_allowed):
                continue
            nd = d + w
            if nd < dist.get(m, 1e18):
                dist[m] = nd
                nxt[m] = n
                heapq.heappush(pq, (nd, m))
    return dist, nxt


def plan(x: float, y: float, goal: str, garden_allowed: bool, clear) -> list[str]:
    """Best route from an arbitrary point: pick the visible entry node that
    minimises (straight-line distance to it + graph distance to goal)."""
    dist, nxt = distances_to(goal, garden_allowed)
    best, best_c = None, 1e18
    for n, d_goal in dist.items():
        nx, ny = NODES[n]
        c = math.hypot(nx - x, ny - y) + d_goal
        if c < best_c and clear(x, y, nx, ny):
            best, best_c = n, c
    if best is None:
        return []
    path = [best]
    while path[-1] != goal:
        path.append(nxt[path[-1]])
    return path


def shortest_path(start: str, goal: str, garden_allowed: bool) -> list[str]:
    if start == goal:
        return [start]
    dist = {start: 0.0}
    prev: dict[str, str] = {}
    pq = [(0.0, start)]
    while pq:
        d, n = heapq.heappop(pq)
        if n == goal:
            break
        if d > dist.get(n, 1e18):
            continue
        for m, w in ADJ[n]:
            if not allowed(m, garden_allowed):
                continue
            nd = d + w
            if nd < dist.get(m, 1e18):
                dist[m] = nd
                prev[m] = n
                heapq.heappush(pq, (nd, m))
    if goal not in dist:
        return []
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    return path[::-1]
