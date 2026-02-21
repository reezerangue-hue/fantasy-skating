import sqlite3

conn = sqlite3.connect(r"C:\Users\zfam4\OneDrive\Desktop\fantasy-skating\skating.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS skater_costs")
cursor.execute("""
    CREATE TABLE skater_costs (
        name TEXT PRIMARY KEY,
        category TEXT,
        nation TEXT,
        best_score REAL,
        cost INTEGER
    )
""")

# Only include skaters above a minimum points threshold per category
THRESHOLDS = {
    "Men": 500,
    "Women": 500,
    "Pairs": 400,
    "Ice Dance": 400,
}

for category in ["Men", "Women", "Pairs", "Ice Dance"]:
    threshold = THRESHOLDS[category]
    cursor.execute("""
        SELECT name, country, rank, points
        FROM world_rankings
        WHERE category=? AND points >= ?
        ORDER BY rank ASC
    """, (category, threshold))
    skaters = cursor.fetchall()

    if not skaters:
        continue

    total = len(skaters)
    print(f"\n{category}: {total} skaters above {threshold} pts threshold")

    for name, country, rank, points in skaters:
        percentile = rank / total
        if percentile <= 0.25:
            cost = 40
        elif percentile <= 0.50:
            cost = 30
        elif percentile <= 0.75:
            cost = 20
        else:
            cost = 10

        cursor.execute("""
            SELECT MAX(score) FROM results2
            WHERE name=? AND segment IN ('Free Skating', 'Free Dance')
        """, (name,))
        row = cursor.fetchone()
        best_score = row[0] if row and row[0] else 0.0

        cursor.execute("INSERT OR REPLACE INTO skater_costs VALUES (?, ?, ?, ?, ?)",
            (name, category, country, best_score, cost))
        print(f"  {rank}. {name} ({points} ranking pts) -> {cost} draft pts")

conn.commit()
conn.close()
print("\nDone! Costs updated.")