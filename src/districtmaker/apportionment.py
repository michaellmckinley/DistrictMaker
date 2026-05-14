"""2020 Census apportionment — House seats per state through 2030.

Source: U.S. Census Bureau, 2020 Apportionment Results
(https://www.census.gov/library/visualizations/2021/dec/2020-apportionment-map.html).
Sums to 435. Hardcoded because it does not change until the 2030 Census.
"""
from __future__ import annotations

DISTRICTS_2020: dict[str, int] = {
    "AL": 7, "AK": 1, "AZ": 9, "AR": 4, "CA": 52, "CO": 8, "CT": 5,
    "DE": 1, "FL": 28, "GA": 14, "HI": 2, "ID": 2, "IL": 17, "IN": 9,
    "IA": 4, "KS": 4, "KY": 6, "LA": 6, "ME": 2, "MD": 8, "MA": 9,
    "MI": 13, "MN": 8, "MS": 4, "MO": 8, "MT": 2, "NE": 3, "NV": 4,
    "NH": 2, "NJ": 12, "NM": 3, "NY": 26, "NC": 14, "ND": 1, "OH": 15,
    "OK": 5, "OR": 6, "PA": 17, "RI": 2, "SC": 7, "SD": 1, "TN": 9,
    "TX": 38, "UT": 4, "VT": 1, "VA": 11, "WA": 10, "WV": 2, "WI": 8,
    "WY": 1,
}


def districts_for_state(state_code: str) -> int:
    """House seats for a state under 2020 apportionment."""
    code = state_code.upper()
    if code not in DISTRICTS_2020:
        raise ValueError(f"Unknown state code: {state_code!r}")
    return DISTRICTS_2020[code]
