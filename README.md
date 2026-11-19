# AI-Assisted Flood Rescue & Evacuation System

A second-year engineering AI-assisted coding project: a Flask web application that helps coordinate flood
rescue and evacuation. Residents request rescue and find shelters; administrators prioritise requests,
assign rescue teams, publish alerts and manage shelters; a transparent rule-based "AI" engine estimates flood risk.

> **All data is simulated** (sample locations, shelters, teams and alerts). Risk results are rule-based
> estimates, not forecasts. Alerts are not official warnings. Route safety is not verified.
> In a real emergency call **112**.

## Tech stack
- Backend: Python Flask + SQLite (`sqlite3`, no ORM)
- Frontend: HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Leaflet + OpenStreetMap, Chart.js
- AI module: `services/risk_assessment.py` (transparent scoring rules, no extra libraries)
- Security: hashed passwords (Werkzeug), CSRF tokens on every form, role-based access, parameterised SQL, escaped output

## Folder structure
```
flood-rescue-system/
├── app.py                  Flask routes (pages, forms, admin actions, JSON API)
├── db.py                   SQLite connection helpers, schema, sample data
├── app_logic.py            Constants, validation helpers, request priority scoring
├── requirements.txt
├── database.db             Created automatically on first run (sample data included)
├── services/
│   └── risk_assessment.py  Rule-based flood risk engine
├── templates/              base.html, admin_base.html + one file per page
└── static/
    ├── css/style.css
    ├── js/app.js           General behaviour (GPS button, confirms, table filter)
    ├── js/map.js           Leaflet flood map, shelter map and routing
    └── images/hero-flood.svg
```

## Run in Visual Studio Code
1. Install Python 3.9+ from python.org (tick "Add Python to PATH") and VS Code with the **Python** extension.
2. In VS Code choose **File > Open Folder...** and open `flood-rescue-system`.
3. Open a terminal (**Terminal > New Terminal**) and create a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - macOS/Linux: `python3 -m venv venv` then `source venv/bin/activate`
4. Install requirements: `pip install -r requirements.txt`
5. Start the app: `python app.py`
6. Open **http://127.0.0.1:5000** in your browser (internet is needed for maps, Bootstrap and routing).

If PowerShell blocks the activate script, run `Set-ExecutionPolicy -Scope Process Bypass` first.

## Demo accounts (sample data)
| Role  | Email                    | Password   |
|-------|--------------------------|------------|
| Admin | admin@floodrescue.local  | Admin@123  |
| User  | user@floodrescue.local   | User@1234  |

Passwords are stored as salted hashes. To register a new administrator, enter the invite code
`FLOOD-ADMIN-2026` on the register page. Change it (and the secret key) before any real use:

- Windows PowerShell: `$env:ADMIN_INVITE_CODE="my-code"; $env:SECRET_KEY="long-random-text"; python app.py`
- macOS/Linux: `ADMIN_INVITE_CODE=my-code SECRET_KEY=long-random-text python app.py`

## Things to try (test checklist)
1. Home page: click **Get Help Now**, **Report Flood**, **View Flood Alerts**.
2. Submit a rescue request (e.g. "trapped", 4 people, Critical). Note the request ID and open **Track Request**.
3. Log in as admin: the dashboard shows the new request as urgent. Open it, assign team **RT-02**, set **In Progress**, add a note.
   The team becomes "On Mission"; set the request to **Rescued** and the team becomes "Available" again.
4. **Flood Map**: filter by risk, search "Chennai", click markers, toggle layers.
5. **Risk Check**: pick "Velachery" and press Assess risk to see the factor breakdown. As admin, tick "apply to map".
6. **Shelters**: search "Kochi", tick "Only shelters with space", press **Route** (allow location, or click the map).
7. **Alerts**: publish an alert as admin, filter, hide and delete it.
8. **Flood reports** (admin sidebar): verify or dismiss public reports.
9. Try invalid input (empty form, bad phone) to see validation messages.

## How the AI risk engine works
`score = rainfall points (max 40) + river-level points (max 40) + flood-report points (max 20)`
- Rainfall bands follow the IMD 24-hour categories (heavy, very heavy, extremely heavy).
- River points depend on level / danger level. At or above the danger level is always **High**.
- Score < 35 = Low, 35-64 = Medium, 65+ = High. Every factor is shown to the user.

The request **priority score** (0-100) combines urgency, number of people, special needs and danger keywords
("trapped", "child", "elderly", ...). It only sorts the list; a human always makes the decision.

## Troubleshooting
| Problem | Fix |
|---------|-----|
| `python` not found | Reinstall Python with "Add to PATH", or try `py` (Windows) / `python3` (macOS/Linux). |
| `ModuleNotFoundError: flask` | Activate the virtual environment, then `pip install -r requirements.txt`. |
| `Address already in use` / port 5000 busy | Edit the last line of `app.py`: `app.run(debug=True, port=5001)`. |
| Map is grey or empty | Check your internet connection (tiles and Leaflet load from CDNs). Press Ctrl+F5. |
| "Your session expired or the form was invalid" | Reload the page (CSRF token) and submit again. Cookies must be enabled. |
| Want to reset all data | Stop the app, delete `database.db`, start again. |
| `sqlite3.OperationalError: database is locked` | Close other programs (like DB Browser) that have `database.db` open. |
| Route button says routing service unreachable | The free OSRM demo server may be busy or blocked; try again later. |
| Cannot open admin pages | Log in with the admin demo account. Normal users get a 403 page. |

## Limitations (honest notes)
- No live government or sensor data. No real GPS tracking of teams. No SMS or email notifications.
- Flask debug mode is on for easy learning. Turn it off (`debug=False`) and use a production server for real deployments.
