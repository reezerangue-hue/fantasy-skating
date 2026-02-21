import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

scripts = [
    "scraper2.py",
    "scrape_rankings.py",
    "update_costs.py",
]

for script in scripts:
    path = os.path.join(BASE_DIR, script)
    print(f"\n{'='*40}")
    print(f"Running {script}...")
    print('='*40)
    result = subprocess.run([sys.executable, path])
    if result.returncode != 0:
        print(f"ERROR: {script} failed! Stopping.")
        break

print("\nAll done! Database is up to date.")