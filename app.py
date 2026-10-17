"""Goose report dashboard: turns Goose report-input.json files into an interactive view.
Reports live in reports/<name>/report.json (optionally delivery-audit.json). You can also upload a Goose ZIP."""
import io, json, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Goose report dashboard", layout="wide")
ROOT = Path(__file__).parent / "reports"
NAMES = ("input.en.json", "report-input.json", "input.json", "report.json")
STATUS_COLOR = {"filed": "#4C78A8", "company_release": "#4C78A8", "derived": "#9ECAE9", "secondary": "#B0B0B0", "preliminary": "#E45756"}
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

tabs = ["Overview", "Financials", "Report", "Evidence", "Trust"] + (["Compare", "Analysis lab"] if len(reports) > 2 else (["Compare"] if len(reports) > 1 else []))
T = dict(zip(tabs, st.tabs(tabs)))

with T["Overview"]:
    c = st.columns(3)
    c[0].metric("Report status", R.get("status", "-"))
    op = R.get("opinion", {})
    c[1].metric("Opinion", op.get("decision", "Not assessed"), op.get("confidence", ""), delta_color="off")
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
        st.caption(f"Unit: {unit}. Colour = data type: filed or company release (blue) / derived (light blue) / secondary source only (grey) / preliminary (red).")
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
    if not R.get("sections"):
        st.info("This is a light data pull (financials only), so there is no written report. Run the full Goose report workflow to get one.")
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
    if R.get("opinion", {}).get("paragraphs"):
        with st.expander("Full opinion"):
            for p in R["opinion"]["paragraphs"]:
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
        st.caption("Margins and growth are unit-free, so they compare across currencies. Periods are calendar quarter-ends (Toyota's fiscal year ends in March). "
                   "Net profit bases differ by company, so only operating profit is compared.")
        picked = st.multiselect("Companies", list(reports), default=[k for k in reports if reports[k][0]["company"].get("ticker") != "005930"], format_func=lambda k: reports[k][0]["company"]["name"])
        rows = []
        for k3 in picked:
            qq = quarters_df(reports[k3][0])
            if qq.empty:
                continue
            qq = qq.sort_values("period").copy()
            qq["company"] = reports[k3][0]["company"]["name"]
            qq["rev_yoy"] = qq.revenue.pct_change(4) * 100
            rows.append(qq)
        if rows:
            all_q = pd.concat(rows)
            a1, a2 = st.columns(2)
            f1 = px.line(all_q, x="period", y="op_margin", color="company", markers=True, title="Operating margin (%)")
            f1.update_layout(yaxis_title="%", xaxis_title=None)
            a1.plotly_chart(f1, width="stretch")
            f2 = px.line(all_q.dropna(subset=["rev_yoy"]), x="period", y="rev_yoy", color="company", markers=True, title="Revenue growth vs same quarter last year (%)")
            f2.update_layout(yaxis_title="%", xaxis_title=None)
            a2.plotly_chart(f2, width="stretch")
            last = all_q[all_q.period == all_q.period.max()][["company", "period", "status", "revenue", "operating_profit", "op_margin", "rev_yoy", "unit"]]
            st.subheader("Latest quarter")
            st.dataframe(last.sort_values("op_margin", ascending=False).round(1), width="stretch", hide_index=True)


T_90 = {3: 1.638, 4: 1.533, 5: 1.476, 6: 1.440}  # t critical values, two-sided 80% interval, df = n - 2


def margin_panel(keys):
    cols = {}
    for k in keys:
        qq = quarters_df(reports[k][0])
        if not qq.empty:
            cols[reports[k][0]["company"]["name"]] = qq.set_index("period").op_margin
    return pd.DataFrame(cols).sort_index()


def trend_fit(y):
    """OLS of y on t. Returns slope, forecast for next point, 80% prediction half-width."""
    y = np.asarray(y, float)
    t = np.arange(len(y))
    b1, b0 = np.polyfit(t, y, 1)
    res = y - (b0 + b1 * t)
    n = len(y)
    s = np.sqrt((res ** 2).sum() / (n - 2))
    x0 = n
    se = s * np.sqrt(1 + 1 / n + (x0 - t.mean()) ** 2 / ((t - t.mean()) ** 2).sum())
    return b1, b0 + b1 * x0, T_90.get(n - 2, np.nan) * se


def kmeans(X, k, seed=0, iters=50):
    best = None
    for s_ in range(20):
        rng = np.random.default_rng(seed + s_)
        C = X[rng.choice(len(X), k, replace=False)]
        for _ in range(iters):
            lab = ((X[:, None] - C[None]) ** 2).sum(-1).argmin(1)
            C2 = np.array([X[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)])
            if np.allclose(C, C2):
                break
            C = C2
        inertia = ((X - C[lab]) ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, lab)
    return best[1]


