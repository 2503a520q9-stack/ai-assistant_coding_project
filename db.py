"""Database helpers: connection, schema and sample data (SQLite)."""
import os
import sqlite3
from datetime import datetime, timedelta

from flask import g
from werkzeug.security import generate_password_hash

from services.risk_assessment import assess_flood_risk

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rescue_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    leader TEXT NOT NULL,
    phone TEXT NOT NULL,
    members INTEGER NOT NULL DEFAULT 5,
    base_location TEXT,
    status TEXT NOT NULL DEFAULT 'Available'
);
CREATE TABLE IF NOT EXISTS rescue_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    user_id INTEGER,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    location TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    people_count INTEGER NOT NULL,
    description TEXT NOT NULL,
    urgency TEXT NOT NULL,
    special_needs TEXT,
    priority_score INTEGER NOT NULL DEFAULT 0,
    is_urgent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Pending',
    team_id INTEGER REFERENCES rescue_teams(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS request_updates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    team_label TEXT,
    updated_by TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS shelters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    capacity INTEGER NOT NULL,
    occupancy INTEGER NOT NULL DEFAULT 0,
    facilities TEXT,
    accessibility TEXT,
    contact TEXT,
    status TEXT NOT NULL DEFAULT 'Open',
    updated_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS flood_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    risk_level TEXT NOT NULL,
    rainfall_mm REAL NOT NULL,
    river_level_m REAL NOT NULL,
    danger_level_m REAL NOT NULL,
    notes TEXT,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS flood_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_name TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    severity TEXT NOT NULL,
    water_depth_cm INTEGER,
    description TEXT NOT NULL,
    reporter_name TEXT,
    user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Unverified',
    created_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    location TEXT NOT NULL,
    source TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    is_simulated INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS risk_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_name TEXT NOT NULL,
    rainfall_mm REAL NOT NULL,
    river_level_m REAL NOT NULL,
    danger_level_m REAL NOT NULL,
    reported_floods INTEGER NOT NULL,
    risk_level TEXT NOT NULL,
    score INTEGER NOT NULL,
    user_id INTEGER,
    created_at TEXT NOT NULL
);
"""


def now_str(minutes_ago=0):
    return (datetime.now() - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%d %H:%M")


# ---------- connection helpers (used inside a request) ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def scalar(sql, args=()):
    row = query(sql, args, one=True)
    return row[0] if row else 0


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


# ---------- setup ----------
def init_db():
    """Create tables and insert sample data the first time the app runs."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed(conn)
    conn.commit()
    conn.close()


