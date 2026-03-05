import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from game_helpers import wrap_coords, get_hex_distance

def test_wrapping():
    print("Testing wrap_coords...")
    # Longitude wrap
    assert wrap_coords(100, 50) == (0, 50)
    assert wrap_coords(-1, 50) == (99, 50)
    
    # North Pole wrap
    # Cross North Pole at q=10, r=-1 -> should be q=60, r=1
    assert wrap_coords(10, -1) == (60, 1)
    
    # South Pole wrap
    # Cross South Pole at q=10, r=101 -> should be q=60, r=99
    assert wrap_coords(10, 101) == (60, 99)
    print("wrap_coords PASS")

def test_distance():
    print("Testing get_hex_distance...")
    # Normal distance
    assert get_hex_distance(0, 0, 5, 5) == 10
    
    # Longitude wrap distance (shortest should be around the back)
    # q=0 to q=95 is dist 5
    assert get_hex_distance(0, 50, 95, 50) == 5
    
    # Polar wrap distance
    # q=10, r=5 to q=60, r=5. 
    # Direct distance r=5 to r=5 is abs(10-60)=50.
    # Over the pole distance: r=5 to r=0 (dist 5) then r=0 to r=5 (dist 5). Total 10?
    # wrap_coords(10, -5) = (60, 5). So distance (10,5) to (60,5) should be 10.
    assert get_hex_distance(10, 5, 60, 5) == 10
    print("get_hex_distance PASS")

if __name__ == "__main__":
    try:
        test_wrapping()
        test_distance()
        print("\nALL GEOMETRY TESTS PASSED")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
    except Exception as e:
        print(f"\nERROR: {e}")
