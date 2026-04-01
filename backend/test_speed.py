import time
WORLD_WIDTH = 100
MAP_MIN_R = 0
MAP_MAX_R = 100

def wrap_coords(q, r) -> tuple:
    q = q % WORLD_WIDTH
    if r < MAP_MIN_R:
        r = abs(r)
        q = (q + (WORLD_WIDTH // 2)) % WORLD_WIDTH
    elif r > MAP_MAX_R:
        r = MAP_MAX_R - (r - MAP_MAX_R)
        q = (q + (WORLD_WIDTH // 2)) % WORLD_WIDTH
    if r <= 1: return 0, 0
    if r >= 99: return 0, 100
    return q, r

def _axial_dist(q1, r1, q2, r2) -> int:
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def get_hex_distance(q1, r1, q2, r2) -> int:
    q1, r1 = wrap_coords(q1, r1)
    q2, r2 = wrap_coords(q2, r2)
    if q1 == q2 and r1 == r2: return 0
    shortcut_dists = []
    if r1 == 0: shortcut_dists.append(max(0, r2 - 1))
    elif r2 == 0: shortcut_dists.append(max(0, r1 - 1))
    if r1 == 100: shortcut_dists.append(max(0, (100 - r2) - 1))
    elif r2 == 100: shortcut_dists.append(max(0, (100 - r1) - 1))
    shortcut_dists.append(max(0, r1 - 1) + max(0, r2 - 1))
    shortcut_dists.append(max(0, 100 - r1 - 1) + max(0, 100 - r2 - 1))
    standard_dists = []
    standard_dists.append(_axial_dist(q1, r1, q2, r2))
    standard_dists.append(_axial_dist(q1, r1, q2 + WORLD_WIDTH, r2))
    standard_dists.append(_axial_dist(q1, r1, q2 - WORLD_WIDTH, r2))
    pq_n = (q2 + (WORLD_WIDTH // 2))
    standard_dists.append(_axial_dist(q1, r1, pq_n, -r2))
    standard_dists.append(_axial_dist(q1, r1, pq_n - WORLD_WIDTH, -r2))
    standard_dists.append(_axial_dist(q1, r1, pq_n + WORLD_WIDTH, -r2))
    pq_s = (q2 + (WORLD_WIDTH // 2))
    standard_dists.append(_axial_dist(q1, r1, pq_s, 200 - r2))
    standard_dists.append(_axial_dist(q1, r1, pq_s - WORLD_WIDTH, 200 - r2))
    standard_dists.append(_axial_dist(q1, r1, pq_s + WORLD_WIDTH, 200 - r2))
    return int(min(shortcut_dists + standard_dists))

start = time.time()
neighbors = [(i, 2) for i in range(WORLD_WIDTH)]
for _ in range(200): # 200 pitfighters
    min(neighbors, key=lambda n: get_hex_distance(n[0], n[1], 75, 2))
print(f"Time: {time.time() - start:.4f}s")
