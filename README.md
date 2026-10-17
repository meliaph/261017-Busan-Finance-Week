# Goose report dashboard

Turns the report ZIPs that the Goose skill produces into an interactive dashboard (Streamlit + Plotly).

- `app.py` – the dashboard (Overview, Financials, Report, Evidence, Trust, Compare)
- `reports/<name>/report.json` – a Goose `input.en.json` (add `delivery-audit.json` next to it for the audit view)
- Light data pulls (8 quarters of revenue, operating profit, net profit) for 10 auto makers/parts firms, plus the full Samsung report
- Add a company: drop its report JSON in a new folder under `reports/`, or upload the ZIP in the sidebar
- `pilot_app.py`, `db.py`, `load_goose.py`, `data.db` – earlier SQLite pilot (Hyundai Motor), kept for reference

Run locally: `pip install -r requirements.txt` then `streamlit run app.py`
