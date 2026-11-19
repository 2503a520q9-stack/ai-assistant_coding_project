"""
AI-Assisted Flood Rescue & Evacuation System - Flask application.

Run:  python app.py      then open http://127.0.0.1:5000
"""
import os
import secrets
import string
from datetime import datetime
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import db
from app_logic import (ACTIVE_STATUSES, ALERT_SEVERITIES, ALERT_TYPES, DONE_STATUSES,
                       RISK_LEVELS, SHELTER_STATUSES, STATUSES, TEAM_STATUSES,
                       URGENCY_LEVELS, compute_priority, password_problem, to_float,
                       to_int, valid_email, valid_phone)
from services.risk_assessment import assess_flood_risk

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key-before-real-use")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
ADMIN_INVITE_CODE = os.environ.get("ADMIN_INVITE_CODE", "FLOOD-ADMIN-2026")

app.teardown_appcontext(db.close_db)
query, scalar, execute, now_str = db.query, db.scalar, db.execute, db.now_str


# ======================================================================
# Security helpers: CSRF protection, login / admin guards
# ======================================================================
@app.before_request
def load_user_and_check_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    g.user = None
    if session.get("user_id"):
        g.user = query("SELECT id,name,email,phone,role FROM users WHERE id=?", (session["user_id"],), one=True)
        if g.user is None:
            session.pop("user_id", None)
    if request.method == "POST":
        token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token") or ""
        if not secrets.compare_digest(token, session.get("csrf_token", "")):
            abort(400, "Your session expired or the form was invalid. Please reload the page and try again.")


@app.context_processor
def inject_globals():
    return dict(csrf_token=session.get("csrf_token", ""), current_user=g.get("user"),
                STATUSES=STATUSES, URGENCY_LEVELS=URGENCY_LEVELS, year=datetime.now().year)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in as an administrator.", "warning")
            return redirect(url_for("login", next=request.path))
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only allow redirects to paths inside this website."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("index")


BADGE_COLORS = {
    "Low": "success", "Medium": "warning", "High": "danger", "Critical": "danger",
    "Pending": "secondary", "Under Review": "info", "Team Assigned": "primary", "In Progress": "warning",
    "Rescued": "success", "Closed": "dark", "Available": "success", "On Mission": "warning",
    "Off Duty": "secondary", "Open": "success", "Full": "danger", "Info": "info", "Watch": "warning",
    "Warning": "orange", "Severe": "danger", "Unverified": "secondary", "Verified": "success",
    "Dismissed": "dark",
}


@app.template_filter("badge")
def badge_filter(value):
    return BADGE_COLORS.get(value, "secondary")


# ======================================================================
# Public pages
# ======================================================================
@app.route("/")
def index():
    stats = {
        "active_alerts": scalar("SELECT COUNT(*) FROM alerts WHERE is_active=1"),
        "open_shelters": scalar("SELECT COUNT(*) FROM shelters WHERE status='Open' AND occupancy<capacity"),
        "high_risk": scalar("SELECT COUNT(*) FROM flood_locations WHERE risk_level='High'"),
        "pending": scalar("SELECT COUNT(*) FROM rescue_requests WHERE status IN ('Pending','Under Review')"),
        "teams_available": scalar("SELECT COUNT(*) FROM rescue_teams WHERE status='Available'"),
    }
    latest_alerts = query("SELECT * FROM alerts WHERE is_active=1 ORDER BY created_at DESC, id DESC LIMIT 3")
    return render_template("index.html", stats=stats, latest_alerts=latest_alerts)


