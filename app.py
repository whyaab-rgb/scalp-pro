import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(
    page_title="Scalping Pro Dashboard",
    layout="wide",
    page_icon="⚡"
)

# =========================
# STYLE
# =========================
st.markdown("""
<style>
.stApp {
    background: #07111f;
    color: white;
}
.block-container {
    padding-top: 1rem;
}
.card {
    background: linear-gradient(145deg, #0d1b2f, #0a1424);
    padding: 18px;
    border-radius: 18px;
    border: 1px solid #1e3a5f;
    box-shadow: 0 8px 22px rgba(0,0,0,0.35);
}
.big-title {
    font-size: 30px;
    font-weight: 800;
}
.sub {
    color: #9fb3c8;
}
.buy {
    color: #22c55e;
    font-weight: 800;
}
.wait {
    color: #facc15;
    font-weight: 800;
}
.sell {
    color: #ef4444;
    font-weight: 800;
}
.blue {
    color: #38bdf8;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)

# =========================
# WATCHLIST
# =========================
DEFAULT_TICKERS = [
    "BBCA.JK", "BBRI.JK", "BMRI.JK", "BBNI.JK", "TLKM.JK",
    "ANTM.JK", "MDKA.JK", "BRIS.JK", "GOTO.JK", "BUKA.JK",
    "ADRO.JK", "AMMN.JK", "MEDC.JK", "PGAS.JK", "INCO.JK",
    "RAJA.JK", "TPIA.JK", "UNTR.JK", "ASII.JK", "ESSA.JK"
]

# =========================
# INDICATOR
# =========================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist

def get_data(ticker, period="5d", interval="5m"):
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()

        df["RSI"] = rsi(df["Close"])
        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA20"] = df["Close"].rolling(20).mean()

        macd_line, signal, hist = macd(df["Close"])
        df["MACD"] = macd_line
        df["MACD_SIGNAL"] = signal
        df["MACD_HIST"] = hist

        df["VOL_MA20"] = df["Volume"].rolling(20).mean()
        df["RVOL"] = df["Volume"] / df["VOL_MA20"]

        return df.dropna()
    except Exception:
        return None

def analyze_scalping(ticker, manual_entry=0):
    df = get_data(ticker)

    if df is None or len(df) < 30:
        return None, None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["Close"])
    open_ = float(last["Open"])
    high = float(last["High"])
    low = float(last["Low"])
    volume = float(last["Volume"])
    rsi_now = float(last["RSI"])
    rvol = float(last["RVOL"])
    macd_hist = float(last["MACD_HIST"])
    prev_macd_hist = float(prev["MACD_HIST"])
    ma5 = float(last["MA5"])
    ma20 = float(last["MA20"])

    change_pct = ((close - float(prev["Close"])) / float(prev["Close"])) * 100

    candle_bullish = close > open_
    macd_improving = macd_hist > prev_macd_hist
    trend_short = ma5 > ma20
    volume_active = rvol >= 1.2

    score = 0
    if candle_bullish:
        score += 20
    if macd_improving:
        score += 20
    if trend_short:
        score += 20
    if volume_active:
        score += 20
    if 45 <= rsi_now <= 68:
        score += 20

    if score >= 80:
        signal = "MASUK"
        status = "ENTRY KUAT"
    elif score >= 60:
        signal = "PANTAU"
        status = "SIAP ENTRY"
    elif score >= 40:
        signal = "TUNGGU"
        status = "BELUM VALID"
    else:
        signal = "HINDARI"
        status = "LEMAH"

    entry = float(manual_entry) if manual_entry else 0

    if entry > 0:
        profit_pct = ((close - entry) / entry) * 100
        tp1 = entry * 1.03
        tp2 = entry * 1.05
        stop_loss = entry * 0.98
        trailing_stop = close * 0.985

        if profit_pct >= 5:
            exit_signal = "PAKAI TS / AMANKAN PROFIT"
        elif profit_pct >= 3:
            exit_signal = "TP1 TERCAPAI"
        elif close <= stop_loss:
            exit_signal = "CUT LOSS"
        elif macd_hist < prev_macd_hist and profit_pct > 0:
            exit_signal = "WASPADA KELUAR"
        else:
            exit_signal = "HOLD"
    else:
        profit_pct = np.nan
        tp1 = np.nan
        tp2 = np.nan
        stop_loss = np.nan
        trailing_stop = np.nan
        exit_signal = "-"

    row = {
        "Kode": ticker.replace(".JK", ""),
        "Harga": round(close, 2),
        "Entry Manual": entry if entry > 0 else np.nan,
        "Profit %": round(profit_pct, 2) if not np.isnan(profit_pct) else np.nan,
        "TP 3%": round(tp1, 2) if not np.isnan(tp1) else np.nan,
        "TP 5%": round(tp2, 2) if not np.isnan(tp2) else np.nan,
        "SL -2%": round(stop_loss, 2) if not np.isnan(stop_loss) else np.nan,
        "Trailing Stop": round(trailing_stop, 2) if not np.isnan(trailing_stop) else np.nan,
        "Signal Masuk": signal,
        "Signal Keluar": exit_signal,
        "Status": status,
        "Score": score,
        "RSI": round(rsi_now, 2),
        "RVOL": round(rvol, 2),
        "MACD Hist": round(macd_hist, 4),
        "Change %": round(change_pct, 2),
        "Volume": int(volume)
    }

    return row, df

# =========================
# SIDEBAR
# =========================
st.sidebar.title("⚙️ Scalping Setting")

auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
refresh_sec = st.sidebar.slider("Refresh detik", 10, 300, 60)

if auto_refresh:
    st_autorefresh(interval=refresh_sec * 1000, key="refresh")

ticker_text = st.sidebar.text_area(
    "Watchlist IDX",
    value=", ".join(DEFAULT_TICKERS),
    height=180
)

tickers = [
    x.strip().upper()
    for x in ticker_text.split(",")
    if x.strip()
]

tickers = [
    t if t.endswith(".JK") else t + ".JK"
    for t in tickers
]

st.sidebar.markdown("---")
st.sidebar.subheader("Input Entry Manual")

manual_entries = {}

for t in tickers[:30]:
    code = t.replace(".JK", "")
    manual_entries[t] = st.sidebar.number_input(
        f"Entry {code}",
        min_value=0.0,
        value=0.0,
        step=1.0
    )

# =========================
# HEADER
# =========================
st.markdown("""
<div class="card">
    <div class="big-title">⚡ Scalping Pro Dashboard IDX</div>
    <div class="sub">
        Dashboard scalping dengan entry manual, profit/loss berjalan, TP, SL, trailing stop, dan sinyal keluar.
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# =========================
# SCAN
# =========================
rows = []
chart_data = {}

with st.spinner("Mengambil data saham..."):
    for ticker in tickers:
        row, df = analyze_scalping(ticker, manual_entries.get(ticker, 0))
        if row:
            rows.append(row)
            chart_data[row["Kode"]] = df

if not rows:
    st.error("Data tidak ditemukan. Cek koneksi internet atau ticker IDX.")
    st.stop()

df_result = pd.DataFrame(rows)
df_result = df_result.sort_values(by=["Score", "RVOL", "Change %"], ascending=False)

# =========================
# SUMMARY
# =========================
col1, col2, col3, col4 = st.columns(4)

masuk = len(df_result[df_result["Signal Masuk"] == "MASUK"])
pantau = len(df_result[df_result["Signal Masuk"] == "PANTAU"])
hold = len(df_result[df_result["Signal Keluar"] == "HOLD"])
cutloss = len(df_result[df_result["Signal Keluar"] == "CUT LOSS"])

col1.metric("Entry Kuat", masuk)
col2.metric("Pantau", pantau)
col3.metric("Hold", hold)
col4.metric("Cut Loss", cutloss)

st.write("")

# =========================
# FILTER
# =========================
f1, f2, f3 = st.columns([1, 1, 2])

with f1:
    filter_signal = st.selectbox(
        "Filter Signal",
        ["SEMUA", "MASUK", "PANTAU", "TUNGGU", "HINDARI"]
    )

with f2:
    min_score = st.slider("Minimal Score", 0, 100, 40)

with f3:
    search = st.text_input("Cari kode saham", "")

filtered = df_result.copy()

if filter_signal != "SEMUA":
    filtered = filtered[filtered["Signal Masuk"] == filter_signal]

filtered = filtered[filtered["Score"] >= min_score]

if search:
    filtered = filtered[filtered["Kode"].str.contains(search.upper(), na=False)]

# =========================
# STYLE TABLE
# =========================
def color_signal(val):
    if val == "MASUK":
        return "background-color:#14532d;color:#86efac;font-weight:bold"
    if val == "PANTAU":
        return "background-color:#0c4a6e;color:#7dd3fc;font-weight:bold"
    if val == "TUNGGU":
        return "background-color:#713f12;color:#fde68a;font-weight:bold"
    if val == "HINDARI":
        return "background-color:#7f1d1d;color:#fecaca;font-weight:bold"
    return ""

def color_exit(val):
    if val in ["CUT LOSS", "WASPADA KELUAR"]:
        return "background-color:#7f1d1d;color:#fecaca;font-weight:bold"
    if val in ["TP1 TERCAPAI", "PAKAI TS / AMANKAN PROFIT"]:
        return "background-color:#14532d;color:#86efac;font-weight:bold"
    if val == "HOLD":
        return "background-color:#0c4a6e;color:#7dd3fc;font-weight:bold"
    return ""

def color_profit(val):
    try:
        if val > 0:
            return "color:#22c55e;font-weight:bold"
        if val < 0:
            return "color:#ef4444;font-weight:bold"
    except Exception:
        pass
    return ""

styled = (
    filtered.style
    .map(color_signal, subset=["Signal Masuk"])
    .map(color_exit, subset=["Signal Keluar"])
    .map(color_profit, subset=["Profit %", "Change %"])
    .format({
        "Harga": "{:,.0f}",
        "Entry Manual": "{:,.0f}",
        "Profit %": "{:.2f}%",
        "TP 3%": "{:,.0f}",
        "TP 5%": "{:,.0f}",
        "SL -2%": "{:,.0f}",
        "Trailing Stop": "{:,.0f}",
        "RSI": "{:.2f}",
        "RVOL": "{:.2f}x",
        "Change %": "{:.2f}%",
        "Volume": "{:,.0f}"
    })
)

st.markdown("### 📊 Tabel Scalping Pro")
st.dataframe(styled, use_container_width=True, height=620)

# =========================
# DETAIL CHART
# =========================
st.markdown("### 📈 Detail Chart")

selected = st.selectbox(
    "Pilih saham untuk lihat chart",
    filtered["Kode"].tolist() if not filtered.empty else df_result["Kode"].tolist()
)

df_chart = chart_data.get(selected)

if df_chart is not None:
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_chart.index,
        open=df_chart["Open"],
        high=df_chart["High"],
        low=df_chart["Low"],
        close=df_chart["Close"],
        name="Candlestick"
    ))

    fig.add_trace(go.Scatter(
        x=df_chart.index,
        y=df_chart["MA5"],
        mode="lines",
        name="MA5"
    ))

    fig.add_trace(go.Scatter(
        x=df_chart.index,
        y=df_chart["MA20"],
        mode="lines",
        name="MA20"
    ))

    selected_row = df_result[df_result["Kode"] == selected].iloc[0]

    entry_price = selected_row["Entry Manual"]

    if not pd.isna(entry_price):
        fig.add_hline(
            y=entry_price,
            line_dash="dash",
            annotation_text="Entry Manual"
        )

        fig.add_hline(
            y=selected_row["TP 3%"],
            line_dash="dot",
            annotation_text="TP 3%"
        )

        fig.add_hline(
            y=selected_row["TP 5%"],
            line_dash="dot",
            annotation_text="TP 5%"
        )

        fig.add_hline(
            y=selected_row["SL -2%"],
            line_dash="dot",
            annotation_text="SL -2%"
        )

    fig.update_layout(
        height=520,
        template="plotly_dark",
        paper_bgcolor="#07111f",
        plot_bgcolor="#07111f",
        xaxis_rangeslider_visible=False,
        title=f"Chart Scalping {selected}"
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# FOOTER INFO
# =========================
st.info(
    f"Update terakhir: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    "Data yfinance bisa delay. Untuk scalping real-time penuh sebaiknya pakai data broker/API realtime."
)
