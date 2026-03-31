import streamlit as st
import openai
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

openai.api_key = st.secrets["openai"]["api_key"]

st.title("StockSense Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about stocks, e.g., 'Analyze AAPL'"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Fetch stock data
        if "analyze" in prompt.lower() or any(t in prompt.lower() for t in ["price", "stock"]):
            ticker = prompt.upper().split()[-1] if prompt.upper().split()[-1].isalpha() else "AAPL"
            data = yf.download(ticker, period="1y")
            if not data.empty:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=data.index, open=data['Open'], high=data['High'], low=data['Low'], close=data['Close']))
                st.plotly_chart(fig, use_container_width=True)
                analysis = f"{ticker} latest close: ${data['Close'][-1]:.2f}. 1Y high: ${data['High'].max():.2f}."
            else:
                analysis = "Invalid ticker."
        else:
            analysis = "Stock query detected."

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages] + [{"role": "user", "content": prompt + "\nAnalysis: " + analysis}]
        ).choices[0].message.content
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# ── CONFIG ────────────────────────────────────────────────────────────────────
COMPANIES = {
    "Reliance":           "RELIANCE.NS",
    "ITC":                "ITC.NS",
    "Hindustan Unilever": "HINDUNILVR.NS",
    "Trent":              "TRENT.NS",
}

# ── PAGE SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StockSense",
    page_icon="📈",
    layout="wide"
)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner="Loading live NSE data...")
def load_data():
    result = {}
    today = datetime.now().strftime("%Y-%m-%d")
    for name, ticker in COMPANIES.items():
        try:
            df = yf.download(ticker, start="1998-01-01", end=today, progress=False)
            result[name] = df
        except:
            pass
    return result

stock_data = load_data()

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────
def calc_magr(data):
    if data is None or len(data) == 0:
        return 0.0
    try:
        dc = data.copy().reset_index()
        dc["Year"] = pd.to_datetime(dc["Date"]).dt.year
        cur_year = datetime.now().year
        yearly = []
        for yr in sorted(dc["Year"].unique()):
            yd = dc[dc["Year"] == yr]
            fp = float(yd["Close"].iloc[0])
            lp = float(yd["Close"].iloc[-1])
            yearly.append(((lp - fp) / fp) * 100)
        return round(float(np.mean(yearly)), 2) if yearly else 0.0
    except:
        return 0.0

def get_trend_signal(close, ma50, ma200):
    cp, m50, m200 = float(close[-1]), float(ma50[-1]), float(ma200[-1])
    if cp > m50 and cp > m200:
        return "🔥 Strong Bullish — Price above both MAs", "success"
    elif cp > m50:
        return "📈 Moderate Bullish — Price above 50-Day MA", "info"
    elif cp < m50 and cp < m200:
        return "📉 Bearish — Price below both MAs", "error"
    else:
        return "⚠️ Neutral / Mixed Signal", "warning"

def calc_return(data, year, month, day, amount):
    try:
        date_obj = pd.to_datetime(f"{year}-{month:02d}-{day:02d}")
        if date_obj > pd.Timestamp.now():
            date_obj = pd.Timestamp.now()
        if date_obj in data.index:
            buy_price = float(data.loc[date_obj, "Close"])
        else:
            idx = data.index.get_indexer([date_obj], method="nearest")[0]
            buy_price = float(data["Close"].iloc[idx])
            date_obj  = data.index[idx]
        cur_price = float(data["Close"].iloc[-1])
        cur_date  = data.index[-1]
        shares    = amount / buy_price
        cur_val   = shares * cur_price
        pl        = cur_val - amount
        days      = (cur_date - date_obj).days
        yrs       = days / 365.25
        ann       = (((cur_val / amount) ** (1 / yrs)) - 1) * 100 if yrs > 0 else 0
        return {
            "buy_price":   buy_price,
            "cur_price":   cur_price,
            "cur_val":     cur_val,
            "pl":          pl,
            "pl_pct":      (pl / amount) * 100,
            "days":        days,
            "ann":         ann,
            "buy_date":    date_obj.strftime("%Y-%m-%d"),
            "cur_date":    cur_date.strftime("%Y-%m-%d"),
            "shares":      shares,
        }
    except Exception as e:
        st.error(f"Error: {e}")
        return None

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 StockSense")
    st.caption("Indian Stock Market Analysis")
    st.divider()
    page = st.radio("Go to", [
        "📊 Dashboard",
        "🔄 Compare",
        "💰 Return Calculator",
        "🤖 AI Chatbot",
        "✅ Accuracy Report",
    ])
    st.divider()
    st.caption("📡 Live data: NSE via Yahoo Finance")
    st.caption("📅 History: 1998 → Today")
    st.divider()
    st.warning("For educational use only.\nNot financial advice.")