# ---------------------------------------------------------------- auth
@app.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("name", "email", "phone", "admin_code")}
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        email = form["email"].lower()
        errors = []
        if len(form["name"]) < 2 or len(form["name"]) > 80:
            errors.append("Please enter your full name (2-80 characters).")
        if not valid_email(email):
            errors.append("Please enter a valid email address.")
        if not valid_phone(form["phone"]):
            errors.append("Please enter a valid phone number (7-15 digits).")
        problem = password_problem(password)
        if problem:
            errors.append(problem)
        if password != confirm:
            errors.append("Passwords do not match.")
        role = "user"
        if form["admin_code"]:
            if secrets.compare_digest(form["admin_code"], ADMIN_INVITE_CODE):
                role = "admin"
            else:
                errors.append("The administrator invite code is not correct.")
        if not errors and query("SELECT id FROM users WHERE email=?", (email,), one=True):
            errors.append("An account with this email already exists.")
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            execute("INSERT INTO users (name,email,phone,password_hash,role,created_at) VALUES (?,?,?,?,?,?)",
                    (form["name"], email, form["phone"], generate_password_hash(password), role, now_str()))
            flash("Account created. You can log in now.", "success")
            return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE email=?", (email,), one=True)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_hex(16)
            flash(f"Welcome back, {user['name']}.", "success")
            if user["role"] == "admin" and not request.args.get("next"):
                return redirect(url_for("dashboard"))
            return redirect(safe_next(request.args.get("next")))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------- rescue request (public)
def new_request_id():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        rid = "FR-" + datetime.now().strftime("%Y%m%d") + "-" + "".join(secrets.choice(alphabet) for _ in range(5))
        if not query("SELECT 1 FROM rescue_requests WHERE request_id=?", (rid,), one=True):
            return rid


@app.route("/rescue-request", methods=["GET", "POST"])
def rescue_request():
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("name", "phone", "location", "people", "description", "urgency", "special_needs", "latitude", "longitude")}
        errors = []
        people = to_int(form["people"])
        if len(form["name"]) < 2:
            errors.append("Please enter your name.")
        if not valid_phone(form["phone"]):
            errors.append("Please enter a valid contact number.")
        if len(form["location"]) < 5:
            errors.append("Please describe your current location or address (at least 5 characters).")
        if people is None or not 1 <= people <= 500:
            errors.append("Number of people must be between 1 and 500.")
        if len(form["description"]) < 10:
            errors.append("Please describe the emergency (at least 10 characters).")
        if form["urgency"] not in URGENCY_LEVELS:
            errors.append("Please choose an urgency level.")
        if len(form["description"]) > 1000 or len(form["special_needs"]) > 500:
            errors.append("Description or special needs text is too long.")
        lat, lon = to_float(form["latitude"]), to_float(form["longitude"])
        if lat is not None and lon is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            lat = lon = None
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            score, urgent = compute_priority(form["urgency"], people, form["special_needs"], form["description"])
            rid = new_request_id()
            execute("INSERT INTO rescue_requests (request_id,user_id,name,phone,location,latitude,longitude,people_count,"
                    "description,urgency,special_needs,priority_score,is_urgent,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, g.user["id"] if g.user else None, form["name"], form["phone"], form["location"], lat, lon,
                     people, form["description"], form["urgency"], form["special_needs"], score, urgent,
                     "Pending", now_str(), now_str()))
            execute("INSERT INTO request_updates (request_id,status,note,updated_by,created_at) VALUES (?,?,?,?,?)",
                    (rid, "Pending", "Request received and waiting for review.", "System", now_str()))
            flash(f"Your rescue request has been submitted. Your request ID is {rid}. Please save it.", "success")
            return redirect(url_for("track", request_id=rid))
    return render_template("rescue_request.html", form=form)


@app.route("/track", methods=["GET"])
def track():
    rid = request.args.get("request_id", "").strip().upper()
    req = timeline = None
    if rid:
        req = query("SELECT r.*, t.name AS team_name, t.team_code FROM rescue_requests r "
                    "LEFT JOIN rescue_teams t ON r.team_id=t.id WHERE r.request_id=?", (rid,), one=True)
        if req is None:
            flash("No request found with that ID. Please check and try again.", "warning")
        else:
            timeline = query("SELECT * FROM request_updates WHERE request_id=? ORDER BY id DESC", (rid,))
    return render_template("track.html", req=req, timeline=timeline, rid=rid)


