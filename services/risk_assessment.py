"""
Transparent, rule-based flood risk scoring.

This is NOT a weather forecast. It turns three simple inputs into a 0-100 score
so that a human can quickly see which locations deserve closer monitoring.

Score = rainfall points (max 40) + river-level points (max 40) + reports points (max 20)
  < 35  -> Low
  < 65  -> Medium
  >= 65 -> High
Extra rule: a river at or above its danger level is always High.

Rainfall bands follow the IMD (India Meteorological Department) 24-hour categories.
"""

LOW_LIMIT = 35
HIGH_LIMIT = 65


def _rainfall_points(rain_mm):
    if rain_mm >= 204.5:
        return 40, "Extremely heavy rainfall (204.5 mm or more in 24 h)"
    if rain_mm >= 115.6:
        return 32, "Very heavy rainfall (115.6 - 204.4 mm in 24 h)"
    if rain_mm >= 64.5:
        return 22, "Heavy rainfall (64.5 - 115.5 mm in 24 h)"
    if rain_mm >= 15.6:
        return 10, "Moderate rainfall (15.6 - 64.4 mm in 24 h)"
    return 0, "Light rainfall (below 15.6 mm in 24 h)"


def _river_points(level_m, danger_m):
    if danger_m <= 0:
        return 0, "No danger level supplied, river factor ignored", 0.0
    ratio = level_m / danger_m
    pct = round(ratio * 100)
    if ratio >= 1.0:
        return 40, f"River is at {pct}% of danger level (at or above danger mark)", ratio
    if ratio >= 0.95:
        return 32, f"River is at {pct}% of danger level (almost at danger mark)", ratio
    if ratio >= 0.8:
        return 25, f"River is at {pct}% of danger level (rising towards danger mark)", ratio
    if ratio >= 0.6:
        return 12, f"River is at {pct}% of danger level (elevated)", ratio
    return 0, f"River is at {pct}% of danger level (normal range)", ratio


def _report_points(count):
    if count >= 6:
        return 20, f"{count} flood reports received (many)"
    if count >= 3:
        return 14, f"{count} flood reports received (several)"
    if count >= 1:
        return 8, f"{count} flood report(s) received (few)"
    return 0, "No flood reports received"


RECOMMENDATIONS = {
    "Low": [
        "Continue routine monitoring of rainfall and river gauges.",
        "Keep shelter and rescue-team contact lists up to date.",
        "Share basic preparedness tips with residents.",
    ],
    "Medium": [
        "Increase monitoring frequency (for example every 1-3 hours).",
        "Put rescue teams and relief material on standby.",
        "Check that nearby shelters are open and have free capacity.",
        "Review unverified flood reports from this area.",
    ],
    "High": [
        "Escalate to the responsible authority for human decision-making.",
        "Pre-position rescue teams and confirm shelter readiness.",
        "Prepare evacuation advisories for low-lying areas.",
        "Verify road access before directing anyone along an evacuation route.",
    ],
}


def assess_flood_risk(rainfall_24h_mm, river_level_m, danger_level_m, reported_floods=0):
    """Return a dict with level, score, factors and recommendations."""
    rainfall_24h_mm = float(rainfall_24h_mm)
    river_level_m = float(river_level_m)
    danger_level_m = float(danger_level_m)
    reported_floods = int(reported_floods)
    if min(rainfall_24h_mm, river_level_m, danger_level_m, reported_floods) < 0:
        raise ValueError("Values cannot be negative.")

    rain_pts, rain_text = _rainfall_points(rainfall_24h_mm)
    river_pts, river_text, ratio = _river_points(river_level_m, danger_level_m)
    rep_pts, rep_text = _report_points(reported_floods)

    score = rain_pts + river_pts + rep_pts
    if score >= HIGH_LIMIT:
        level = "High"
    elif score >= LOW_LIMIT:
        level = "Medium"
    else:
        level = "Low"

    override = None
    if danger_level_m > 0 and ratio >= 1.0 and level != "High":
        level = "High"
        override = "Rule applied: river at or above danger level is always High risk."

    factors = [
        {"name": "Rainfall (24 h)", "detail": rain_text, "points": rain_pts, "max": 40},
        {"name": "River level", "detail": river_text, "points": river_pts, "max": 40},
        {"name": "Flood reports", "detail": rep_text, "points": rep_pts, "max": 20},
    ]
    return {
        "level": level,
        "score": score,
        "factors": factors,
        "override": override,
        "recommendations": RECOMMENDATIONS[level],
        "disclaimer": ("Rule-based estimate from the values entered. It is not a real-time "
                       "forecast or an official warning. Always follow official authorities."),
    }