def seed(conn):
    from app_logic import compute_priority  # local import avoids a circular import

    # Demo accounts (passwords are stored hashed). Change them before any real use.
    users = [
        ("Demo Administrator", "admin@floodrescue.local", "9000000000", "Admin@123", "admin"),
        ("Demo Public User", "user@floodrescue.local", "9000000001", "User@1234", "user"),
    ]
    for name, email, phone, pw, role in users:
        conn.execute(
            "INSERT INTO users (name,email,phone,password_hash,role,created_at) VALUES (?,?,?,?,?,?)",
            (name, email, phone, generate_password_hash(pw), role, now_str()))

    teams = [
        ("RT-01", "Alpha Boat Rescue", "Insp. R. Kumar", "9000000101", 8, "Chennai Central", "Available"),
        ("RT-02", "Bravo Medical Response", "Dr. S. Priya", "9000000102", 6, "Tambaram, Chennai", "Available"),
        ("RT-03", "Charlie Water Rescue", "Lt. A. Menon", "9000000103", 9, "Kochi", "Available"),
        ("RT-04", "Delta Logistics Unit", "Mr. T. Das", "9000000104", 5, "Guwahati", "Off Duty"),
        ("RT-05", "Echo Relief Team", "Ms. N. Fernandes", "9000000105", 7, "Mumbai", "Available"),
    ]
    conn.executemany("INSERT INTO rescue_teams (team_code,name,leader,phone,members,base_location,status) "
                     "VALUES (?,?,?,?,?,?,?)", teams)

    shelters = [
        ("Velachery Community Hall", "Velachery Main Rd, Chennai", "Chennai", 12.9815, 80.2180, 300, 120,
         "Drinking water, Food, Medical corner, Toilets", "Ramp access, ground floor", "9000000201", "Open"),
        ("Adyar Government School Shelter", "Sardar Patel Rd, Adyar, Chennai", "Chennai", 13.0067, 80.2570, 450, 438,
         "Drinking water, Food, Toilets", "Ground floor only", "9000000202", "Open"),
        ("Tambaram Relief Camp", "GST Rd, Tambaram, Chennai", "Chennai", 12.9249, 80.1000, 600, 150,
         "Drinking water, Food, Medical corner, Power backup, Toilets", "Ramp and wheelchair access", "9000000203", "Open"),
        ("Aluva Higher Secondary School", "Aluva, Ernakulam", "Kochi", 10.1004, 76.3570, 400, 210,
         "Drinking water, Food, Toilets", "Information not available", "9000000204", "Open"),
        ("Kuttanad Relief Centre", "Kuttanad, Alappuzha", "Alappuzha", 9.4981, 76.3388, 350, 350,
         "Drinking water, Food", "Information not available", "9000000205", "Full"),
        ("Dispur Indoor Stadium", "Dispur, Guwahati", "Guwahati", 26.1433, 91.7898, 800, 240,
         "Drinking water, Food, Medical corner, Power backup, Toilets", "Ramp access", "9000000206", "Open"),
        ("Kurla Municipal School", "Kurla West, Mumbai", "Mumbai", 19.0726, 72.8845, 500, 90,
         "Drinking water, Food, Toilets", "Ground floor, ramp access", "9000000207", "Open"),
        ("Patna Relief Camp", "Near Gandhi Maidan, Patna", "Patna", 25.6093, 85.1376, 1000, 400,
         "Drinking water, Food, Medical corner, Toilets", "Information not available", "9000000208", "Closed"),
    ]
    for s in shelters:
        conn.execute("INSERT INTO shelters (name,address,city,latitude,longitude,capacity,occupancy,facilities,"
                     "accessibility,contact,status,updated_at,is_simulated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
                     s + (now_str(),))

    # name, city, lat, lon, rainfall, river level, danger level, report count (for scoring), notes
    locations = [
        ("Velachery", "Chennai", 12.9791, 80.2209, 190.0, 3.9, 4.2, 4, "Low-lying residential area, repeated waterlogging."),
        ("Adyar River Banks", "Chennai", 13.0012, 80.2565, 95.0, 2.9, 4.0, 1, "River bank settlements near the estuary."),
        ("Mudichur", "Chennai", 12.9087, 80.0846, 210.0, 4.4, 4.2, 3, "Adyar river overflow zone."),
        ("Aluva (Periyar)", "Kochi", 10.1076, 76.3516, 120.0, 2.6, 3.5, 2, "Periyar river bank town."),
        ("Kuttanad", "Alappuzha", 9.4000, 76.4000, 160.0, 3.4, 3.5, 5, "Below sea level farmland region."),
        ("Guwahati Riverfront", "Guwahati", 26.1445, 91.7362, 70.0, 2.2, 3.8, 0, "Brahmaputra riverfront."),
        ("Kurla", "Mumbai", 19.0726, 72.8777, 55.0, 1.0, 3.0, 1, "Mithi river catchment."),
        ("Vaigai Banks", "Madurai", 9.9252, 78.1198, 18.0, 0.8, 3.0, 0, "Seasonal river, currently low."),
        ("Patna Ganga Ghats", "Patna", 25.5941, 85.1376, 30.0, 2.4, 4.5, 0, "Ganga river ghat area."),
    ]
    for name, city, lat, lon, rain, river, danger, rep, notes in locations:
        level = assess_flood_risk(rain, river, danger, rep)["level"]
        conn.execute("INSERT INTO flood_locations (name,city,latitude,longitude,risk_level,rainfall_mm,river_level_m,"
                     "danger_level_m,notes,source,updated_at,is_simulated) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                     (name, city, lat, lon, level, rain, river, danger, notes,
                      "Sample data (simulated)", now_str(30)))

    reports = [
        ("Velachery Main Road", 12.9830, 80.2190, "High", 60, "Water entering ground-floor homes near the bus stand.", "Sample reporter", "Unverified", 25),
        ("Mudichur Bridge", 12.9100, 80.0870, "High", 90, "Road under water, vehicles stuck.", "Sample reporter", "Verified", 70),
        ("Aluva Market", 10.1060, 76.3560, "Medium", 30, "Knee-deep water in market lane.", "Sample reporter", "Unverified", 140),
        ("Kuttanad Canal Road", 9.4100, 76.3900, "High", 80, "Canal overflowing onto village road.", "Sample reporter", "Verified", 200),
    ]
    for loc, lat, lon, sev, depth, desc, rep, st, ago in reports:
        conn.execute("INSERT INTO flood_reports (location_name,latitude,longitude,severity,water_depth_cm,description,"
                     "reporter_name,status,created_at,is_simulated) VALUES (?,?,?,?,?,?,?,?,?,1)",
                     (loc, lat, lon, sev, depth, desc, rep, st, now_str(ago)))

    alerts = [
        ("High flood risk - Velachery & Mudichur", "Heavy rainfall and a rising river. Residents of low-lying streets should be ready to move to shelters.", "Severe", "Flood Warning", "Chennai", 20),
        ("River level near danger mark - Adyar", "River gauge is close to the danger level. Monitoring every hour.", "Warning", "River Level", "Chennai", 55),
        ("Road closure - Mudichur Bridge", "Bridge is flooded. Use alternate routes. Safety of routes is not verified.", "Warning", "Road Closure", "Chennai", 90),
        ("Shelter update - Adyar School", "Shelter is almost full. Please use Tambaram Relief Camp or Velachery Hall.", "Watch", "Shelter Update", "Chennai", 120),
        ("Kuttanad Relief Centre is full", "No more space at the centre. Nearby alternatives are being arranged.", "Warning", "Shelter Update", "Alappuzha", 180),
        ("Emergency announcement", "Keep phones charged, store drinking water and keep documents in a waterproof bag.", "Info", "Announcement", "All areas", 300),
    ]
    for title, msg, sev, typ, loc, ago in alerts:
        conn.execute("INSERT INTO alerts (title,message,severity,alert_type,location,source,is_active,is_simulated,created_at) "
                     "VALUES (?,?,?,?,?,?,1,1,?)",
                     (title, msg, sev, typ, loc, "Sample data (simulated) - not an official warning", now_str(ago)))

    # name, phone, location, lat, lon, people, description, urgency, special, status, team_index(1-based or None), minutes ago
    requests = [
        ("Demo Resident A", "9000000301", "12 Lake View St, Velachery, Chennai", 12.9800, 80.2200, 6,
         "Water is rising and we are trapped on the first floor with two children.", "Critical", "Two small children", "Pending", None, 15),
        ("Demo Resident B", "9000000302", "Mudichur Main Road, Chennai", 12.9090, 80.0850, 4,
         "Elderly parents cannot walk, water is entering the house.", "High", "Wheelchair user", "Team Assigned", 1, 60),
        ("Demo Resident C", "9000000303", "Aluva Market Road, Kochi", 10.1070, 76.3550, 3,
         "Ground floor flooded, need food and drinking water.", "Medium", "", "Under Review", None, 95),
        ("Demo Resident D", "9000000304", "Kuttanad Village Road, Alappuzha", 9.4050, 76.3950, 10,
         "Village cut off by flood water, need boat evacuation.", "High", "Pregnant woman", "In Progress", 3, 150),
        ("Demo Resident E", "9000000305", "Kurla West, Mumbai", 19.0730, 72.8800, 2,
         "Water on the street, wish to move to a shelter.", "Low", "", "Rescued", 5, 400),
    ]
    for i, (name, phone, loc, lat, lon, ppl, desc, urg, special, status, team_i, ago) in enumerate(requests, start=1):
        score, urgent = compute_priority(urg, ppl, special, desc)
        rid = f"FR-DEMO-{i:04d}"
        team_id = team_i
        conn.execute("INSERT INTO rescue_requests (request_id,name,phone,location,latitude,longitude,people_count,"
                     "description,urgency,special_needs,priority_score,is_urgent,status,team_id,created_at,updated_at) "
                     "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (rid, name, phone, loc, lat, lon, ppl, desc, urg, special, score, urgent, status, team_id,
                      now_str(ago), now_str(max(ago - 10, 0))))
        conn.execute("INSERT INTO request_updates (request_id,status,note,team_label,updated_by,created_at) VALUES (?,?,?,?,?,?)",
                     (rid, "Pending", "Request received.", None, "System", now_str(ago)))
        if status != "Pending":
            conn.execute("INSERT INTO request_updates (request_id,status,note,team_label,updated_by,created_at) VALUES (?,?,?,?,?,?)",
                         (rid, status, "Sample progress update.", None, "Demo Administrator", now_str(max(ago - 10, 0))))
    # keep team statuses consistent with the sample missions
    conn.execute("UPDATE rescue_teams SET status='On Mission' WHERE id IN (1,3)")