# ---------------------------------------------------------------- flood reports (public)
@app.route("/report-flood", methods=["GET", "POST"])
def report_flood():
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("location_name", "severity", "water_depth_cm", "description", "reporter_name", "latitude", "longitude")}
        errors = []
        if len(form["location_name"]) < 3:
            errors.append("Please enter the location of the flooding.")
        if form["severity"] not in RISK_LEVELS:
            errors.append("Please choose how severe the flooding is.")
        depth = to_int(form["water_depth_cm"], 0)
        if depth < 0 or depth > 1000:
            errors.append("Water depth must be between 0 and 1000 cm.")
        if len(form["description"]) < 10:
            errors.append("Please describe what you see (at least 10 characters).")
        lat, lon = to_float(form["latitude"]), to_float(form["longitude"])
        if lat is not None and lon is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            lat = lon = None
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            execute("INSERT INTO flood_reports (location_name,latitude,longitude,severity,water_depth_cm,description,"
                    "reporter_name,user_id,status,created_at,is_simulated) VALUES (?,?,?,?,?,?,?,?,?,?,0)",
                    (form["location_name"], lat, lon, form["severity"], depth, form["description"],
                     form["reporter_name"] or (g.user["name"] if g.user else "Anonymous"),
                     g.user["id"] if g.user else None, "Unverified", now_str()))
            flash("Thank you. Your flood report was submitted and will be reviewed by an administrator.", "success")
            return redirect(url_for("flood_map"))
    return render_template("report_flood.html", form=form)


# ---------------------------------------------------------------- map
@app.route("/map")
def flood_map():
    return render_template("flood_map.html")


@app.route("/api/map-data")
def api_map_data():
    locations = [dict(r) for r in query("SELECT * FROM flood_locations ORDER BY name")]
    shelters = [dict(r) for r in query("SELECT * FROM shelters ORDER BY name")]
    reports = [dict(r) for r in query(
        "SELECT * FROM flood_reports WHERE status!='Dismissed' AND latitude IS NOT NULL ORDER BY created_at DESC")]
    return jsonify(locations=locations, shelters=shelters, reports=reports)


# ---------------------------------------------------------------- risk assessment
@app.route("/risk-assessment", methods=["GET", "POST"])
def risk_assessment():
    locations = query("SELECT * FROM flood_locations ORDER BY name")
    form, result = {}, None
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in
                ("location_id", "location_name", "rainfall", "river_level", "danger_level", "reports")}
        rain, river = to_float(form["rainfall"]), to_float(form["river_level"])
        danger, reports = to_float(form["danger_level"]), to_int(form["reports"], 0)
        errors = []
        if rain is None or not 0 <= rain <= 1500:
            errors.append("Rainfall must be a number between 0 and 1500 mm.")
        if river is None or not 0 <= river <= 100:
            errors.append("River level must be a number between 0 and 100 m.")
        if danger is None or not 0 < danger <= 100:
            errors.append("Danger level must be a number greater than 0 (max 100 m).")
        if reports < 0 or reports > 1000:
            errors.append("Number of reports must be between 0 and 1000.")
        loc = None
        if form["location_id"]:
            loc = query("SELECT * FROM flood_locations WHERE id=?", (to_int(form["location_id"], 0),), one=True)
        name = loc["name"] if loc else (form["location_name"] or "Custom location")
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            result = assess_flood_risk(rain, river, danger, reports)
            result["location"] = name
            execute("INSERT INTO risk_assessments (location_name,rainfall_mm,river_level_m,danger_level_m,reported_floods,"
                    "risk_level,score,user_id,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (name, rain, river, danger, reports, result["level"], result["score"],
                     g.user["id"] if g.user else None, now_str()))
            if loc and g.user and g.user["role"] == "admin" and request.form.get("apply_to_map"):
                execute("UPDATE flood_locations SET risk_level=?, rainfall_mm=?, river_level_m=?, danger_level_m=?, "
                        "source=?, updated_at=? WHERE id=?",
                        (result["level"], rain, river, danger, f"Administrator input ({g.user['name']})", now_str(), loc["id"]))
                flash(f"Map risk for {loc['name']} was updated to {result['level']}.", "success")
    recent = []
    if g.user and g.user["role"] == "admin":
        recent = query("SELECT * FROM risk_assessments ORDER BY id DESC LIMIT 8")
    return render_template("risk_assessment.html", locations=locations, form=form, result=result, recent=recent)


