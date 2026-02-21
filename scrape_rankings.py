import requests
from bs4 import BeautifulSoup
import sqlite3

categories = {
    "Men": "https://results.isu.org/ws/ws/wsmen.htm",
    "Women": "https://results.isu.org/ws/ws/wswomen.htm",
    "Pairs": "https://results.isu.org/ws/ws/wspairs.htm",
    "Ice Dance": "https://results.isu.org/ws/ws/wsdance.htm",
}

headers = {"User-Agent": "Mozilla/5.0"}

def normalize_name(name):
    parts = name.strip().split()
    last = [p for p in parts if p.isupper()]
    first = [p for p in parts if not p.isupper()]
    if last and first:
        return " ".join(first) + " " + " ".join(last)
    return name

conn = sqlite3.connect(r"C:\Users\zfam4\OneDrive\Desktop\fantasy-skating\skating.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS world_rankings (
        category TEXT,
        rank INTEGER,
        name TEXT,
        country TEXT,
        points INTEGER,
        PRIMARY KEY (category, name)
    )
""")
cursor.execute("DELETE FROM world_rankings")

for category, url in categories.items():
    print(f"\nScraping {category}...")
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr")

    count = 0
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 4:
            rank = cols[0].text.strip()
            points = cols[1].text.strip()
            name = normalize_name(cols[2].text.strip())
            country = cols[3].text.strip()
            if rank.isdigit() and name:
                cursor.execute("INSERT OR REPLACE INTO world_rankings VALUES (?, ?, ?, ?, ?)",
                    (category, int(rank), name, country, int(points) if points.isdigit() else 0))
                print(f"  {rank}. {name} ({country}) - {points} pts")
                count += 1
    print(f"  Saved {count} skaters")

conn.commit()
conn.close()
print("\nDone!")