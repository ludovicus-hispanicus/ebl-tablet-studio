"""
Configuration file for ruler detector tests.
Contains expected measurements and test parameters.
"""

def calculate_range(expected_value, deviation_percent=15):
    """Calculate min and max values based on percentage deviation."""
    deviation = expected_value * (deviation_percent / 100)
    return {
        "expected": expected_value,
        "min": int(expected_value - deviation),
        "max": int(expected_value + deviation)
    }

EXPECTED_MEASUREMENTS = {
    "IM.124625.H_02.JPG": calculate_range(726),
    "IM.124625.K_02.JPG": calculate_range(716),
    "IM.124625.O_01.JPG": calculate_range(707),
    "IM.132576.P_01.JPG": calculate_range(780),
    "IM.132672.C_01.JPG": calculate_range(409),
    "IM.132521.B_01.JPG": calculate_range(478),
    "IM.132576.G_01.JPG": calculate_range(521),
}