@app.route("/api/location/<int:loc_id>")
def api_location(loc_id):
    loc = query("SELECT * FROM flood_locations WHERE id=?", (loc_id,), one=True)
    if loc is None:
        abort(404)
    count = scalar("SELECT COUNT(*) FROM flood_reports WHERE status!='Dismissed' AND location_name LIKE ?",
                   (f"%{loc['name'].split()[0]}%",))
    data = dict(loc)
    data["reports"] = count
    return jsonify(data)


# ---------------------------------------------------------------- shelters (public view, admin manage)
@app.route("/shelters")
def shelters():
    q = request.args.get("q", "").strip()
    only_available = request.args.get("available") == "1"
    sql, args = "SELECT * FROM shelters WHERE 1=1", []
    if q:
        sql += " AND (name LIKE ? OR city LIKE ? OR address LIKE ?)"
        args += [f"%{q}%"] * 3
    if only_available:
        sql += " AND status='Open' AND occupancy<capacity"
    rows = query(sql + " ORDER BY city, name", args)
    return render_template("shelters.html", shelters=rows, q=q, only_available=only_available,
                           SHELTER_STATUSES=SHELTER_STATUSES)


def read_shelter_form():
    f = {k: request.form.get(k, "").strip() for k in
         ("name", "address", "city", "latitude", "longitude", "capacity", "occupancy", "facilities",
          "accessibility", "contact", "status")}
    errors = []
    lat, lon = to_float(f["latitude"]), to_float(f["longitude"])
    cap, occ = to_int(f["capacity"]), to_int(f["occupancy"], 0)
    if len(f["name"]) < 3 or len(f["address"]) < 3 or len(f["city"]) < 2:
        errors.append("Shelter name, address and city are required.")
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        errors.append("Enter valid latitude and longitude.")
    if cap is None or cap < 1 or cap > 100000:
        errors.append("Capacity must be a positive number.")
    if occ < 0 or (cap is not None and occ > cap):
        errors.append("Occupancy must be between 0 and the capacity.")
    if f["status"] not in SHELTER_STATUSES:
        errors.append("Choose a valid status.")
    return f, lat, lon, cap, occ, errors


@app.route("/shelters/add", methods=["POST"])
@admin_required
def shelter_add():
    f, lat, lon, cap, occ, errors = read_shelter_form()
    if errors:
        for e in errors:
            flash(e, "danger")
    else:
        status = "Full" if f["status"] == "Open" and occ >= cap else f["status"]
        execute("INSERT INTO shelters (name,address,city,latitude,longitude,capacity,occupancy,facilities,accessibility,"
                "contact,status,updated_at,is_simulated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,0)",
                (f["name"], f["address"], f["city"], lat, lon, cap, occ, f["facilities"],
                 f["accessibility"] or "Information not available", f["contact"], status, now_str()))
        flash("Shelter added.", "success")
    return redirect(url_for("shelters"))


@app.route("/shelters/<int:sid>/update", methods=["POST"])
@admin_required
def shelter_update(sid):
    shelter = query("SELECT * FROM shelters WHERE id=?", (sid,), one=True)
    if shelter is None:
        abort(404)
    occ = to_int(request.form.get("occupancy"), -1)
    status = request.form.get("status", "")
    if occ < 0 or occ > shelter["capacity"] or status not in SHELTER_STATUSES:
        flash("Occupancy must be between 0 and capacity, and status must be valid.", "danger")
    else:
        if status == "Open" and occ >= shelter["capacity"]:
            status = "Full"
        execute("UPDATE shelters SET occupancy=?, status=?, updated_at=? WHERE id=?", (occ, status, now_str(), sid))
        flash(f"{shelter['name']} updated.", "success")
    return redirect(url_for("shelters"))


# ---------------------------------------------------------------- alerts (public view, admin manage)
@app.route("/alerts")
def alerts():
    typ = request.args.get("type", "")
    sev = request.args.get("severity", "")
    sql, args = "SELECT * FROM alerts WHERE 1=1", []
    if not (g.user and g.user["role"] == "admin"):
        sql += " AND is_active=1"
    if typ in ALERT_TYPES:
        sql += " AND alert_type=?"
        args.append(typ)
    if sev in ALERT_SEVERITIES:
        sql += " AND severity=?"
        args.append(sev)
    rows = query(sql + " ORDER BY is_active DESC, created_at DESC, id DESC", args)
    reports = query("SELECT * FROM flood_reports WHERE status!='Dismissed' ORDER BY created_at DESC LIMIT 6")
    return render_template("alerts.html", alerts=rows, reports=reports, typ=typ, sev=sev,
                           ALERT_TYPES=ALERT_TYPES, ALERT_SEVERITIES=ALERT_SEVERITIES)


