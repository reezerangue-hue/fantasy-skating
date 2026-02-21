from flask import Flask, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json

app = Flask(__name__)
app.secret_key = "changethislater"

def get_db():
    conn = sqlite3.connect("skating.db")
    conn.row_factory = sqlite3.Row
    return conn

def get_competitions():
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT competition FROM results2").fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_results(competition, category):
    conn = get_db()
    rows = conn.execute("""
        SELECT segment, place, name, nation, score
        FROM results2
        WHERE competition=? AND category=?
        ORDER BY segment, place
    """, (competition, category)).fetchall()
    conn.close()
    return rows

def get_all_skaters():
    conn = get_db()
    rows = conn.execute("""
        SELECT name, nation, category, best_score, cost
        FROM skater_costs
        ORDER BY category, cost DESC, name ASC
    """).fetchall()
    conn.close()
    return rows

def get_team(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT t.category, t.name, t.nation, s.cost
        FROM team t
        LEFT JOIN skater_costs s ON t.name = s.name
        WHERE t.user_id=?
    """, (user_id,)).fetchall()
    conn.close()
    return rows

def get_fantasy_points(user_id):
    conn = get_db()
    team = [r[0] for r in conn.execute("SELECT name FROM team WHERE user_id=?", (user_id,)).fetchall()]

    ranges = {}
    for category in ["Men", "Women", "Pairs", "Ice Dance"]:
        row = conn.execute("""
            SELECT MAX(score), MIN(score) FROM results2
            WHERE category=? AND segment IN ('Free Skating', 'Free Dance')
        """, (category,)).fetchone()
        if row and row[0]:
            ranges[category] = (row[0], row[1])

    points = {}
    for name in team:
        results = conn.execute("""
            SELECT place, score, category FROM results2
            WHERE name=? AND segment IN ('Free Skating', 'Free Dance')
        """, (name,)).fetchall()
        total = 0
        for row in results:
            place, score, category = row[0], row[1], row[2]
            if category in ranges:
                max_score, min_score = ranges[category]
                score_range = max_score - min_score or 1
                normalized = ((score - min_score) / score_range) * 20
                total += round(normalized, 1)
            if place == 1: total += 5
            elif place == 2: total += 3
            elif place == 3: total += 1
        points[name] = round(total, 1)
    conn.close()
    return points

def get_stats():
    conn = get_db()
    skater_count = conn.execute("SELECT COUNT(DISTINCT name) FROM skater_costs").fetchone()[0]
    comp_count = conn.execute("SELECT COUNT(DISTINCT competition) FROM results2").fetchone()[0]
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    latest_comp = conn.execute("SELECT competition FROM results2 ORDER BY rowid DESC LIMIT 1").fetchone()
    latest_comp = latest_comp[0] if latest_comp else "N/A"
    conn.close()
    return skater_count, comp_count, user_count, latest_comp

def get_latest_results():
    conn = get_db()
    latest = conn.execute("""
        SELECT competition FROM results2
        ORDER BY rowid DESC LIMIT 1
    """).fetchone()
    if not latest:
        conn.close()
        return [], ""
    comp = latest[0]
    rows = conn.execute("""
        SELECT category, place, name, nation, score
        FROM results2
        WHERE competition=? AND segment IN ('Free Skating', 'Free Dance') AND place <= 3
        ORDER BY category, place
    """, (comp,)).fetchall()
    conn.close()
    return rows, comp

def current_user():
    return session.get("user_id"), session.get("username")

def nav(user_id, username):
    if user_id:
        auth = f'<span class="nav-user">👤 {username}</span><a href="/logout" class="nav-link">Log Out</a>'
    else:
        auth = '<a href="/login" class="nav-link">Log In</a><a href="/register" class="nav-link">Register</a>'
    return f"""
    <nav>
        <div class="nav-brand"><a href="/" style="text-decoration:none;color:inherit;">⛸ <span>Fantasy Figure Skating</span></a></div>
        <div class="nav-links">
            <a href="/results" class="nav-link">Results</a>
            <a href="/roster" class="nav-link">Roster</a>
            <a href="/draft" class="nav-link">Draft</a>
            <a href="/team" class="nav-link">My Team</a>
            <a href="/leaderboard" class="nav-link">Leaderboard</a>
            {auth}
        </div>
    </nav>
    """

STYLE = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Sans:wght@300;400;500&display=swap');

    :root {
        --ice: #e8f4f8;
        --deep-navy: #0a1628;
        --navy: #0f2044;
        --mid-navy: #1a3a6e;
        --blue: #1e56b0;
        --ice-blue: #6ab4d4;
        --frost: #b8dce8;
        --gold: #c9a84c;
        --white: #f0f8ff;
        --text: #e4eef5;
        --text-dim: #7a9bb5;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
        font-family: 'DM Sans', sans-serif;
        background-color: var(--deep-navy);
        color: var(--text);
        min-height: 100vh;
        background-image:
            radial-gradient(ellipse at 20% 20%, rgba(30, 86, 176, 0.15) 0%, transparent 60%),
            radial-gradient(ellipse at 80% 80%, rgba(106, 180, 212, 0.1) 0%, transparent 60%);
    }

    nav {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 20px 40px;
        background: rgba(10, 22, 40, 0.8);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid rgba(106, 180, 212, 0.2);
        position: sticky;
        top: 0;
        z-index: 100;
    }

    .nav-brand {
        font-family: 'Playfair Display', serif;
        font-size: 1.3em;
        font-weight: 700;
        color: var(--ice-blue);
        letter-spacing: 0.02em;
    }

    .nav-brand span { color: var(--white); }
    .nav-links { display: flex; align-items: center; gap: 8px; }

    .nav-link {
        color: var(--text-dim);
        text-decoration: none;
        font-size: 0.9em;
        font-weight: 500;
        padding: 6px 14px;
        border-radius: 20px;
        transition: all 0.2s ease;
        letter-spacing: 0.03em;
    }

    .nav-link:hover { color: var(--white); background: rgba(106, 180, 212, 0.15); }
    .nav-user { color: var(--ice-blue); font-size: 0.9em; padding: 6px 14px; font-weight: 500; }

    .page {
        max-width: 1100px;
        margin: 0 auto;
        padding: 50px 40px;
        animation: fadeIn 0.4s ease;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }

    h1 {
        font-family: 'Playfair Display', serif;
        font-size: 2.8em;
        font-weight: 900;
        color: var(--white);
        margin-bottom: 8px;
        line-height: 1.1;
    }

    h2 { font-family: 'Playfair Display', serif; font-size: 1.8em; color: var(--white); margin-bottom: 24px; }
    h3 { font-family: 'Playfair Display', serif; font-size: 1.2em; color: var(--ice-blue); margin-bottom: 12px; }

    .subtitle { color: var(--text-dim); font-size: 1em; margin-bottom: 36px; font-weight: 300; }

    .controls { display: flex; gap: 12px; margin-bottom: 28px; flex-wrap: wrap; align-items: center; }

    select, input[type=text], input[type=password] {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(106, 180, 212, 0.25);
        color: var(--text);
        padding: 10px 16px;
        border-radius: 8px;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.9em;
        outline: none;
        transition: border-color 0.2s;
        min-width: 160px;
    }

    select:focus, input:focus { border-color: var(--ice-blue); }
    select option { background: var(--navy); }

    button, .btn {
        background: var(--blue);
        color: white;
        border: none;
        padding: 10px 22px;
        border-radius: 8px;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.9em;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        text-decoration: none;
        display: inline-block;
        letter-spacing: 0.02em;
    }

    button:hover, .btn:hover { background: var(--ice-blue); color: var(--deep-navy); transform: translateY(-1px); }

    .btn-outline {
        background: transparent;
        border: 1px solid rgba(106, 180, 212, 0.4);
        color: var(--ice-blue);
    }

    .btn-outline:hover { background: rgba(106, 180, 212, 0.15); color: var(--white); }

    .card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 14px;
        overflow: hidden;
        margin-bottom: 24px;
    }

    table { width: 100%; border-collapse: collapse; }
    thead tr { background: rgba(106, 180, 212, 0.12); }

    th {
        padding: 14px 18px;
        text-align: left;
        font-size: 0.78em;
        font-weight: 500;
        color: var(--ice-blue);
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-bottom: 1px solid rgba(106, 180, 212, 0.15);
    }

    td {
        padding: 13px 18px;
        font-size: 0.92em;
        border-bottom: 1px solid rgba(255,255,255,0.04);
        color: var(--text);
    }

    tbody tr:last-child td { border-bottom: none; }
    tbody tr:hover { background: rgba(106, 180, 212, 0.06); }

    .segment-header td {
        background: rgba(30, 86, 176, 0.25);
        color: var(--ice-blue);
        font-size: 0.8em;
        font-weight: 500;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        padding: 10px 18px;
    }

    .place-1 td:first-child { color: var(--gold); font-weight: 700; }
    .place-2 td:first-child { color: #c0c0c0; font-weight: 600; }
    .place-3 td:first-child { color: #cd7f32; font-weight: 600; }

    .total-row td {
        background: rgba(106, 180, 212, 0.08);
        font-weight: 600;
        color: var(--ice-blue);
        border-top: 1px solid rgba(106, 180, 212, 0.2);
    }

    .budget-counter {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.2);
        border-radius: 10px;
        padding: 12px 20px;
        margin-bottom: 28px;
        font-size: 1em;
        font-weight: 500;
        color: var(--text-dim);
    }

    #budget-used { font-family: 'Playfair Display', serif; font-size: 1.4em; font-weight: 700; color: var(--ice-blue); }
    #budget-used.over-budget { color: #ff6b6b; }
    #budget-used.ok-budget { color: #6bffb8; }

    .draft-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }

    .draft-section {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 14px;
        padding: 20px;
    }

    .filters { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
    .filters select, .filters input { min-width: 0; flex: 1; font-size: 0.82em; padding: 7px 10px; }

    .skater-select {
        width: 100%;
        border-radius: 8px;
        border: 1px solid rgba(106, 180, 212, 0.2);
        padding: 6px;
        background: rgba(10, 22, 40, 0.6);
        color: var(--text);
        font-family: 'DM Sans', sans-serif;
        font-size: 0.88em;
    }

    .auth-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 16px;
        padding: 36px;
        max-width: 380px;
    }

    .auth-card input { display: block; width: 100%; margin-bottom: 14px; }
    .auth-card .btn { width: 100%; text-align: center; padding: 12px; }

    .auth-link { display: block; margin-top: 16px; color: var(--text-dim); font-size: 0.88em; text-decoration: none; text-align: center; }
    .auth-link:hover { color: var(--ice-blue); }

    .error { color: #ff6b6b; font-size: 0.88em; margin-bottom: 14px; }

    .leaderboard-rank { font-family: 'Playfair Display', serif; font-size: 1.1em; font-weight: 700; color: var(--text-dim); }
    .rank-1 { color: var(--gold); }
    .rank-2 { color: #c0c0c0; }
    .rank-3 { color: #cd7f32; }

    .cost-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.78em;
        font-weight: 600;
        background: rgba(106, 180, 212, 0.15);
        color: var(--ice-blue);
    }

    .no-data { color: var(--text-dim); text-align: center; padding: 40px; font-size: 0.95em; }

    /* LANDING PAGE */
    .hero {
        text-align: center;
        padding: 80px 40px 60px;
        position: relative;
    }

    .hero-eyebrow {
        font-size: 0.85em;
        font-weight: 500;
        color: var(--ice-blue);
        letter-spacing: 0.15em;
        text-transform: uppercase;
        margin-bottom: 20px;
    }

    .hero h1 {
        font-size: 4em;
        line-height: 1.05;
        margin-bottom: 20px;
        background: linear-gradient(135deg, var(--white) 40%, var(--ice-blue) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .hero-sub {
        font-size: 1.15em;
        color: var(--text-dim);
        max-width: 520px;
        margin: 0 auto 36px;
        line-height: 1.7;
        font-weight: 300;
    }

    .hero-cta { display: flex; gap: 14px; justify-content: center; flex-wrap: wrap; }
    .btn-large { padding: 14px 32px; font-size: 1em; border-radius: 10px; }

    .stats-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin: 50px 40px;
    }

    .stat-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 14px;
        padding: 28px;
        text-align: center;
        transition: border-color 0.2s;
    }

    .stat-card:hover { border-color: rgba(106, 180, 212, 0.4); }

    .stat-number {
        font-family: 'Playfair Display', serif;
        font-size: 2.8em;
        font-weight: 900;
        color: var(--ice-blue);
        line-height: 1;
        margin-bottom: 8px;
    }

    .stat-label { color: var(--text-dim); font-size: 0.88em; font-weight: 400; letter-spacing: 0.04em; }

    .section { padding: 10px 40px 50px; max-width: 1100px; margin: 0 auto; }
    .section-title { font-family: 'Playfair Display', serif; font-size: 1.6em; color: var(--white); margin-bottom: 6px; }
    .section-sub { color: var(--text-dim); font-size: 0.9em; margin-bottom: 24px; }

    .how-it-works {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        margin-top: 10px;
    }

    .step-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 14px;
        padding: 28px;
        position: relative;
    }

    .step-number {
        font-family: 'Playfair Display', serif;
        font-size: 3em;
        font-weight: 900;
        color: rgba(106, 180, 212, 0.15);
        line-height: 1;
        margin-bottom: 12px;
    }

    .step-title { font-weight: 600; color: var(--white); margin-bottom: 8px; font-size: 1em; }
    .step-desc { color: var(--text-dim); font-size: 0.88em; line-height: 1.6; }

    .recent-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
    }

    .recent-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 14px;
        overflow: hidden;
    }

    .recent-card-header {
        background: rgba(106, 180, 212, 0.1);
        padding: 12px 18px;
        font-size: 0.8em;
        font-weight: 500;
        color: var(--ice-blue);
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border-bottom: 1px solid rgba(106, 180, 212, 0.15);
    }

    .recent-card table { width: 100%; }
    .recent-card td { padding: 10px 18px; font-size: 0.88em; border-bottom: 1px solid rgba(255,255,255,0.04); }
    .recent-card tr:last-child td { border-bottom: none; }
</style>
"""

@app.route("/")
def landing():
    user_id, username = current_user()
    skater_count, comp_count, user_count, latest_comp = get_stats()
    recent_results, latest_comp_name = get_latest_results()

    # Group recent results by category
    by_cat = {}
    for row in recent_results:
        cat = row[0]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(row)

    recent_cards = ""
    medals = ["🥇", "🥈", "🥉"]
    for cat, rows in by_cat.items():
        rows_html = "".join([
            f'<tr><td>{medals[i] if i < 3 else ""}</td><td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td></tr>'
            for i, r in enumerate(rows)
        ])
        recent_cards += f"""
        <div class="recent-card">
            <div class="recent-card-header">{cat}</div>
            <table><tbody>{rows_html}</tbody></table>
        </div>
        """

    if user_id:
        cta = f"""
        <a href="/draft" class="btn btn-large">Edit My Team</a>
        <a href="/leaderboard" class="btn btn-large btn-outline">Leaderboard</a>
        """
    else:
        cta = f"""
        <a href="/register" class="btn btn-large">Get Started</a>
        <a href="/login" class="btn btn-large btn-outline">Log In</a>
        """

    return f"""<!DOCTYPE html><html><head><title>Fantasy Figure Skating</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    {STYLE}</head>
    <body>{nav(user_id, username)}

    <div class="hero">
        <div class="hero-eyebrow">⛸ The 2025–26 Season is Live</div>
        <h1>Fantasy Figure<br>Skating</h1>
        <p class="hero-sub">Draft your team of elite figure skaters, earn points from real ISU competition results, and compete against friends all season long.</p>
        <div class="hero-cta">{cta}</div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{skater_count}</div>
            <div class="stat-label">Draftable Skaters</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{comp_count}</div>
            <div class="stat-label">Competitions Tracked</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{user_count}</div>
            <div class="stat-label">Leagues Members</div>
        </div>
    </div>

    <div class="section">
        <div class="section-title">How It Works</div>
        <div class="section-sub">Build your dream team in three simple steps</div>
        <div class="how-it-works">
            <div class="step-card">
                <div class="step-number">01</div>
                <div class="step-title">Create an Account</div>
                <div class="step-desc">Register for free and join the league. Invite friends to compete against you all season.</div>
            </div>
            <div class="step-card">
                <div class="step-number">02</div>
                <div class="step-title">Draft Your Team</div>
                <div class="step-desc">Pick one skater from each discipline — Men, Women, Pairs, and Ice Dance — within your 130 point budget.</div>
            </div>
            <div class="step-card">
                <div class="step-number">03</div>
                <div class="step-title">Earn Points</div>
                <div class="step-desc">Your skaters earn fantasy points based on their real ISU competition scores and placements throughout the season.</div>
            </div>
        </div>
    </div>

    <div class="section">
        <div class="section-title">Latest Results</div>
        <div class="section-sub">{latest_comp_name}</div>
        <div class="recent-grid">{recent_cards}</div>
        <br>
        <a href="/results" class="btn btn-outline">View All Results</a>
    </div>

    </body></html>"""

@app.route("/results")
def results():
    user_id, username = current_user()
    competitions = get_competitions()
    selected_comp = request.args.get("competition", competitions[0])
    selected_cat = request.args.get("category", "Men")
    results = get_results(selected_comp, selected_cat)

    comp_options = "".join([
        f'<option value="{c}" {"selected" if c == selected_comp else ""}>{c}</option>'
        for c in competitions
    ])
    cat_options = "".join([
        f'<option value="{c}" {"selected" if c == selected_cat else ""}>{c}</option>'
        for c in ["Men", "Women", "Pairs", "Ice Dance"]
    ])

    rows_html = ""
    current_segment = None
    for row in results:
        segment, place, name, nation, score = row
        if segment != current_segment:
            current_segment = segment
            rows_html += f'<tr class="segment-header"><td colspan="4">{segment}</td></tr>'
        place_class = f"place-{place}" if place <= 3 else ""
        rows_html += f'<tr class="{place_class}"><td>{place}</td><td>{name}</td><td>{nation}</td><td>{score}</td></tr>'

    return f"""<!DOCTYPE html><html><head><title>Results</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    {STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Competition Results</h1>
        <p class="subtitle">Live scores from ISU competitions worldwide</p>
        <form method="get" class="controls">
            <select name="competition">{comp_options}</select>
            <select name="category">{cat_options}</select>
            <button type="submit">View</button>
        </form>
        <div class="card">
            <table>
                <thead><tr><th>Place</th><th>Skater</th><th>Nation</th><th>Score</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>
    </body></html>"""

@app.route("/register", methods=["GET", "POST"])
def register():
    user_id, username = current_user()
    error = ""
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()
        if not uname or not pwd:
            error = "Please enter a username and password."
        else:
            conn = get_db()
            try:
                conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                    (uname, generate_password_hash(pwd)))
                conn.commit()
                user = conn.execute("SELECT id FROM users WHERE username=?", (uname,)).fetchone()
                session["user_id"] = user[0]
                session["username"] = uname
                conn.close()
                return redirect("/draft")
            except sqlite3.IntegrityError:
                error = "Username already taken."
            conn.close()

    return f"""<!DOCTYPE html><html><head><title>Register</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Join the League</h1>
        <p class="subtitle">Create your account to start drafting</p>
        <div class="auth-card">
            <p class="error">{error}</p>
            <form method="post">
                <input type="text" name="username" placeholder="Username">
                <input type="password" name="password" placeholder="Password">
                <button type="submit" class="btn">Create Account</button>
            </form>
            <a href="/login" class="auth-link">Already have an account? Log in</a>
        </div>
    </div>
    </body></html>"""

