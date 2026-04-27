import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(layout="wide", page_title="Scalping Pro + Volume Detector")

# =========================
# STYLE
# =========================
st.markdown("""
<style>
.stApp {background:#07111f;color:white;}
.card {background:#0d1b2f;padding:16px;border-radius:16px;}
</style>
""", unsafe_allow_html=True)

# =========================
# WATCHLIST
# =========================
DEFAULT_TICKERS = [
"BBCA.JK","BBRI.JK","BMRI.JK","BBNI.JK","TLKM.JK",
"ANTM.JK","MDKA.JK","BRIS.JK","GOTO.JK","BUKA.JK",
"ADRO.JK","AMMN.JK","MEDC.JK","PGAS.JK","INCO.JK"
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
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    hist = macd_line - signal
    return macd_line, signal, hist

def get_data(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="5m", progress=False)
        df = df.dropna()

        df["RSI"] = rsi(df["Close"])
        macd_line, signal, hist = macd(df["Close"])
        df["MACD_HIST"] = hist

        df["VOL_MA"] = df["Volume"].rolling(20).mean()
        df["RVOL"] = df["Volume"] / df["VOL_MA"]

        return df.dropna()
    except:
        return None

# =========================
# LOGIC VOLUME DULU
# =========================
def volume_logic(row):
    score = 0

    if row["RVOL"] >= 2: score += 30
    elif row["RVOL"] >= 1.5: score += 20

    if -1 <= row["Change %"] <= 1.5: score += 25
    elif row["Change %"] <= 3: score += 10

    if 40 <= row["RSI"] <= 60: score += 20
    elif row["RSI"] <= 68: score += 10

    if row["MACD"] > 0: score += 15
    if row["Volume"] > 10_000_000: score += 10

    if score >= 80: status = "AKUMULASI KUAT"
    elif score >= 60: status = "VOLUME MASUK"
    elif score >= 40: status = "PANTAU"
    else: status = "LEMAH"

    return score, status

# =========================
# ANALYZE
# =========================
def analyze(ticker, entry_manual):
    df = get_data(ticker)
    if df is None or len(df) < 30:
        return None, None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    close = float(last["Close"])
    change = ((close - prev["Close"]) / prev["Close"]) * 100

    row = {
        "Kode": ticker.replace(".JK",""),
        "Harga": close,
        "Entry": entry_manual,
        "Change %": change,
        "RSI": last["RSI"],
        "RVOL": last["RVOL"],
        "MACD": last["MACD_HIST"],
        "Volume": int(last["Volume"])
    }

    # ======================
    # PROFIT
    # ======================
    if entry_manual > 0:
        profit = ((close - entry_manual) / entry_manual) * 100
    else:
        profit = np.nan

    row["Profit %"] = profit

    # ======================
    # SIGNAL SCALPING
    # ======================
    score = 0

    if last["RVOL"] > 1.2: score += 20
    if last["MACD_HIST"] > prev["MACD_HIST"]: score += 20
    if 45 <= last["RSI"] <= 65: score += 20
    if close > prev["Close"]: score += 20

    if score >= 60:
        signal = "MASUK"
    elif score >= 40:
        signal = "PANTAU"
    else:
        signal = "TUNGGU"

    row["Signal"] = signal
    row["Score"] = score

    # ======================
    # VOLUME LOGIC
    # ======================
    vol_score, vol_status = volume_logic(row)
    row["Vol Score"] = vol_score
    row["Vol Status"] = vol_status

    return row, df

# =========================
# SIDEBAR
# =========================
st.sidebar.title("⚙️ Setting")

if st.sidebar.checkbox("Auto Refresh", True):
    st_autorefresh(interval=60000)

tickers = st.sidebar.text_area("Watchlist", ",".join(DEFAULT_TICKERS)).split(",")

entries = {}
for t in tickers:
    t = t.strip()
    if t:
        entries[t] = st.sidebar.number_input(f"Entry {t}", 0.0)

# =========================
# SCAN
# =========================
rows = []
charts = {}

for t in tickers:
    t = t.strip()
    if not t:
        continue

    if not t.endswith(".JK"):
        t += ".JK"

    row, df = analyze(t, entries.get(t,0))
    if row:
        rows.append(row)
        charts[row["Kode"]] = df

df = pd.DataFrame(rows)

if df.empty:
    st.stop()

# =========================
# SORTING
# =========================
df = df.sort_values(
    by=["Vol Score","Score","RVOL"],
    ascending=False
)

# =========================
# HEADER
# =========================
st.markdown("## ⚡ Scalping + Volume Detector")

c1,c2,c3 = st.columns(3)
c1.metric("Entry", len(df[df["Signal"]=="MASUK"]))
c2.metric("Volume Masuk", len(df[df["Vol Status"]=="VOLUME MASUK"]))
c3.metric("Akumulasi", len(df[df["Vol Status"]=="AKUMULASI KUAT"]))

# =========================
# TABLE
# =========================
st.dataframe(
    df.style.format({
        "Harga":"{:,.0f}",
        "Profit %":"{:.2f}%",
        "Change %":"{:.2f}%"
    }),
    use_container_width=True,
    height=600
)

# =========================
# CHART
# =========================
kode = st.selectbox("Pilih Saham", df["Kode"])

df_chart = charts.get(kode)

if df_chart is not None:
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_chart.index,
        open=df_chart["Open"],
        high=df_chart["High"],
        low=df_chart["Low"],
        close=df_chart["Close"]
    ))

    st.plotly_chart(fig, use_container_width=True)

# =========================
# FOOTER
# =========================
st.info(
    f"Update: {datetime.now().strftime('%H:%M:%S')} | "
    "Strategi: Volume dulu baru harga (akumulasi bandar)"
)