if "Analysis lab" in T:
    with T["Analysis lab"]:
        st.warning("Small-data warning: each company has only about 8 quarters. These are simple descriptive and statistical tools to explore the data, "
                   "not reliable forecasts. Operating margin is the analysis variable because it is unit-free.")
        lab_keys = st.multiselect("Companies in the lab", list(reports),
                                  default=[k for k in reports if reports[k][0]["company"].get("ticker") != "005930"],
                                  format_func=lambda k: reports[k][0]["company"]["name"], key="lab_keys")
        M = margin_panel(lab_keys).dropna(axis=1, thresh=5)
        if M.shape[1] < 3:
            st.info("Pick at least three companies with five or more quarters.")
        else:
            st.subheader("1. Profile: level, stability and direction")
            prof = pd.DataFrame({
                "mean margin (%)": M.mean(),
                "volatility (std, pp)": M.std(),
                "trend (pp per quarter)": [trend_fit(M[c].dropna())[0] for c in M],
                "latest (%)": M.ffill().iloc[-1],
                "worst quarter (%)": M.min()}).round(2)
            st.dataframe(prof.sort_values("mean margin (%)", ascending=False), width="stretch")
            fig = px.scatter(prof.reset_index(names="company"), x="volatility (std, pp)", y="mean margin (%)", text="company",
                             title="Margin level vs stability (top-left = high and steady)")
            fig.update_traces(textposition="top center")
            st.plotly_chart(fig, width="stretch")

            st.subheader("2. Peer groups (k-means on level, volatility, trend, latest)")
            k_ = st.slider("Number of groups", 2, min(5, M.shape[1] - 1), 3)
            X = prof[["mean margin (%)", "volatility (std, pp)", "trend (pp per quarter)", "latest (%)"]].values
            Xz = (X - X.mean(0)) / (X.std(0) + 1e-9)
            prof["group"] = ["Group " + str(g + 1) for g in kmeans(Xz, k_)]
            fig = px.scatter(prof.reset_index(names="company"), x="mean margin (%)", y="trend (pp per quarter)", color="group", text="company",
                             title="Groups by margin level and direction")
            fig.update_traces(textposition="top center")
            st.plotly_chart(fig, width="stretch")
            st.caption("Descriptive grouping only: it says which companies have looked alike over these quarters, not why.")

            st.subheader("3. Do margins move together?")
            D = M.diff().dropna(how="all")
            corr = D.corr().round(2)
            st.plotly_chart(px.imshow(corr, text_auto=True, zmin=-1, zmax=1, color_continuous_scale="RdBu", title="Correlation of quarter-to-quarter margin changes"),
                            width="stretch")
            st.caption(f"Based on {len(D)} changes per pair, so single values are noisy. Changes are used instead of levels to avoid fake correlation from shared trends.")

            st.subheader("4. Next-quarter margin: does a trend line beat a naive guess?")
            errs = []
            for c in M:
                y = M[c].dropna().values
                for t0 in range(len(y) - 3, len(y)):
                    if t0 < 4:
                        continue
                    tr = np.polyval(np.polyfit(np.arange(t0), y[:t0], 1), t0)
                    errs.append(dict(company=c, last_value=abs(y[t0] - y[t0 - 1]), average=abs(y[t0] - y[:t0].mean()), trend_line=abs(y[t0] - tr)))
            E = pd.DataFrame(errs)
            if not E.empty:
                bt = E[["last_value", "average", "trend_line"]].mean().round(2).rename("mean absolute error (pp)").to_frame()
                st.dataframe(bt.T, width="stretch")
                st.caption(f"Rolling backtest: predict each of the last 3 quarters from earlier ones, across {E.company.nunique()} companies ({len(E)} predictions). Lower is better; "
                           "the winner here may not hold with more data.")
            nxt = []
            for c in M:
                y = M[c].dropna().values
                b1, f, hw = trend_fit(y)
                nxt.append(dict(company=c, latest=round(y[-1], 2), trend_forecast=round(f, 2), low_80=round(f - hw, 2), high_80=round(f + hw, 2),
                                interval_width=round(2 * hw, 2)))
            N = pd.DataFrame(nxt).set_index("company")
            st.dataframe(N, width="stretch")
            st.caption("Trend-line forecast of the next quarter's operating margin (%) with an 80% prediction interval. Wide intervals mean the trend says little; "
                       "one-off items, seasonality and guidance are not modelled.")
            pick = st.selectbox("Show one company", list(M.columns))
            y = M[pick].dropna()
            b1, f, hw = trend_fit(y.values)
            fg = go.Figure()
            fg.add_scatter(x=list(y.index), y=y.values, name="actual", mode="lines+markers")
            fg.add_scatter(x=["next"], y=[f], name="trend forecast", mode="markers", error_y=dict(type="constant", value=float(hw)))
            fg.update_layout(title=f"{pick}: operating margin (%) with next-quarter trend forecast (80% interval)", yaxis_title="%")
            st.plotly_chart(fg, width="stretch")