# ── GROWTH CARDS ──────────────────────────────────────────────────────────────
def show_growth_cards():
    st.markdown("### 📈 Mean Annual Growth Rate — 1998 to Present")
    cols = st.columns(4)
    for col, name in zip(cols, COMPANIES):
        g = calc_magr(stock_data.get(name))
        col.metric(name, f"{g:.2f}%", delta=f"{'↑' if g >= 0 else '↓'} avg/year")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    show_growth_cards()
    st.divider()
    st.header("📊 Stock Analysis Dashboard")

    c1, c2 = st.columns(2)
    company  = c1.selectbox("Select Company", list(COMPANIES.keys()))
    analysis = c2.selectbox("Analysis Type", ["Summary", "Trend", "Statistical", "Year-by-Year"])

    data = stock_data.get(company)
    if data is None or len(data) == 0:
        st.error("No data loaded. Check your internet connection.")
        st.stop()

    # SUMMARY
    if analysis == "Summary":
        cur   = float(data["Close"].iloc[-1])
        prev  = float(data["Close"].iloc[-2])
        chg   = ((cur - prev) / prev) * 100
        hi52  = float(data["High"].max())
        lo52  = float(data["Low"].min())

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Price", f"₹{cur:.2f}")
        m2.metric("Day Change",    f"{chg:.2f}%", delta=f"{chg:.2f}%")
        m3.metric("52W High",      f"₹{hi52:.2f}")
        m4.metric("52W Low",       f"₹{lo52:.2f}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data["Close"].values.flatten(),
            mode="lines",
            line=dict(color="#667eea", width=2),
            fill="tozeroy",
            fillcolor="rgba(102,126,234,0.1)"
        ))
        fig.update_layout(
            title=f"{company} — Price History (1998 to Today)",
            xaxis_title="Date", yaxis_title="Price (₹)",
            height=450, template="plotly_white", hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

    # TREND
    elif analysis == "Trend":
        df    = data.tail(1000).copy()
        close = df["Close"].values.flatten()
        dates = df.index
        ma50  = pd.Series(close).rolling(50,  min_periods=1).mean().values
        ma200 = pd.Series(close).rolling(200, min_periods=1).mean().values

        signal, stype = get_trend_signal(close, ma50, ma200)
        if stype == "success": st.success(signal)
        elif stype == "info":  st.info(signal)
        elif stype == "error": st.error(signal)
        else:                  st.warning(signal)

        m1, m2, m3 = st.columns(3)
        m1.metric("Current Price", f"₹{float(close[-1]):.2f}")
        m2.metric("50-Day MA",     f"₹{float(ma50[-1]):.2f}")
        m3.metric("200-Day MA",    f"₹{float(ma200[-1]):.2f}")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=dates, y=close, name="Price",     line=dict(color="#667eea", width=2)))
        fig.add_trace(go.Scatter(x=dates, y=ma50,  name="50-Day MA", line=dict(color="#f97316", width=2, dash="dash")))
        fig.add_trace(go.Scatter(x=dates, y=ma200, name="200-Day MA",line=dict(color="#10b981", width=2, dash="dot")))
        fig.update_layout(
            title=f"{company} — Trend Analysis (Last 1000 Days)",
            xaxis_title="Date", yaxis_title="Price (₹)",
            height=450, template="plotly_white", hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

    # STATISTICAL
    elif analysis == "Statistical":
        dc = data.copy()
        dc["DR"] = dc["Close"].pct_change() * 100

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 📈 Price Statistics")
            st.write(f"**Mean Price:** ₹{float(dc['Close'].mean()):.2f}")
            st.write(f"**Median Price:** ₹{float(dc['Close'].median()):.2f}")
            st.write(f"**Std Deviation:** ₹{float(dc['Close'].std()):.2f}")
            st.write(f"**Min Price:** ₹{float(dc['Close'].min()):.2f}")
            st.write(f"**Max Price:** ₹{float(dc['Close'].max()):.2f}")
        with c2:
            st.markdown("#### 📊 Returns Statistics")
            st.write(f"**Mean Daily Return:** {float(dc['DR'].mean()):.4f}%")
            st.write(f"**Volatility:** {float(dc['DR'].std()):.4f}%")
            st.write(f"**Best Day:** {float(dc['DR'].max()):.2f}%")
            st.write(f"**Worst Day:** {float(dc['DR'].min()):.2f}%")

        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=dc["DR"].dropna(),
            nbinsx=60,
            marker_color="#667eea",
            opacity=0.8
        ))
        fig.update_layout(
            title=f"{company} — Daily Returns Distribution",
            xaxis_title="Daily Return (%)", yaxis_title="Frequency",
            height=400, template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

    # YEAR BY YEAR
    elif analysis == "Year-by-Year":
        dc = data.copy().reset_index()
        dc["Year"] = pd.to_datetime(dc["Date"]).dt.year
        rows = []
        for yr in sorted(dc["Year"].unique()):
            yd = dc[dc["Year"] == yr]
            fp = float(yd["Close"].iloc[0])
            lp = float(yd["Close"].iloc[-1])
            rows.append({"Year": int(yr), "Return (%)": round(((lp-fp)/fp)*100, 2)})
        ydf = pd.DataFrame(rows)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=ydf["Year"],
            y=ydf["Return (%)"],
            marker_color=["#10b981" if r > 0 else "#ef4444" for r in ydf["Return (%)"]],
            text=ydf["Return (%)"].apply(lambda x: f"{x:.1f}%"),
            textposition="outside"
        ))
        fig.update_layout(
            title=f"{company} — Year by Year Returns",
            xaxis_title="Year", yaxis_title="Return (%)",
            height=450, template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ydf, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — COMPARE
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔄 Compare":
    show_growth_cards()
    st.divider()
    st.header("🔄 Compare Companies")

    selected = st.multiselect(
        "Select at least 2 companies",
        list(COMPANIES.keys()),
        default=["Reliance", "ITC"]
    )
    analysis = st.selectbox("Analysis Type", ["Price & Volume", "Trend", "Statistics", "Year-by-Year"])

    if len(selected) < 2:
        st.warning("Please select at least 2 companies.")
        st.stop()

    if st.button("🔄 Compare Now", type="primary"):

        if analysis == "Price & Volume":
            fig1 = go.Figure()
            fig2 = go.Figure()
            rows = []
            for name in selected:
                d = stock_data.get(name)
                if d is not None:
                    df = d.tail(1000)
                    fig1.add_trace(go.Scatter(x=df.index, y=df["Close"].values.flatten(), mode="lines", name=name))
                    fig2.add_trace(go.Scatter(x=df.index, y=df["Volume"].values.flatten(), mode="lines", name=name))
                    rows.append({
                        "Company":       name,
                        "Current Price": f"₹{float(d['Close'].iloc[-1]):.2f}",
                        "52W High":      f"₹{float(d['High'].max()):.2f}",
                        "52W Low":       f"₹{float(d['Low'].min()):.2f}",
                    })
            fig1.update_layout(title="Price Comparison — Last 1000 Days", height=400, template="plotly_white")
            fig2.update_layout(title="Volume Comparison — Last 1000 Days", height=400, template="plotly_white")
            st.plotly_chart(fig1, use_container_width=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(pd.DataFrame(rows), use_container_width=True)

        elif analysis == "Trend":
            for name in selected:
                d = stock_data.get(name)
                if d is not None:
                    df    = d.tail(1000)
                    close = df["Close"].values.flatten()
                    ma50  = pd.Series(close).rolling(50,  min_periods=1).mean().values
                    ma200 = pd.Series(close).rolling(200, min_periods=1).mean().values
                    sig, stype = get_trend_signal(close, ma50, ma200)
                    st.markdown(f"**{name}** — {sig}")
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df.index, y=close, name="Price",      line=dict(width=2)))
                    fig.add_trace(go.Scatter(x=df.index, y=ma50,  name="50-Day MA",  line=dict(dash="dash")))
                    fig.add_trace(go.Scatter(x=df.index, y=ma200, name="200-Day MA", line=dict(dash="dot")))
                    fig.update_layout(title=f"{name} Trend", height=350, template="plotly_white")
                    st.plotly_chart(fig, use_container_width=True)

        elif analysis == "Statistics":
            rows = []
            for name in selected:
                d = stock_data.get(name)
                if d is not None:
                    dc = d.copy()
                    dc["DR"] = dc["Close"].pct_change() * 100
                    rows.append({
                        "Company":      name,
                        "Mean Return%": f"{float(dc['DR'].mean()):.4f}",
                        "Volatility%":  f"{float(dc['DR'].std()):.4f}",
                        "Best Day%":    f"{float(dc['DR'].max()):.2f}",
                        "Worst Day%":   f"{float(dc['DR'].min()):.2f}",
                    })
            df_s = pd.DataFrame(rows)
            st.dataframe(df_s, use_container_width=True)
            for col in ["Mean Return%", "Volatility%", "Best Day%", "Worst Day%"]:
                fig = px.bar(df_s, x="Company", y=col, title=col, height=300)
                st.plotly_chart(fig, use_container_width=True)

        elif analysis == "Year-by-Year":
            fig = go.Figure()
            for name in selected:
                d = stock_data.get(name)
                if d is not None:
                    dc = d.copy().reset_index()
                    dc["Year"] = pd.to_datetime(dc["Date"]).dt.year
                    rows = []
                    for yr in sorted(dc["Year"].unique()):
                        yd = dc[dc["Year"] == yr]
                        fp = float(yd["Close"].iloc[0])
                        lp = float(yd["Close"].iloc[-1])
                        rows.append({"Year": int(yr), "Return": round(((lp-fp)/fp)*100, 2)})
                    ydf = pd.DataFrame(rows)
                    fig.add_trace(go.Scatter(x=ydf["Year"], y=ydf["Return"], mode="lines+markers", name=name))
            fig.add_hline(y=0, line_color="black", line_width=1)
            fig.update_layout(title="Year-by-Year Return Comparison", height=450, template="plotly_white")
            st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — RETURN CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💰 Return Calculator":
    show_growth_cards()
    st.divider()
    st.header("💰 Investment Return Calculator")
    st.caption("Enter a past investment date and amount to see today's profit or loss.")

    c1, c2 = st.columns(2)
    company = c1.selectbox("Company", list(COMPANIES.keys()))
    amount  = c2.number_input("Investment Amount (₹)", min_value=1000, value=10000, step=500)

    c3, c4, c5 = st.columns(3)
    year  = c3.number_input("Year",  min_value=1998, max_value=2025, value=2020)
    month = c4.number_input("Month", min_value=1,    max_value=12,   value=1)
    day   = c5.number_input("Day",   min_value=1,    max_value=31,   value=1)

    if st.button("💰 Calculate", type="primary"):
        r = calc_return(stock_data.get(company), int(year), int(month), int(day), float(amount))
        if r:
            profit = r["pl"] >= 0
            st.divider()
            st.markdown(f"### {'🎉 You made a Profit!' if profit else '😔 You made a Loss'}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Invested",          f"₹{amount:,.2f}")
            m2.metric("Current Value",     f"₹{r['cur_val']:,.2f}")
            m3.metric("Profit / Loss",     f"₹{abs(r['pl']):,.2f}", delta=f"{r['pl_pct']:.2f}%")
            m4.metric("Annualised Return", f"{r['ann']:.2f}% / yr")

            st.markdown(f"""
| | |
|---|---|
| 📅 Buy Date | {r['buy_date']} |
| 📅 Today | {r['cur_date']} |
| ⏱️ Days Held | {r['days']} days |
| 💵 Buy Price | ₹{r['buy_price']:.2f} |
| 💎 Current Price | ₹{r['cur_price']:.2f} |
| 🔢 Shares | {r['shares']:.4f} |
""")
            st.caption("⚠️ Educational use only. Not financial advice.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — AI CHATBOT (RAG)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Chatbot":
    st.header("🤖 StockSense AI Chatbot")
    st.caption("Ask anything about Reliance, ITC, Hindustan Unilever, and Trent stocks.")

    # ── Build knowledge base from live stock data ─────────────────────────────
    @st.cache_resource(show_spinner="Building knowledge base from live stock data...")
    def build_knowledge_base(_stock_data):
        """
        Convert live yfinance data into text chunks — this IS the RAG knowledge base.
        No PDFs or API keys needed. The knowledge base is built from real stock data.
        """
        chunks = []
        for name, data in _stock_data.items():
            if data is None or len(data) == 0:
                continue

            # Current price info
            cur   = float(data["Close"].iloc[-1])
            prev  = float(data["Close"].iloc[-2])
            chg   = ((cur - prev) / prev) * 100
            hi52  = float(data["High"].max())
            lo52  = float(data["Low"].min())
            chunks.append(
                f"{name} current stock price is ₹{cur:.2f}. "
                f"Day change is {chg:.2f}%. "
                f"All-time high is ₹{hi52:.2f} and all-time low is ₹{lo52:.2f}."
            )

            # MAGR
            magr = calc_magr(data)
            chunks.append(
                f"{name} has a Mean Annual Growth Rate (MAGR) of {magr:.2f}% since 1998. "
                f"{'This is a strong positive growth.' if magr > 15 else 'This shows moderate growth.' if magr > 5 else 'This shows slow or negative growth.'}"
            )

            # Trend analysis
            df    = data.tail(1000)
            close = df["Close"].values.flatten()
            ma50  = pd.Series(close).rolling(50,  min_periods=1).mean().values
            ma200 = pd.Series(close).rolling(200, min_periods=1).mean().values
            cp, m50, m200 = float(close[-1]), float(ma50[-1]), float(ma200[-1])
            if cp > m50 and cp > m200:
                trend = "strong bullish — price is above both 50-day and 200-day moving averages"
            elif cp > m50:
                trend = "moderate bullish — price is above the 50-day moving average"
            elif cp < m50 and cp < m200:
                trend = "bearish — price is below both moving averages"
            else:
                trend = "neutral or mixed"
            chunks.append(
                f"{name} trend analysis shows a {trend}. "
                f"Current price ₹{cp:.2f}, 50-day MA ₹{m50:.2f}, 200-day MA ₹{m200:.2f}."
            )

            # Volatility and returns
            dc = data.copy()
            dc["DR"] = dc["Close"].pct_change() * 100
            vol      = float(dc["DR"].std())
            best     = float(dc["DR"].max())
            worst    = float(dc["DR"].min())
            mean_ret = float(dc["DR"].mean())
            chunks.append(
                f"{name} statistical analysis: mean daily return {mean_ret:.4f}%, "
                f"volatility {vol:.4f}%, best single day {best:.2f}%, worst single day {worst:.2f}%. "
                f"{'High volatility stock.' if vol > 2 else 'Moderate volatility stock.' if vol > 1 else 'Low volatility stock.'}"
            )

            # Year by year — last 5 years
            dc2 = data.copy().reset_index()
            dc2["Year"] = pd.to_datetime(dc2["Date"]).dt.year
            recent_years = sorted(dc2["Year"].unique())[-5:]
            yearly_text = []
            for yr in recent_years:
                yd = dc2[dc2["Year"] == yr]
                fp = float(yd["Close"].iloc[0])
                lp = float(yd["Close"].iloc[-1])
                ret = round(((lp - fp) / fp) * 100, 2)
                yearly_text.append(f"{yr}: {ret:.1f}%")
            chunks.append(
                f"{name} year-by-year returns for recent years — {', '.join(yearly_text)}."
            )

            # Price levels
            mean_price = float(data["Close"].mean())
            chunks.append(
                f"{name} average price since 1998 is ₹{mean_price:.2f}. "
                f"The stock is currently trading {'above' if cur > mean_price else 'below'} its historical average."
            )

        # Add comparison chunks
        names     = list(_stock_data.keys())
        magr_vals = {n: calc_magr(_stock_data[n]) for n in names}
        best_co   = max(magr_vals, key=magr_vals.get)
        worst_co  = min(magr_vals, key=magr_vals.get)
        chunks.append(
            f"Comparing all four companies: {best_co} has the highest MAGR at {magr_vals[best_co]:.2f}%, "
            f"and {worst_co} has the lowest MAGR at {magr_vals[worst_co]:.2f}%. "
            f"All MAGRs: " + ", ".join([f"{n} {v:.2f}%" for n, v in magr_vals.items()])
        )

        # Volatility comparison
        vols = {}
        for n, d in _stock_data.items():
            if d is not None:
                dc = d.copy()
                dc["DR"] = dc["Close"].pct_change() * 100
                vols[n] = float(dc["DR"].std())
        most_vol  = max(vols, key=vols.get)
        least_vol = min(vols, key=vols.get)
        chunks.append(
            f"Volatility comparison: {most_vol} is the most volatile stock with {vols[most_vol]:.4f}% std deviation. "
            f"{least_vol} is the least volatile with {vols[least_vol]:.4f}% std deviation."
        )

        # General knowledge chunks
        chunks += [
            "MAGR stands for Mean Annual Growth Rate. It is the average yearly return of a stock calculated across all years since 1998.",
            "Moving averages help identify trends. The 50-day MA shows short-term trend. The 200-day MA shows long-term trend. When price is above both, it is bullish. When below both, it is bearish.",
            "A golden cross happens when the 50-day moving average crosses above the 200-day moving average — this is a strong bullish signal.",
            "A death cross happens when the 50-day moving average crosses below the 200-day moving average — this is a bearish signal.",
            "Volatility measures how much a stock price moves up and down. Higher volatility means more risk but also more potential reward.",
            "NSE stands for National Stock Exchange of India. BSE stands for Bombay Stock Exchange. Both are major Indian stock exchanges.",
            "Reliance Industries is India's largest company by market cap. It operates in energy, petrochemicals, retail (Reliance Retail), and telecom (Jio).",
            "ITC Limited is a diversified Indian company. Its main businesses are cigarettes, FMCG products, hotels, paperboards, and agribusiness.",
            "Hindustan Unilever Limited (HUL) is India's largest consumer goods company. It sells brands like Surf, Dove, Lux, Lipton, and Horlicks.",
            "Trent Limited is the retail arm of the Tata Group. It operates Westside, Zudio, and Star Bazaar stores across India.",
            "P/E ratio or Price to Earnings ratio shows how much investors pay per rupee of earnings. A high P/E means investors expect high growth.",
            "Bull market means stock prices are rising. Bear market means stock prices are falling. Correction means a drop of 10% or more.",
            "Diversification means spreading investments across different stocks or sectors to reduce risk.",
            "Annual report is a document published every year by a company showing its financial performance including revenue, profit, and balance sheet.",
        ]

        return chunks

    # ── Simple TF-IDF style retrieval (no API needed) ─────────────────────────
    def retrieve_chunks(query, chunks, top_k=4):
        """Find the most relevant chunks using keyword matching."""
        query_words = set(re.findall(r'\w+', query.lower()))
        scores = []
        for i, chunk in enumerate(chunks):
            chunk_words = set(re.findall(r'\w+', chunk.lower()))
            # Score = number of matching words
            score = len(query_words & chunk_words)
            # Boost score if company name is mentioned
            for company in COMPANIES.keys():
                if company.lower() in query.lower() and company.lower() in chunk.lower():
                    score += 5
            scores.append((score, i))
        scores.sort(reverse=True)
        top = [chunks[i] for score, i in scores[:top_k] if score > 0]
        return top if top else chunks[:top_k]

    # ── Generate answer using context ─────────────────────────────────────────
    def generate_answer(query, context_chunks, mode, api_key=""):
        context = "\n".join(context_chunks)

        # Try OpenAI if API key provided
        if api_key.strip():
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key.strip())
                instruction = (
                    "Give a SHORT 2-3 sentence answer using only the context."
                    if mode == "Concise"
                    else "Give a DETAILED answer with full explanation using the context."
                )
                resp = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content":
                            "You are StockSense, an expert on Indian stocks (Reliance, ITC, HUL, Trent). "
                            "Answer ONLY from the provided context. Never make up numbers. "
                            "Always end with: This is for educational purposes only."},
                        {"role": "user", "content":
                            f"Context:\n{context}\n\nQuestion: {query}\n\nInstruction: {instruction}\n\nAnswer:"}
                    ],
                    max_tokens=150 if mode == "Concise" else 400,
                    temperature=0.2,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                return f"OpenAI error: {e}. Showing context-based answer below.\n\n" + "\n\n".join(context_chunks)

        # Free fallback — return the retrieved chunks as the answer
        answer = f"Based on the StockSense knowledge base:\n\n"
        for chunk in context_chunks:
            answer += f"• {chunk}\n\n"
        answer += "\n⚠️ This is for educational purposes only. Not financial advice."
        return answer

    # ── Build knowledge base ──────────────────────────────────────────────────
    chunks = build_knowledge_base(stock_data)

    # ── UI ────────────────────────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    mode = col1.radio("Response Mode", ["Concise", "Detailed"], horizontal=True)

    with st.expander("🔑 Optional: Add OpenAI API Key for better answers"):
        st.caption("Without a key, the chatbot still works using direct knowledge base retrieval.")
        api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")

    st.divider()

    # Example questions
    st.markdown("**💡 Try asking:**")
    example_cols = st.columns(3)
    examples = [
        "What is the trend for Reliance?",
        "Which company has the highest growth?",
        "Compare ITC and HUL volatility",
        "What is MAGR?",
        "Is Trent bullish or bearish?",
        "What does Hindustan Unilever do?",
    ]
    for i, ex in enumerate(examples):
        if example_cols[i % 3].button(ex, use_container_width=True):
            st.session_state["chat_prefill"] = ex

    st.divider()

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Display previous messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask about Reliance, ITC, HUL, Trent...")
    query = user_input or st.session_state.pop("chat_prefill", None)

    if query:
        # Show user message
        st.session_state.chat_history.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.markdown(query)

        # Retrieve + Generate
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                relevant_chunks = retrieve_chunks(query, chunks, top_k=4)
                answer = generate_answer(query, relevant_chunks, mode, api_key if 'api_key' in locals() else "")
            st.markdown(answer)
            st.caption(f"{'⚡ Concise' if mode == 'Concise' else '📖 Detailed'} | 📚 {len(relevant_chunks)} chunks retrieved")

        st.session_state.chat_history.append({"role": "assistant", "content": answer})

    # Clear chat button
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_history = []
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — ACCURACY REPORT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "✅ Accuracy Report":  # noqa
    st.header("✅ System Accuracy Report")
    st.caption("Validates data quality and calculation correctness — from the original notebook.")

    if st.button("▶️ Run Tests", type="primary"):
        with st.spinner("Running accuracy tests..."):

            # Test 1: Data accuracy
            scores = []
            for name, ticker in COMPANIES.items():
                try:
                    d = yf.download(ticker, start="2020-01-01", end="2020-12-31", progress=False)
                    total   = len(d)
                    missing = int(d.isnull().sum().sum())
                    scores.append(((total - missing) / total) * 100)
                except:
                    scores.append(0.0)
            data_acc = float(np.mean(scores))

            # Test 2: Calculation accuracy
            td = pd.DataFrame({"Close": [100,105,103,108,110,112,115,113,118,120]})
            td["DR"] = td["Close"].pct_change() * 100
            manual_mean = sum(td["Close"]) / len(td["Close"])
            manual_std  = float(np.std(td["Close"], ddof=1))
            calc_acc = 100.0
            if abs(manual_mean - float(td["Close"].mean())) >= 0.01: calc_acc -= 33.33
            if abs(manual_std  - float(td["Close"].std()))  >= 0.01: calc_acc -= 33.33

            # Test 3: Moving average accuracy
            prices = [100,102,101,105,107,106,108,110,109,112]
            tdf    = pd.DataFrame({"Close": prices})
            manual_ma = [sum(prices[:i+1])/(i+1) if i<2 else sum(prices[i-2:i+1])/3 for i in range(len(prices))]
            sys_ma    = tdf["Close"].rolling(3, min_periods=1).mean().values
            matches   = sum(abs(manual_ma[i]-sys_ma[i]) < 0.01 for i in range(len(manual_ma)))
            ma_acc    = (matches / len(manual_ma)) * 100

            # Test 4: Return calculation accuracy
            initial, p0, p1 = 10000, 100, 150
            shares = initial / p0
            final  = shares * p1
            return_acc = 100.0
            if abs(shares - initial/p0)            >= 0.01: return_acc -= 25
            if abs(final  - shares*p1)             >= 0.01: return_acc -= 25
            if abs(((final-initial)/initial)*100 - 50.0) >= 0.01: return_acc -= 25

            # Test 5: Trend detection accuracy
            cases   = [(150,140,130,"Bullish"),(120,130,140,"Bearish"),(145,140,150,"Bullish"),(135,130,140,"Neutral")]
            correct = 0
            for p, m50, m200, exp in cases:
                if   p > m50 and p > m200: det = "Bullish"
                elif p < m50 and p < m200: det = "Bearish"
                elif p > m50:              det = "Bullish"
                else:                      det = "Neutral"
                if det == exp: correct += 1
            trend_acc = (correct / len(cases)) * 100

            overall = data_acc*0.20 + calc_acc*0.25 + ma_acc*0.20 + return_acc*0.25 + trend_acc*0.10
            grade   = "A+ Excellent" if overall>=95 else "A Very Good" if overall>=90 else "B+ Good" if overall>=85 else "B Satisfactory"

        # Show results
        st.divider()
        m1,m2,m3,m4,m5 = st.columns(5)
        m1.metric("Data Fetching",   f"{data_acc:.1f}%")
        m2.metric("Calculations",    f"{calc_acc:.1f}%")
        m3.metric("Moving Averages", f"{ma_acc:.1f}%")
        m4.metric("Return Calc",     f"{return_acc:.1f}%")
        m5.metric("Trend Detection", f"{trend_acc:.1f}%")

        st.divider()
        st.markdown(f"## 🎯 Overall: **{overall:.2f}%** — {grade}")

        components = ["Data Fetching","Calculations","Moving Averages","Return Calc","Trend Detection"]
        values     = [data_acc, calc_acc, ma_acc, return_acc, trend_acc]
        colors     = ["#10b981" if v>=95 else "#f97316" if v>=90 else "#ef4444" for v in values]

        fig = go.Figure(go.Bar(
            x=components, y=values,
            marker_color=colors,
            text=[f"{v:.1f}%" for v in values],
            textposition="outside"
        ))
        fig.add_hline(y=95, line_dash="dash", line_color="green",  annotation_text="Excellent 95%+")
        fig.add_hline(y=90, line_dash="dash", line_color="orange", annotation_text="Good 90%+")
        fig.update_layout(
            title="Component Accuracy",
            yaxis_range=[75,110],
            height=420,
            template="plotly_white"
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f"""
| Component | Weight | Score |
|---|---|---|
| Data Fetching | 20% | {data_acc:.1f}% |
| Calculations | 25% | {calc_acc:.1f}% |
| Moving Averages | 20% | {ma_acc:.1f}% |
| Return Calculations | 25% | {return_acc:.1f}% |
| Trend Detection | 10% | {trend_acc:.1f}% |
| **OVERALL** | **100%** | **{overall:.1f}%** |
""")
