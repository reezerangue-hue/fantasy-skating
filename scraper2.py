import requests
from bs4 import BeautifulSoup
import sqlite3

competitions = list(dict.fromkeys([
    "https://results.isu.org/results/season2526/gpfra2025/",
    "https://results.isu.org/results/season2425/wc2025/",
    "https://results.isu.org/results/season2526/owg2026/",
    "https://results.isu.org/results/season2425/gpusa2024/",
]))

SEGMENT_MAP = {
    1: ("Men", "Short Program"),
    2: ("Men", "Free Skating"),
    3: ("Women", "Short Program"),
    4: ("Women", "Free Skating"),
    5: ("Pairs", "Short Program"),
    6: ("Pairs", "Free Skating"),
    7: ("Ice Dance", "Rhythm Dance"),
    8: ("Ice Dance", "Free Dance"),
}

headers = {"User-Agent": "Mozilla/5.0"}

def normalize_name(name):
    parts = name.strip().split()
    last = [p for p in parts if p.isupper()]
    first = [p for p in parts if not p.isupper()]
    if last and first:
        return " ".join(first) + " " + " ".join(last)
    return name

conn = sqlite3.connect("skating.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS results2")
cursor.execute("""
    CREATE TABLE results2 (
        competition TEXT,
        category TEXT,
        segment TEXT,
        place INTEGER,
        name TEXT,
        nation TEXT,
        score REAL,
        UNIQUE(competition, category, segment, name)
    )
""")

def scrape_segment(comp_url, comp_name, seg_num):
    category, segment = SEGMENT_MAP[seg_num]
    seg_file = f"SEG{seg_num:03d}.htm"
    url = comp_url + seg_file
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return 0
    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr")
    seen = set()
    count = 0
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 4:
            place = cols[0].text.strip()
            name = normalize_name(cols[1].text.strip())
            nation = cols[2].text.strip()
            score = cols[3].text.strip()
            if name and name not in seen and place.isdigit():
                seen.add(name)
                try:
                    cursor.execute("INSERT OR IGNORE INTO results2 VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (comp_name, category, segment, int(place), name, nation, float(score)))
                    print(f"    {place}. {name} - {score}")
                    count += 1
                except ValueError:
                    continue
    return count

for comp_url in competitions:
    print(f"\nScraping {comp_url}...")
    response = requests.get(comp_url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    comp_name = soup.title.text.strip() if soup.title else comp_url

    for seg_num in range(1, 9):
        category, segment = SEGMENT_MAP[seg_num]
        print(f"  Scraping {category} - {segment}...")
        count = scrape_segment(comp_url, comp_name, seg_num)
        print(f"  Saved {count} results")

conn.commit()
conn.close()
print("\nAll done!")