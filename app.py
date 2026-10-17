"""Goose report dashboard: turns Goose report-input.json files into an interactive view.
Reports live in reports/<name>/report.json (optionally delivery-audit.json). You can also upload a Goose ZIP."""
import io, json, zipfile
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Goose report dashboard", layout="wide")
ROOT = Path(__file__).parent / "reports"
NAMES = ("input.en.json", "report-input.json", "input.json", "report.json")
STATUS_COLOR = {"filed": "#4C78A8", "derived": "#9ECAE9", "preliminary": "#E45756"}
BADGE = {"verified": "🟢", "supported": "🟢", "qualified": "🟡", "inference": "🔵", "unverified": "🔴",
         "unresolved": "🔴", "contradicted": "🔴", "read": "🟢", "direct_read": "🟢", "blocked": "🔴",
         "pass": "🟢", "revise": "🟡", "limited": "🟡", "pending": "⚪", "partial": "🟡", "ok": "🟢"}


def b(s):
    return f"{BADGE.get(str(s).lower(), '⚪')} {s}"


def pick(files):
    for n in NAMES:
        for k in files:
            if k.split("/")[-1] == n:
                return k
    return None


@st.cache_data
def load_folder():
    out = {}
    for d in sorted(ROOT.glob("*/")):
        f = {p.name: p.read_bytes() for p in d.glob("*.json")}
        k = pick(f)
        if k:
            out[d.name] = (json.loads(f[k]), json.loads(f["delivery-audit.json"]) if "delivery-audit.json" in f else None)
    return out


def load_zip(data):
    z = zipfile.ZipFile(io.BytesIO(data))
    f = {n: z.read(n) for n in z.namelist() if n.endswith(".json")}
    k = pick(f)
    if not k:
        return None
    aud = next((n for n in f if n.endswith("delivery-audit.json")), None)
    return json.loads(f[k]), (json.loads(f[aud]) if aud else None)


reports = dict(load_folder())
with st.sidebar:
    st.header("Reports")
    up = st.file_uploader("Add a Goose ZIP or JSON", type=["zip", "json"])
    if up:
        try:
            r = load_zip(up.getvalue()) if up.name.endswith(".zip") else (json.loads(up.getvalue()), None)
            if r:
                reports[f"upload: {up.name}"] = r
            else:
                st.error("No report JSON found in the ZIP.")
        except Exception as e:
            st.error(f"Could not read the file: {e}")
if not reports:
    st.info("No reports yet. Upload a Goose ZIP in the sidebar, or add one under reports/.")
    st.stop()


def label(k):
    c = reports[k][0].get("company", {})
    return f"{c.get('name', k)} ({c.get('ticker', '')}) · {reports[k][0].get('as_of', '')}"


key = st.sidebar.selectbox("Report", list(reports), format_func=label)
R, AUD = reports[key]
co = R.get("company", {})
src = {s["id"]: s for s in R.get("sources", [])}


def quarters_df(rep):
    fh = rep.get("financial_history", {})
    rows = list(fh.get("quarters", [])) + list(fh.get("preliminary", []))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ("revenue", "operating_profit", "net_profit"):
        if c not in df:
            df[c] = None
    df["op_margin"] = df.operating_profit / df.revenue * 100
    df["net_margin"] = df.net_profit / df.revenue * 100
    return df


def src_list(ids):
    return ", ".join(f"{i}" for i in ids or [])


def fmt(v):
    if v is None:
        return ""
    return f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


st.title(f"{co.get('name', '')} · {co.get('ticker', '')}")
st.caption(f"{co.get('market', '')} · as of {R.get('as_of', '')} · {R.get('subtitle', '')}")

tabs = ["Overview", "Financials", "Report", "Evidence", "Trust"] + (["Compare"] if len(reports) > 1 else [])
T = dict(zip(tabs, st.tabs(tabs)))

with T["Overview"]:
    c = st.columns(3)
    c[0].metric("Report status", R.get("status", "-"))
    op = R.get("opinion", {})
    c[1].metric("Opinion", op.get("decision", "-"), op.get("confidence", ""), delta_color="off")
    c[2].metric("Delivery audit", (AUD or {}).get("decision", "n/a"))
    st.warning("This is a research draft, not investment advice. "
               + (op.get("lead", {}).get("text", "") if isinstance(op.get("lead"), dict) else ""))
    k = R.get("kpis", [])
    if k:
        cols = st.columns(len(k))
        for col, x in zip(cols, k):
            col.metric(x["label"], f"{fmt(x['value'])} {x.get('unit', '')}")
            col.caption(f"{x.get('period', '')} · {x.get('basis', '')} · {b(x.get('status', ''))}")
    for p in R.get("summary", []):
        st.markdown(f"{p['text']}  \n<sub>{b(p.get('status', ''))} · sources: {src_list(p.get('source_ids'))}</sub>",
                    unsafe_allow_html=True)
    with st.expander("Known limitations (read before trusting the numbers)", expanded=True):
        for l in R.get("limitations", []):
            st.markdown(f"- {l}")