@app.route("/login", methods=["GET", "POST"])
def login():
    user_id, username = current_user()
    error = ""
    if request.method == "POST":
        uname = request.form.get("username", "").strip()
        pwd = request.form.get("password", "").strip()
        conn = get_db()
        user = conn.execute("SELECT id, password FROM users WHERE username=?", (uname,)).fetchone()
        conn.close()
        if user and check_password_hash(user[1], pwd):
            session["user_id"] = user[0]
            session["username"] = uname
            return redirect("/team")
        else:
            error = "Invalid username or password."

    return f"""<!DOCTYPE html><html><head><title>Log In</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Welcome Back</h1>
        <p class="subtitle">Log in to manage your team</p>
        <div class="auth-card">
            <p class="error">{error}</p>
            <form method="post">
                <input type="text" name="username" placeholder="Username">
                <input type="password" name="password" placeholder="Password">
                <button type="submit" class="btn">Log In</button>
            </form>
            <a href="/register" class="auth-link">Don't have an account? Register</a>
        </div>
    </div>
    </body></html>"""

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/roster")
def roster():
    user_id, username = current_user()
    skaters = get_all_skaters()
    selected_cat = request.args.get("category", "Men")
    cat_options = "".join([
        f'<option value="{c}" {"selected" if c == selected_cat else ""}>{c}</option>'
        for c in ["Men", "Women", "Pairs", "Ice Dance"]
    ])
    rows_html = "".join([
        f'<tr><td>{name}</td><td>{nation}</td><td>{best_score or "—"}</td><td><span class="cost-badge">{cost} pts</span></td></tr>'
        for name, nation, category, best_score, cost in skaters if category == selected_cat and best_score and best_score > 0
    ])
    return f"""<!DOCTYPE html><html><head><title>Skater Roster</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Skater Roster</h1>
        <p class="subtitle">All eligible skaters and their draft costs</p>
        <form method="get" class="controls">
            <select name="category">{cat_options}</select>
            <button type="submit">Filter</button>
        </form>
        <div class="card">
            <table>
                <thead><tr><th>Name</th><th>Nation</th><th>Best Free Score</th><th>Cost</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>
    </body></html>"""

