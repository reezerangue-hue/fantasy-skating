from flask import Flask, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os

app = Flask(__name__)
app.secret_key = "hdlgeigleygrrei7485794egey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "skating.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

_ISU_TO_ALPHA2 = {
    'ARM': 'AM', 'AUS': 'AU', 'AUT': 'AT', 'AZE': 'AZ', 'BEL': 'BE',
    'BUL': 'BG', 'CAN': 'CA', 'CHN': 'CN', 'CZE': 'CZ', 'ESP': 'ES',
    'EST': 'EE', 'FIN': 'FI', 'FRA': 'FR', 'GBR': 'GB', 'GEO': 'GE',
    'GER': 'DE', 'HUN': 'HU', 'ISR': 'IL', 'ITA': 'IT', 'JPN': 'JP',
    'KAZ': 'KZ', 'KOR': 'KR', 'LAT': 'LV', 'LTU': 'LT', 'MEX': 'MX',
    'NED': 'NL', 'POL': 'PL', 'ROU': 'RO', 'SUI': 'CH', 'SVK': 'SK',
    'SWE': 'SE', 'TPE': 'TW', 'UKR': 'UA', 'USA': 'US', 'UZB': 'UZ',
}

def flag(code):
    alpha2 = _ISU_TO_ALPHA2.get(code)
    if not alpha2:
        return code
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in alpha2)

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
    latest = conn.execute("SELECT competition FROM results2 ORDER BY rowid DESC LIMIT 1").fetchone()
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
<meta charset="utf-8">
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

    .btn-small {
        padding: 5px 12px;
        font-size: 0.8em;
        border-radius: 6px;
    }

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

    .draft-section {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(106, 180, 212, 0.15);
        border-radius: 14px;
        padding: 24px;
        margin-bottom: 24px;
        max-width: 600px;
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

    .swap-info {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        background: rgba(106, 180, 212, 0.08);
        border: 1px solid rgba(106, 180, 212, 0.2);
        border-radius: 10px;
        padding: 12px 20px;
        margin-bottom: 20px;
        font-size: 0.95em;
        color: var(--text-dim);
    }

    .swap-count { font-family: 'Playfair Display', serif; font-size: 1.3em; font-weight: 700; color: var(--ice-blue); }
    .swap-count.low { color: #ffaa6b; }
    .swap-count.none { color: #ff6b6b; }

    .current-pick {
        background: rgba(106, 180, 212, 0.08);
        border: 1px solid rgba(106, 180, 212, 0.2);
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 20px;
        font-size: 0.95em;
        color: var(--text-dim);
    }

    .current-pick strong { color: var(--white); }

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
            f'<tr><td>{medals[i] if i < 3 else ""}</td><td>{r[2]}</td><td>{flag(r[3])}</td><td>{r[4]}</td></tr>'
            for i, r in enumerate(rows)
        ])
        recent_cards += f"""
        <div class="recent-card">
            <div class="recent-card-header">{cat}</div>
            <table><tbody>{rows_html}</tbody></table>
        </div>
        """

    if user_id:
        cta = """
        <a href="/team" class="btn btn-large">My Team</a>
        <a href="/leaderboard" class="btn btn-large btn-outline">Leaderboard</a>
        """
    else:
        cta = """
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
            <div class="stat-label">League Members</div>
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
        rows_html += f'<tr class="{place_class}"><td>{place}</td><td><a href="/skater/{name}" style="color:inherit;text-decoration:none;" onmouseover="this.style.color=\'var(--ice-blue)\'" onmouseout="this.style.color=\'\'">{name}</a></td><td>{flag(nation)}</td><td>{score}</td></tr>'

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
                return redirect("/draft/Men")
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
        f'<tr><td><a href="/skater/{name}" style="color:var(--text);text-decoration:none;" onmouseover="this.style.color=\'var(--ice-blue)\'" onmouseout="this.style.color=\'var(--text)\'">{name}</a></td><td>{flag(nation)}</td><td>{best_score or "—"}</td><td><span class="cost-badge">{cost} pts</span></td></tr>'
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

@app.route("/draft")
def draft_home():
    user_id, username = current_user()
    if not user_id:
        return redirect("/login")
    return redirect("/draft/Men")

@app.route("/draft/<category>", methods=["GET", "POST"])
def draft(category):
    user_id, username = current_user()
    if not user_id:
        return redirect("/login")

    valid_categories = ["Men", "Women", "Pairs", "Ice Dance"]
    if category not in valid_categories:
        return redirect("/draft/Men")

    conn = get_db()
    user = conn.execute("SELECT swaps_remaining, has_drafted FROM users WHERE id=?", (user_id,)).fetchone()
    swaps = user[0] if user[0] is not None else 3
    has_drafted = user[1] if user[1] is not None else 0

    # Get current pick for this category
    current = conn.execute("SELECT name, nation FROM team WHERE user_id=? AND category=?", (user_id, category)).fetchone()
    current_name = current[0] if current else None
    current_nation = current[1] if current else None
    conn.close()

    if has_drafted and swaps <= 0:
        return f"""<!DOCTYPE html><html><head><title>Team Locked</title>{STYLE}</head>
        <body>{nav(user_id, username)}
        <div class="page">
            <h1>Team Locked</h1>
            <p class="subtitle">You have used all 3 of your swaps for this season.</p>
            <a href="/team" class="btn">View My Team</a>
        </div>
        </body></html>"""

    if request.method == "POST":
        pick = request.form.get("pick")
        if not pick:
            return redirect(f"/draft/{category}?error=1")

        name, nation = pick.split("|", 1)

        conn = get_db()

        # Check budget — get costs of other picks plus this one
        other_costs = conn.execute("""
            SELECT COALESCE(SUM(s.cost), 0)
            FROM team t
            LEFT JOIN skater_costs s ON t.name = s.name
            WHERE t.user_id=? AND t.category != ?
        """, (user_id, category)).fetchone()[0]

        this_cost = conn.execute("SELECT cost FROM skater_costs WHERE name=?", (name,)).fetchone()
        this_cost = this_cost[0] if this_cost else 0

        if other_costs + this_cost > 130:
            conn.close()
            return redirect(f"/draft/{category}?error=1")

        conn.execute("INSERT OR REPLACE INTO team VALUES (?, ?, ?, ?)", (user_id, category, name, nation))

        if has_drafted:
            conn.execute("UPDATE users SET swaps_remaining = swaps_remaining - 1 WHERE id=?", (user_id,))
        else:
            # Check if all 4 categories are now picked — if so mark as drafted
            picks_count = conn.execute("SELECT COUNT(*) FROM team WHERE user_id=?", (user_id,)).fetchone()[0]
            if picks_count >= 4:
                conn.execute("UPDATE users SET has_drafted = 1 WHERE id=?", (user_id,))

        conn.commit()
        conn.close()
        return redirect("/team")

    error_html = '<p class="error">Over budget! This pick would exceed your 130 point budget.</p>' if request.args.get("error") else ""

    if not has_drafted:
        swap_html = '<div class="swap-info">🎉 Initial draft — no swaps will be used!</div>'
    else:
        swap_color = "none" if swaps == 1 else "low" if swaps == 2 else ""
        swap_html = f'<div class="swap-info">⚡ Swaps remaining: <span class="swap-count {swap_color}">{swaps}</span> / 3 &nbsp;—&nbsp; saving will use 1 swap</div>'

    current_html = f'<div class="current-pick">Current pick: <strong>{current_name} {flag(current_nation)}</strong></div>' if current_name else '<div class="current-pick">No pick yet for this discipline.</div>'

    skaters = get_all_skaters()
    cost_lookup = {}
    nations = set()
    skater_list = []
    for name, nation, cat, best_score, cost in skaters:
        if cat == category:
            cost_lookup[f"{name}|{nation}"] = cost
            nations.add(nation)
            skater_list.append({"name": name, "nation": nation, "flag": flag(nation), "cost": cost, "value": f"{name}|{nation}"})

    cost_json = json.dumps(cost_lookup)
    skater_json = json.dumps(skater_list)
    current_value = f"{current_name}|{current_nation}" if current_name else ""

    nation_options = '<option value="">All Nations</option>' + "".join(
        f'<option value="{n}">{n}</option>' for n in sorted(nations)
    )

    return f"""<!DOCTYPE html><html><head><title>Draft {category}</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>Edit {category}</h1>
        <p class="subtitle">Choose your {category} skater</p>
        {swap_html}
        {current_html}
        {error_html}
        <div class="draft-section">
            <div class="filters">
                <input type="text" id="search" placeholder="Search name..." oninput="filterSkaters()">
                <select id="nation-filter" onchange="filterSkaters()">{nation_options}</select>
                <select id="cost-filter" onchange="filterSkaters()">
                    <option value="">All Costs</option>
                    <option value="40">40 pts</option>
                    <option value="30">30 pts</option>
                    <option value="20">20 pts</option>
                    <option value="10">10 pts</option>
                </select>
            </div>
            <form method="post">
                <select name="pick" id="skater-select" size="10" class="skater-select" style="margin-bottom:16px;"></select>
                <br>
                <button type="submit" class="btn">Save Pick</button>
                <a href="/team" class="btn btn-outline" style="margin-left:10px;">Cancel</a>
            </form>
        </div>
    </div>
    <script>
        const costs = {cost_json};
        const skaterData = {skater_json};
        const currentValue = "{current_value}";

        function filterSkaters() {{
            const search = document.getElementById("search").value.toLowerCase();
            const nation = document.getElementById("nation-filter").value;
            const cost = document.getElementById("cost-filter").value;
            const select = document.getElementById("skater-select");
            select.innerHTML = "";

            const filtered = skaterData.filter(s =>
                (!search || s.name.toLowerCase().includes(search))
                && (!nation || s.nation === nation)
                && (!cost || s.cost === parseInt(cost))
            );

            for (const s of filtered) {{
                const opt = document.createElement("option");
                opt.value = s.value;
                opt.textContent = s.flag + " " + s.name + " — " + s.cost + " pts";
                if (s.value === currentValue) opt.selected = true;
                select.appendChild(opt);
            }}
        }}

        filterSkaters();
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

    conn = get_db()
    user = conn.execute("SELECT swaps_remaining, has_drafted FROM users WHERE id=?", (user_id,)).fetchone()
    swaps = user[0] if user[0] is not None else 3
    has_drafted = user[1] if user[1] is not None else 0
    conn.close()

    # Build picks dict for easy lookup
    picks_by_cat = {cat: (name, nation, cost) for cat, name, nation, cost in picks}

    rows_html = ""
    for category in ["Men", "Women", "Pairs", "Ice Dance"]:
        if category in picks_by_cat:
            name, nation, cost = picks_by_cat[category]
            pts = fantasy_points.get(name, 0)
            if has_drafted and swaps <= 0:
                edit_btn = '<span style="color:var(--text-dim);font-size:0.8em;">🔒 Locked</span>'
            else:
                edit_btn = f'<a href="/draft/{category}" class="btn btn-small btn-outline">Edit</a>'
            rows_html += f'<tr><td>{category}</td><td>{name}</td><td>{flag(nation)}</td><td><span class="cost-badge">{cost or 0} pts</span></td><td>{pts}</td><td>{edit_btn}</td></tr>'
        else:
            rows_html += f'<tr><td>{category}</td><td colspan="4" style="color:var(--text-dim);">No pick yet</td><td><a href="/draft/{category}" class="btn btn-small">Draft</a></td></tr>'

    if has_drafted and swaps <= 0:
        swap_status = '<p style="color:#ff6b6b;margin-bottom:16px;">🔒 Your team is locked — no swaps remaining.</p>'
    elif has_drafted:
        swap_color = "none" if swaps == 1 else "low" if swaps == 2 else ""
        swap_status = f'<div class="swap-info" style="margin-bottom:20px;">⚡ Swaps remaining: <span class="swap-count {swap_color}">{swaps}</span> / 3</div>'
    else:
        swap_status = '<div class="swap-info" style="margin-bottom:20px;">🎉 Draft your team to get started!</div>'

    return f"""<!DOCTYPE html><html><head><title>My Team</title>{STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <h1>{username}'s Team</h1>
        <p class="subtitle">Your fantasy squad and points earned</p>
        {swap_status}
        <div class="card">
            <table>
                <thead><tr><th>Discipline</th><th>Skater</th><th>Nation</th><th>Cost</th><th>Fantasy Pts</th><th></th></tr></thead>
                <tbody>
                    {rows_html}
                    <tr class="total-row">
                        <td colspan="3">Total</td>
                        <td>{total_cost} / 130 pts</td>
                        <td>{total_fantasy} pts</td>
                        <td></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
    </body></html>"""

@app.route("/skater/<name>")
def skater_profile(name):
    user_id, username = current_user()
    conn = get_db()

    info = conn.execute(
        "SELECT category, nation, best_score, cost FROM skater_costs WHERE name=?", (name,)
    ).fetchone()

    if not info:
        conn.close()
        return f"""<!DOCTYPE html><html><head><title>Skater Not Found</title>{STYLE}</head>
        <body>{nav(user_id, username)}
        <div class="page"><h1>Skater Not Found</h1>
        <p class="subtitle">No data found for "{name}".</p>
        <a href="/roster" class="btn btn-outline">Back to Roster</a>
        </div></body></html>""", 404

    category, nation, best_score, cost = info

    results = conn.execute("""
        SELECT competition, segment, place, score
        FROM results2
        WHERE name=?
        ORDER BY competition, segment
    """, (name,)).fetchall()
    conn.close()

    # Group results by competition
    by_comp = {}
    for comp, segment, place, score in results:
        if comp not in by_comp:
            by_comp[comp] = []
        by_comp[comp].append((segment, place, score))

    comp_count = len(by_comp)
    wins = sum(1 for rows in by_comp.values() for seg, pl, sc in rows if pl == 1 and seg in ("Free Skating", "Free Dance"))
    podiums = sum(1 for rows in by_comp.values() for seg, pl, sc in rows if pl <= 3 and seg in ("Free Skating", "Free Dance"))

    comp_rows = ""
    for comp, rows in by_comp.items():
        for segment, place, score in rows:
            place_class = f"place-{place}" if place <= 3 else ""
            comp_rows += f'<tr class="{place_class}"><td>{comp}</td><td>{segment}</td><td>{place}</td><td>{score}</td></tr>'

    stats_html = f"""
    <div style="display:flex;gap:16px;margin-bottom:32px;flex-wrap:wrap;">
        <div class="stat-card" style="padding:20px 28px;flex:1;min-width:120px;">
            <div class="stat-number" style="font-size:2em;">{cost}</div>
            <div class="stat-label">Draft Cost (pts)</div>
        </div>
        <div class="stat-card" style="padding:20px 28px;flex:1;min-width:120px;">
            <div class="stat-number" style="font-size:2em;">{comp_count}</div>
            <div class="stat-label">Competitions</div>
        </div>
        <div class="stat-card" style="padding:20px 28px;flex:1;min-width:120px;">
            <div class="stat-number" style="font-size:2em;">{wins}</div>
            <div class="stat-label">Wins</div>
        </div>
        <div class="stat-card" style="padding:20px 28px;flex:1;min-width:120px;">
            <div class="stat-number" style="font-size:2em;">{podiums}</div>
            <div class="stat-label">Podiums</div>
        </div>
        <div class="stat-card" style="padding:20px 28px;flex:1;min-width:120px;">
            <div class="stat-number" style="font-size:2em;">{best_score or "—"}</div>
            <div class="stat-label">Best Free Score</div>
        </div>
    </div>"""

    no_results = '<tr><td colspan="4" class="no-data">No competition results found.</td></tr>' if not comp_rows else ""

    return f"""<!DOCTYPE html><html><head><title>{name}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    {STYLE}</head>
    <body>{nav(user_id, username)}
    <div class="page">
        <p class="subtitle" style="margin-bottom:8px;">
            <a href="/roster" style="color:var(--text-dim);text-decoration:none;">Roster</a>
            <span style="color:var(--text-dim);"> / {category}</span>
        </p>
        <h1>{name}</h1>
        <p class="subtitle">{flag(nation)} {nation} &middot; {category}</p>
        {stats_html}
        <h2>Competition Results</h2>
        <div class="card">
            <table>
                <thead><tr><th>Competition</th><th>Segment</th><th>Place</th><th>Score</th></tr></thead>
                <tbody>{comp_rows}{no_results}</tbody>
            </table>
        </div>
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
        <p class="subtitle">How your league stacks up</p>
        <div class="card">
            <table>
                <thead><tr><th>Rank</th><th>User</th><th>Fantasy Points</th></tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>
    </body></html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)