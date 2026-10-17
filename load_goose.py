"""Load Goose JSON arrays into SQLite.
Usage: python load_goose.py data.db file1.json [file2.json ...] [--country KR] [--segment carmaker]
Re-running is safe: rows are upserted by (ticker, metric, period)."""
import argparse, json
from db import connect

ap = argparse.ArgumentParser()
ap.add_argument("db"); ap.add_argument("files", nargs="+")
ap.add_argument("--country"); ap.add_argument("--segment")
a = ap.parse_args()
con = connect(a.db)
n = 0
for f in a.files:
    for r in json.load(open(f, encoding="utf-8")):
        st = r.get("status")
        if st not in ("verified", "unverified"):
            raise SystemExit(f"bad status {st!r} in {f}")
        if r.get("value") is None:
            st = "unverified"            # a missing value can never be 'verified'
        con.execute("""INSERT INTO companies(ticker,name,country,segment,currency) VALUES(?,?,?,?,?)
          ON CONFLICT(ticker) DO UPDATE SET name=excluded.name,
          country=COALESCE(?,country), segment=COALESCE(?,segment)""",
          (r["ticker"], r["company"], a.country, a.segment, r.get("currency"), a.country, a.segment))
        con.execute("""INSERT OR IGNORE INTO sources(title,url,published_at,accessed_at) VALUES(?,?,?,?)""",
          (r.get("source_title"), r.get("source_url") or "", r.get("published_at"), r.get("accessed_at")))
        sid = con.execute("SELECT source_id FROM sources WHERE title IS ? AND url IS ?",
                          (r.get("source_title"), r.get("source_url") or "")).fetchone()[0]
        con.execute("""INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?,?)
          ON CONFLICT(ticker,metric,period) DO UPDATE SET value=excluded.value,
          period_end=excluded.period_end, unit=excluded.unit, currency=excluded.currency,
          basis=excluded.basis, source_id=excluded.source_id, status=excluded.status""",
          (r["ticker"], r["metric"], r["period"], r.get("period_end"), r.get("value"),
           r.get("unit"), r.get("currency"), r.get("basis"), sid, st))
        n += 1
con.commit()
print(f"loaded {n} records into {a.db}")