@app.route("/alerts/add", methods=["POST"])
@admin_required
def alert_add():
    f = {k: request.form.get(k, "").strip() for k in ("title", "message", "severity", "alert_type", "location", "source")}
    if (len(f["title"]) < 3 or len(f["message"]) < 5 or len(f["location"]) < 2
            or f["severity"] not in ALERT_SEVERITIES or f["alert_type"] not in ALERT_TYPES):
        flash("Please fill in title, message, location, type and severity.", "danger")
    else:
        simulated = 1 if request.form.get("is_simulated") else 0
        source = f["source"] or f"Administrator: {g.user['name']}"
        if simulated:
            source += " (simulated demo alert)"
        execute("INSERT INTO alerts (title,message,severity,alert_type,location,source,is_active,is_simulated,created_at) "
                "VALUES (?,?,?,?,?,?,1,?,?)",
                (f["title"], f["message"], f["severity"], f["alert_type"], f["location"], source, simulated, now_str()))
        flash("Alert published.", "success")
    return redirect(url_for("alerts"))


@app.route("/alerts/<int:aid>/toggle", methods=["POST"])
@admin_required
def alert_toggle(aid):
    execute("UPDATE alerts SET is_active = 1 - is_active WHERE id=?", (aid,))
    flash("Alert visibility changed.", "info")
    return redirect(url_for("alerts"))


@app.route("/alerts/<int:aid>/delete", methods=["POST"])
@admin_required
def alert_delete(aid):
    execute("DELETE FROM alerts WHERE id=?", (aid,))
    flash("Alert deleted.", "info")
    return redirect(url_for("alerts"))


# ======================================================================
# Administrator pages
# ======================================================================
@app.route("/dashboard")
@admin_required
def dashboard():
    stats = {
        "total": scalar("SELECT COUNT(*) FROM rescue_requests"),
        "pending": scalar("SELECT COUNT(*) FROM rescue_requests WHERE status IN ('Pending','Under Review')"),
        "urgent": scalar("SELECT COUNT(*) FROM rescue_requests WHERE is_urgent=1 AND status NOT IN ('Rescued','Closed')"),
        "active_teams": scalar("SELECT COUNT(*) FROM rescue_teams WHERE status='On Mission'"),
        "available_teams": scalar("SELECT COUNT(*) FROM rescue_teams WHERE status='Available'"),
        "shelters": scalar("SELECT COUNT(*) FROM shelters WHERE status='Open' AND occupancy<capacity"),
        "free_beds": scalar("SELECT COALESCE(SUM(capacity-occupancy),0) FROM shelters WHERE status='Open'"),
        "unverified": scalar("SELECT COUNT(*) FROM flood_reports WHERE status='Unverified'"),
        "high_risk": scalar("SELECT COUNT(*) FROM flood_locations WHERE risk_level='High'"),
    }
    urgent_requests = query(
        "SELECT * FROM rescue_requests WHERE is_urgent=1 AND status NOT IN ('Rescued','Closed') "
        "ORDER BY priority_score DESC, created_at LIMIT 5")
    incidents = query("SELECT * FROM flood_reports WHERE status!='Dismissed' ORDER BY created_at DESC LIMIT 5")
    counts = {r["status"]: r["c"] for r in query("SELECT status, COUNT(*) c FROM rescue_requests GROUP BY status")}
    chart = [counts.get(s, 0) for s in STATUSES]
    return render_template("dashboard.html", stats=stats, urgent_requests=urgent_requests,
                           incidents=incidents, chart_labels=STATUSES, chart_data=chart)


