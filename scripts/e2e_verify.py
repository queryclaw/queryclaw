#!/usr/bin/env python3
"""E2E verification: onboard, SQLite DB, chat (fails without API key)."""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

def main():
    e2e_dir = Path(__file__).resolve().parent / ".e2e_tmp"
    e2e_dir.mkdir(exist_ok=True)
    cfg_path = e2e_dir / "config.json"
    db_path = e2e_dir / "e2e.db"

    # 1. Onboard
    r = subprocess.run(
        ["queryclaw", "onboard", "-c", str(cfg_path)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print("onboard failed:", r.stderr or r.stdout)
        return 1

    # 2. Create SQLite DB with table
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS e2e_demo (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT OR REPLACE INTO e2e_demo VALUES (1, 'test')")
    conn.commit()
    conn.close()

    # 3. Set database path in config
    with open(cfg_path) as f:
        cfg = json.load(f)
    cfg["database"]["database"] = str(db_path)
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)

    # 4. Run chat -m (no API key => expect exit 1 and message)
    r = subprocess.run(
        ["queryclaw", "chat", "-c", str(cfg_path), "-m", "这个数据库有哪些表？", "--no-markdown"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 1:
        print("Expected exit code 1 (no API key); got", r.returncode)
        print("stdout:", r.stdout)
        print("stderr:", r.stderr)
        return 1
    if "No LLM API key" not in r.stdout and "No LLM API key" not in r.stderr:
        print("Expected 'No LLM API key' in output")
        print("stdout:", r.stdout)
        print("stderr:", r.stderr)
        return 1

    print("E2E verification passed: onboard -> SQLite config -> chat fails gracefully without API key.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
