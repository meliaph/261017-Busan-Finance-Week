import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies(
  ticker TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT, segment TEXT, currency TEXT);
CREATE TABLE IF NOT EXISTS sources(
  source_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, url TEXT,
  published_at TEXT, accessed_at TEXT, UNIQUE(title, url));
CREATE TABLE IF NOT EXISTS facts(
  ticker TEXT NOT NULL REFERENCES companies(ticker),
  metric TEXT NOT NULL, period TEXT NOT NULL, period_end TEXT,
  value REAL,                      -- NULL = not verified (never 0)
  unit TEXT, currency TEXT, basis TEXT,
  source_id INTEGER REFERENCES sources(source_id),
  status TEXT NOT NULL CHECK(status IN ('verified','unverified')),
  PRIMARY KEY(ticker, metric, period));
"""

def connect(path="data.db"):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con