@app.route("/admin/requests")
@admin_required
def rescue_management():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    urgency = request.args.get("urgency", "")
    sql = ("SELECT r.*, t.name AS team_name, t.team_code FROM rescue_requests r "
           "LEFT JOIN rescue_teams t ON r.team_id=t.id WHERE 1=1")
    args = []
    if q:
        sql += " AND (r.request_id LIKE ? OR r.name LIKE ? OR r.location LIKE ? OR r.phone LIKE ?)"
        args += [f"%{q}%"] * 4
    if status in STATUSES:
        sql += " AND r.status=?"
        args.append(status)
    if urgency in URGENCY_LEVELS:
        sql += " AND r.urgency=?"
        args.append(urgency)
    sql += (" ORDER BY CASE WHEN r.status IN ('Rescued','Closed') THEN 1 ELSE 0 END, "
            "r.priority_score DESC, r.created_at DESC")
    return render_template("rescue_management.html", requests=query(sql, args), q=q, status=status, urgency=urgency)


def refresh_team(team_id):
    """Set a team to Available / On Mission depending on its active requests."""
    if not team_id:
        return
    team = query("SELECT * FROM rescue_teams WHERE id=?", (team_id,), one=True)
    if team is None or team["status"] == "Off Duty":
        return
    marks = ",".join("?" * len(ACTIVE_STATUSES))
    active = scalar(f"SELECT COUNT(*) FROM rescue_requests WHERE team_id=? AND status IN ({marks})",
                    (team_id, *ACTIVE_STATUSES))
    execute("UPDATE rescue_teams SET status=? WHERE id=?", ("On Mission" if active else "Available", team_id))


def apply_request_update(rid, new_status, team_id, note):
    """Shared by the request page and the teams page. Returns an error text or None."""
    req = query("SELECT * FROM rescue_requests WHERE request_id=?", (rid,), one=True)
    if req is None:
        return "Request not found."
    if new_status not in STATUSES:
        return "Invalid status."
    team = None
    if team_id:
        team = query("SELECT * FROM rescue_teams WHERE id=?", (team_id,), one=True)
        if team is None:
            return "Selected team does not exist."
        if team["status"] == "Off Duty" and team["id"] != req["team_id"]:
            return f"{team['name']} is off duty and cannot be assigned."
    if team and new_status in ("Pending", "Under Review"):
        new_status = "Team Assigned"
    if new_status in ACTIVE_STATUSES and not team:
        return "Assign a rescue team before moving the request to 'Team Assigned' or 'In Progress'."
    if len(note) > 500:
        return "Progress note is too long (max 500 characters)."
    old_team = req["team_id"]
    execute("UPDATE rescue_requests SET status=?, team_id=?, updated_at=? WHERE request_id=?",
            (new_status, team["id"] if team else None, now_str(), rid))
    label = f"{team['team_code']} {team['name']}" if team else None
    execute("INSERT INTO request_updates (request_id,status,note,team_label,updated_by,created_at) VALUES (?,?,?,?,?,?)",
            (rid, new_status, note or "Status updated.", label, g.user["name"], now_str()))
    refresh_team(old_team)
    refresh_team(team["id"] if team else None)
    return None


@app.route("/admin/requests/<rid>")
@admin_required
def request_detail(rid):
    req = query("SELECT r.*, t.name AS team_name, t.team_code FROM rescue_requests r "
                "LEFT JOIN rescue_teams t ON r.team_id=t.id WHERE r.request_id=?", (rid,), one=True)
    if req is None:
        abort(404)
    teams = query("SELECT * FROM rescue_teams ORDER BY team_code")
    timeline = query("SELECT * FROM request_updates WHERE request_id=? ORDER BY id DESC", (rid,))
    return render_template("request_detail.html", req=req, teams=teams, timeline=timeline)


@app.route("/admin/requests/<rid>/update", methods=["POST"])
@admin_required
def request_update(rid):
    error = apply_request_update(rid, request.form.get("status", ""), to_int(request.form.get("team_id")),
                                 request.form.get("note", "").strip())
    if error:
        flash(error, "danger")
    else:
        flash("Request updated.", "success")
    return redirect(url_for("request_detail", rid=rid))


@app.route("/admin/teams")
@admin_required
def teams():
    rows = query("SELECT * FROM rescue_teams ORDER BY team_code")
    missions = {}
    for t in rows:
        missions[t["id"]] = query("SELECT * FROM rescue_requests WHERE team_id=? ORDER BY created_at DESC", (t["id"],))
    open_requests = query("SELECT request_id, name, urgency FROM rescue_requests "
                          "WHERE team_id IS NULL AND status IN ('Pending','Under Review') "
                          "ORDER BY priority_score DESC")
    return render_template("teams.html", teams=rows, missions=missions, open_requests=open_requests,
                           TEAM_STATUSES=TEAM_STATUSES)


