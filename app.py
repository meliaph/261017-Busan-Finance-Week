import sqlite3, pandas as pd, plotly.express as px, streamlit as st

DB = "data.db"
st.set_page_config(page_title="Auto sector monitor (pilot)", layout="wide")

@st.cache_data
def load():
    con = sqlite3.connect(DB)
    f = pd.read_sql("""SELECT f.*, c.name, s.title AS source_title, s.url AS source_url,
        s.published_at FROM facts f JOIN companies c USING(ticker)
        LEFT JOIN sources s USING(source_id)""", con)
    return f

f = load()
LABEL = {"revenue": "Revenue", "operating_profit": "Operating profit", "net_income": "Net income",
         "operating_cash_flow": "Operating cash flow", "capex": "Capex",
         "total_debt": "Total debt", "cash": "Cash"}
TN = 10_000   # 1 trillion won = 10,000 x 100 million won (억원)

st.title("Auto & auto parts monitor · pilot")
st.caption("Historical, frozen dataset. Values are in KRW trillion (조원), converted from the "
           "original unit 억원 (KRW 100 million). Missing values are blank, never zero.")

names = sorted(f["name"].unique())
sel = st.sidebar.multiselect("Companies", names, default=names)
d = f[f["name"].isin(sel)].copy()
d["value_tn"] = d["value"] / TN
periods = sorted(d["period"].unique())

tab1, tab2, tab3 = st.tabs(["Trends", "Margins", "Data trust"])

with tab1:
    metric = st.selectbox("Metric", [m for m in LABEL if m in d["metric"].unique()],
                          format_func=LABEL.get)
    m = d[d["metric"] == metric]
    if m["value"].notna().any():
        fig = px.bar(m, x="period", y="value_tn", color="name", barmode="group",
                     category_orders={"period": periods},
                     labels={"value_tn": "KRW trillion (조원)", "period": "Quarter", "name": ""})
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No verified values for this metric yet.")
    st.dataframe(m.pivot_table(index="period", columns="name", values="value_tn")
                 .round(3), width="stretch")

with tab2:
    w = d.pivot_table(index=["name", "period"], columns="metric", values="value").reset_index()
    if {"revenue", "operating_profit", "net_income"} <= set(w.columns):
        w["Operating margin (%)"] = w["operating_profit"] / w["revenue"] * 100
        w["Net margin (%)"] = w["net_income"] / w["revenue"] * 100
        mm = st.radio("Margin", ["Operating margin (%)", "Net margin (%)"], horizontal=True)
        fig = px.line(w, x="period", y=mm, color="name", markers=True,
                      category_orders={"period": periods})
        st.plotly_chart(fig, width="stretch")
        st.caption("Net income includes non-controlling interests. "
                   "Preliminary (잠정) results from company releases.")
    else:
        st.info("Revenue, operating profit and net income are needed for margins.")

with tab3:
    tot = len(d); ver = int((d["status"] == "verified").sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Records", tot); c2.metric("Verified", ver); c3.metric("Unverified / missing", tot - ver)
    cov = (d.assign(ok=d["status"].eq("verified"))
             .pivot_table(index="metric", columns="name", values="ok", aggfunc="mean") * 100).round(0)
    st.subheader("Verified coverage by metric (%)")
    st.dataframe(cov, width="stretch")
    st.subheader("Sources")
    src = (d.dropna(subset=["source_title"])
             .groupby(["source_title", "source_url", "published_at"], dropna=False)
             .size().reset_index(name="records"))
    st.dataframe(src, width="stretch", hide_index=True)
    with st.expander("Unverified records"):
        st.dataframe(d[d["status"] != "verified"][["name", "metric", "period", "source_title"]],
                     width="stretch", hide_index=True)
