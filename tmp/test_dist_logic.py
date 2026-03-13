
import sys
import os

# Add the project root to sys.path so we can import backend modules
sys.path.append(os.path.abspath('backend'))

from game_helpers import get_hex_distance

def test_distances():
    # User is at (0,0) - North Pole
    p1 = (0, 0)
    
    stations = [
        ((0, 0), "STATION_HUB"),
        ((0, 0), "MARKET"),
        ((25, 2), "SMELTER"),
        ((50, 2), "CRAFTER"),
        ((75, 2), "REPAIR"),
        ((0, 3), "REFINERY")
    ]
    
    print(f"Testing distances from {p1}:")
    for pos, name in stations:
        d = get_hex_distance(p1[0], p1[1], pos[0], pos[1])
        print(f"{name} at {pos}: Dist {d}")

if __name__ == "__main__":
    test_distances()