@app.route("/admin/teams/add", methods=["POST"])
@admin_required
def team_add():
    f = {k: request.form.get(k, "").strip() for k in ("team_code", "name", "leader", "phone", "members", "base_location")}
    members = to_int(f["members"], 0)
    if (len(f["team_code"]) < 2 or len(f["name"]) < 3 or len(f["leader"]) < 2 or not valid_phone(f["phone"])
            or not 1 <= members <= 200):
        flash("Please fill in all team fields correctly.", "danger")
    elif query("SELECT 1 FROM rescue_teams WHERE team_code=?", (f["team_code"],), one=True):
        flash("That team ID already exists.", "danger")
    else:
        execute("INSERT INTO rescue_teams (team_code,name,leader,phone,members,base_location,status) VALUES (?,?,?,?,?,?,'Available')",
                (f["team_code"], f["name"], f["leader"], f["phone"], members, f["base_location"]))
        flash("Team added.", "success")
    return redirect(url_for("teams"))


@app.route("/admin/teams/<int:tid>/status", methods=["POST"])
@admin_required
def team_status(tid):
    status = request.form.get("status", "")
    team = query("SELECT * FROM rescue_teams WHERE id=?", (tid,), one=True)
    if team is None:
        abort(404)
    marks = ",".join("?" * len(ACTIVE_STATUSES))
    active = scalar(f"SELECT COUNT(*) FROM rescue_requests WHERE team_id=? AND status IN ({marks})", (tid, *ACTIVE_STATUSES))
    if status not in ("Available", "Off Duty"):
        flash("Choose Available or Off Duty. 'On Mission' is set automatically when a request is assigned.", "warning")
    elif status == "Off Duty" and active:
        flash("This team has active missions. Complete or reassign them first.", "danger")
    else:
        execute("UPDATE rescue_teams SET status=? WHERE id=?", (status, tid))
        refresh_team(tid)
        flash(f"{team['name']} availability updated.", "success")
    return redirect(url_for("teams"))


@app.route("/admin/teams/<int:tid>/assign", methods=["POST"])
@admin_required
def team_assign(tid):
    rid = request.form.get("request_id", "")
    error = apply_request_update(rid, "Team Assigned", tid, request.form.get("note", "").strip() or "Team assigned from Teams page.")
    flash(error or "Team assigned to the request.", "danger" if error else "success")
    return redirect(url_for("teams"))


@app.route("/admin/reports")
@admin_required
def admin_reports():
    status = request.args.get("status", "")
    sql, args = "SELECT * FROM flood_reports WHERE 1=1", []
    if status in ("Unverified", "Verified", "Dismissed"):
        sql += " AND status=?"
        args.append(status)
    rows = query(sql + " ORDER BY CASE status WHEN 'Unverified' THEN 0 ELSE 1 END, created_at DESC", args)
    return render_template("admin_reports.html", reports=rows, status=status)


@app.route("/admin/reports/<int:rid>/status", methods=["POST"])
@admin_required
def report_status(rid):
    status = request.form.get("status", "")
    if status not in ("Unverified", "Verified", "Dismissed"):
        flash("Invalid status.", "danger")
    else:
        execute("UPDATE flood_reports SET status=? WHERE id=?", (status, rid))
        flash(f"Report marked as {status}.", "success")
    return redirect(url_for("admin_reports"))


# ======================================================================
# Error pages
# ======================================================================
@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(500)
def handle_error(err):
    code = getattr(err, "code", 500)
    messages = {400: "Bad request", 403: "You do not have permission to view this page",
                404: "Page not found", 500: "Something went wrong on our side"}
    detail = getattr(err, "description", "") if code == 400 else ""
    return render_template("error.html", code=code, message=messages.get(code, "Error"), detail=detail), code


# Create tables and sample data when the app starts (safe to run many times).
db.init_db()

if __name__ == "__main__":
    app.run(debug=True)