with T["Financials"]:
    q = quarters_df(R)
    if q.empty:
        st.info("This report has no quarterly history.")
    else:
        unit = q["unit"].dropna().iloc[0] if "unit" in q else ""
        st.caption(f"Unit: {unit}. Colour = data type: filed / derived (full year − cumulative) / preliminary (company, pre-close).")
        a, bcol = st.columns(2)
        for col, m, t in ((a, "revenue", "Revenue"), (bcol, "operating_profit", "Operating profit")):
            fig = px.bar(q, x="period", y=m, color="status", color_discrete_map=STATUS_COLOR, title=t)
            fig.update_layout(yaxis_title=unit, xaxis_title=None, legend_title=None)
            col.plotly_chart(fig, width="stretch")
        fig = go.Figure()
        fig.add_scatter(x=q.period, y=q.op_margin, name="Operating margin", mode="lines+markers")
        fig.add_scatter(x=q.period, y=q.net_margin, name="Net margin (owners)", mode="lines+markers")
        fig.update_layout(title="Margins (%)  — net margin blank where net profit is not published", yaxis_title="%")
        st.plotly_chart(fig, width="stretch")
        cols = [c for c in ("period", "status", "revenue", "operating_profit", "op_margin", "net_profit", "calculation") if c in q]
        st.dataframe(q[cols].round(2), width="stretch", hide_index=True)
        ann = pd.DataFrame(R.get("financial_history", {}).get("annual", []))
        if not ann.empty:
            st.subheader("Annual")
            st.dataframe(ann.drop(columns=["source_ids"], errors="ignore"), width="stretch", hide_index=True)

with T["Report"]:
    st.caption("The full Goose report, section by section. 🟢 verified · 🟡 qualified · 🔵 analyst inference.")
    for s in R.get("sections", []):
        with st.expander(s["title"]):
            for i, blk in enumerate(s["blocks"]):
                t = blk["type"]
                if t == "paragraph":
                    st.markdown(f"{blk['text']}  \n<sub>{b(blk.get('status', ''))} · {src_list(blk.get('source_ids'))}</sub>",
                                unsafe_allow_html=True)
                elif t == "table":
                    st.markdown(f"**{blk['title']}**")
                    st.caption(f"{blk.get('period', '')} · {blk.get('unit', '')} · {blk.get('basis', '')}")
                    df = pd.DataFrame([[fmt(v) for v in r] for r in blk["rows"]], columns=blk["headers"])
                    st.dataframe(df, width="stretch", hide_index=True)
                elif t == "chart":
                    f = go.Figure()
                    for se in blk["series"]:
                        (f.add_bar if blk["kind"] == "bar" else f.add_scatter)(
                            x=blk["categories"], y=se["values"], name=se["label"],
                            **({} if blk["kind"] == "bar" else {"mode": "lines+markers"}))
                    f.update_layout(title=blk["title"], yaxis_title=blk.get("unit"), barmode="group")
                    st.plotly_chart(f, width="stretch", key=f"{s['title']}{i}")
    with st.expander("Full opinion"):
        for p in R.get("opinion", {}).get("paragraphs", []):
            st.markdown(" ".join(p["sentences"]))

with T["Evidence"]:
    S = pd.DataFrame(R.get("sources", []))
    st.caption("Every source the report used. 'direct_read' = Goose actually read it; 'blocked' = could not be read.")
    f1, f2 = st.columns(2)
    v = f1.multiselect("Verification", sorted(S.verification.dropna().unique()), default=None)
    ty = f2.multiselect("Source type", sorted(S.source_type.dropna().unique()), default=None)
    if v:
        S = S[S.verification.isin(v)]
    if ty:
        S = S[S.source_type.isin(ty)]
    show = [c for c in ("id", "title", "publisher", "source_type", "verification", "published_at", "period", "url", "findings", "limitations") if c in S]
    st.dataframe(S[show], width="stretch", hide_index=True,
                 column_config={"url": st.column_config.LinkColumn("url")})

with T["Trust"]:
    st.subheader("What was and wasn't read")
    fc = R.get("filing_coverage", {})
    st.dataframe(pd.DataFrame([{"area": k, "status": b(v.get("status")), "read": v.get("read_scope")} for k, v in fc.items()]),
                 width="stretch", hide_index=True)
    st.subheader("Search log")
    sl = pd.DataFrame(R.get("research_window", {}).get("searches", []))
    if not sl.empty:
        st.dataframe(sl.drop(columns=["source_ids"], errors="ignore"), width="stretch", hide_index=True)
    claims = [b_ for s in R.get("sections", []) for b_ in s["blocks"] if b_.get("status")]
    if claims:
        cnt = pd.Series([x["status"] for x in claims]).value_counts().rename_axis("status").reset_index(name="blocks")
        st.subheader("Evidence status of report blocks")
        st.plotly_chart(px.bar(cnt, x="status", y="blocks", color="status"), width="stretch")
    if AUD:
        st.subheader(f"Delivery audit: {AUD.get('decision')} (delivery allowed: {AUD.get('delivery_allowed')})")
        for k2, v2 in AUD.get("review", {}).get("checks", {}).items():
            st.markdown(f"**{k2}** {b(v2.get('status'))}  \n{v2.get('evidence', '')}")

if "Compare" in T:
    with T["Compare"]:
        st.caption("Margins are unit-free, so they compare across companies. Fiscal calendars may differ; check each report.")
        fig = go.Figure()
        for k3 in reports:
            qq = quarters_df(reports[k3][0])
            if not qq.empty:
                fig.add_scatter(x=qq.period, y=qq.op_margin, name=reports[k3][0]["company"]["name"], mode="lines+markers")
        fig.update_layout(title="Operating margin (%)", yaxis_title="%")
        st.plotly_chart(fig, width="stretch")