@app.route("/draft", methods=["GET", "POST"])
def draft():
    user_id, username = current_user()
    if not user_id:
        return redirect("/login")

    if request.method == "POST":
        picks = {}
        total_cost = 0
        conn = get_db()
        for category in ["Men", "Women", "Pairs", "Ice Dance"]:
            pick = request.form.get(category)
            if pick:
                name, nation = pick.split("|", 1)
                row = conn.execute("SELECT cost FROM skater_costs WHERE name=?", (name,)).fetchone()
                cost = row[0] if row else 0
                total_cost += cost
                picks[category] = (name, nation)

        if total_cost > 130:
            conn.close()
            return redirect("/draft?error=1")

        for category, (name, nation) in picks.items():
            conn.execute("INSERT OR REPLACE INTO team VALUES (?, ?, ?, ?)", (user_id, category, name, nation))
        conn.commit()
        conn.close()
        return redirect("/team")

    skaters = get_all_skaters()
    error = request.args.get("error")
    error_html = '<p class="error">Over budget! Your team cannot exceed 130 points.</p>' if error else ""

    cost_lookup = {}
    nations_by_cat = {cat: set() for cat in ["Men", "Women", "Pairs", "Ice Dance"]}
    for name, nation, cat, best_score, cost in skaters:
        cost_lookup[f"{name}|{nation}"] = cost
        nations_by_cat[cat].add(nation)

    cost_json = json.dumps(cost_lookup)
    skater_data = {}
    for cat in ["Men", "Women", "Pairs", "Ice Dance"]:
        skater_data[cat] = [
            {"name": name, "nation": nation, "cost": cost, "value": f"{name}|{nation}"}
            for name, nation, c, best_score, cost in skaters if c == cat
        ]
    skater_json = json.dumps(skater_data)

    sections_html = ""
    for category in ["Men", "Women", "Pairs", "Ice Dance"]:
        nations = sorted(nations_by_cat[category])
        nation_options = '<option value="">All Nations</option>' + "".join(
            f'<option value="{n}">{n}</option>' for n in nations
        )
        sections_html += f"""
        <div class="draft-section">
            <h3>{category}</h3>
            <div class="filters">
                <input type="text" id="search-{category}" placeholder="Search..." oninput="filterSkaters('{category}')">
                <select id="nation-{category}" onchange="filterSkaters('{category}')">
                    {nation_options}
                </select>
                <select id="cost-{category}" onchange="filterSkaters('{category}')">
                    <option value="">All Costs</option>
                    <option value="40">40 pts</option>
                    <option value="30">30 pts</option>
                    <option value="20">20 pts</option>
                    <option value="10">10 pts</option>
                </select>
            </div>
            <select name="{category}" id="select-{category}" onchange="updateBudget()" size="7" class="skater-select"></select>
        </div>
        """

    return f"""<!DOCTYPE html><html><head><title>Draft Team</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Draft Your Team</h1>
        <p class="subtitle">Pick one skater from each discipline within your 130 point budget</p>
        {error_html}
        <div class="budget-counter">
            Budget used: <span id="budget-used">0</span> / 130 pts
        </div>
        <form method="post" id="draft-form">
            <div class="draft-grid">{sections_html}</div>
            <button type="submit" class="btn">Save Team</button>
        </form>
    </div>
    <script>
        const costs = {cost_json};
        const skaterData = {skater_json};

        function filterSkaters(cat) {{
            const search = document.getElementById("search-" + cat).value.toLowerCase();
            const nation = document.getElementById("nation-" + cat).value;
            const cost = document.getElementById("cost-" + cat).value;
            const select = document.getElementById("select-" + cat);
            const current = select.value;
            select.innerHTML = "";
            const filtered = skaterData[cat].filter(s =>
                (!search || s.name.toLowerCase().includes(search))
                && (!nation || s.nation === nation)
                && (!cost || s.cost === parseInt(cost))
            );
            for (const s of filtered) {{
                const opt = document.createElement("option");
                opt.value = s.value;
                opt.textContent = s.name + " (" + s.nation + ") — " + s.cost + " pts";
                if (s.value === current) opt.selected = true;
                select.appendChild(opt);
            }}
            updateBudget();
        }}

        function updateBudget() {{
            let total = 0;
            for (const cat of ["Men", "Women", "Pairs", "Ice Dance"]) {{
                const sel = document.getElementById("select-" + cat);
                if (sel && sel.value) total += costs[sel.value] || 0;
            }}
            const el = document.getElementById("budget-used");
            el.textContent = total;
            el.className = total > 130 ? "over-budget" : "ok-budget";
        }}

        for (const cat of ["Men", "Women", "Pairs", "Ice Dance"]) {{
            filterSkaters(cat);
        }}
    </script>
    </body></html>"""

