"""Small pure helper functions and constants (no database or Flask code here)."""
import re

STATUSES = ["Pending", "Under Review", "Team Assigned", "In Progress", "Rescued", "Closed"]
ACTIVE_STATUSES = ("Team Assigned", "In Progress")
DONE_STATUSES = ("Rescued", "Closed")
URGENCY_LEVELS = ["Low", "Medium", "High", "Critical"]
TEAM_STATUSES = ["Available", "On Mission", "Off Duty"]
SHELTER_STATUSES = ["Open", "Full", "Closed"]
ALERT_SEVERITIES = ["Info", "Watch", "Warning", "Severe"]
ALERT_TYPES = ["Flood Warning", "River Level", "Road Closure", "Shelter Update", "Announcement"]
RISK_LEVELS = ["Low", "Medium", "High"]

DANGER_KEYWORDS = ["trapped", "roof", "drown", "injur", "child", "baby", "elderly", "pregnant",
                   "wheelchair", "medical", "no food", "electric", "rising", "unconscious"]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s]{7,15}$")


def compute_priority(urgency, people, special_needs, description):
    """Return (score 0-100, is_urgent). Only a decision-support hint: a human must review."""
    base = {"Low": 10, "Medium": 25, "High": 45, "Critical": 60}.get(urgency, 10)
    score = base + min(people, 20) * 1.5
    if (special_needs or "").strip():
        score += 8
    text = f"{description} {special_needs or ''}".lower()
    hits = sum(1 for word in DANGER_KEYWORDS if word in text)
    score += min(hits, 3) * 5
    score = int(min(score, 100))
    return score, int(urgency in ("High", "Critical") or score >= 60)


def valid_email(value):
    return bool(EMAIL_RE.match(value or ""))


def valid_phone(value):
    return bool(PHONE_RE.match(value or ""))


def password_problem(password):
    """Return a message if the password is weak, otherwise None."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Password must contain at least one letter and one number."
    return None


def to_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
