# Auto sector monitor (pilot)
Run:  pip install -r requirements.txt && streamlit run app.py
Add data: python load_goose.py data.db new_file.json --country KR --segment carmaker
(re-loading is safe; rows upsert by ticker + metric + period; missing values stay NULL)
Files: db.py (schema), load_goose.py (JSON -> SQLite), app.py (Streamlit + Plotly), data.db (Hyundai Motor pilot, 56 records)