@app.route("/team")
def team():
    user_id, username = current_user()
    if not user_id:
        return redirect("/login")

    picks = get_team(user_id)
    fantasy_points = get_fantasy_points(user_id)
    total_cost = sum(cost or 0 for _, _, _, cost in picks)
    total_fantasy = sum(fantasy_points.get(name, 0) for _, name, _, _ in picks)

    rows_html = "".join([
        f'<tr><td>{category}</td><td>{name}</td><td>{nation}</td><td><span class="cost-badge">{cost or 0} pts</span></td><td>{fantasy_points.get(name, 0)}</td></tr>'
        for category, name, nation, cost in picks
    ])
    if not rows_html:
        rows_html = '<tr><td colspan="5" class="no-data">No picks yet — go to Draft to build your team!</td></tr>'

    return f"""<!DOCTYPE html><html><head><title>My Team</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>{username}'s Team</h1>
        <p class="subtitle">Your fantasy squad and points earned</p>
        <div class="card">
            <table>
                <thead><tr><th>Discipline</th><th>Skater</th><th>Nation</th><th>Cost</th><th>Fantasy Pts</th></tr></thead>
                <tbody>
                    {rows_html}
                    <tr class="total-row">
                        <td colspan="3">Total</td>
                        <td>{total_cost} / 130 pts</td>
                        <td>{total_fantasy} pts</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <a href="/draft" class="btn">Edit Team</a>
    </div>
    </body></html>"""

@app.route("/leaderboard")
def leaderboard():
    user_id, username = current_user()
    conn = get_db()
    users = conn.execute("SELECT id, username FROM users").fetchall()
    conn.close()

    scores = []
    for u in users:
        uid, uname = u[0], u[1]
        fp = get_fantasy_points(uid)
        total = round(sum(fp.values()), 1)
        scores.append((uname, total))

    scores.sort(key=lambda x: x[1], reverse=True)

    rows_html = ""
    for i, (uname, pts) in enumerate(scores):
        rank_class = f"rank-{i+1}" if i < 3 else ""
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else ""
        rows_html += f'<tr><td class="leaderboard-rank {rank_class}">{medal} {i+1}</td><td>{uname}</td><td>{pts}</td></tr>'

    if not rows_html:
        rows_html = '<tr><td colspan="3" class="no-data">No users yet!</td></tr>'

    return f"""<!DOCTYPE html><html><head><title>Leaderboard</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Leaderboard</h1>
        <p class="subtitle">How your team stacks up</p>
        <div class="card">
            <table>
                <thead><tr><th>Rank</th><th>User</th><th>Fantasy Points</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>
    </body></html>"""

app.run(debug=True)