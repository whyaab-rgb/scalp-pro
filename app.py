import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Scalping Pro IDX",
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
}
.big-title {
    font-size: 30px;
    font-weight: 800;
}
.sub {
    color: #9fb3c8;
}
</style>
""", unsafe_allow_html=True)

# =========================
# ALL IDX TICKERS
# =========================
IDX_CODES = """
AALI ABBA ABDA ABMM ACES ACST ADCP ADES ADHI ADMF ADMG ADMR ADRO AGII AGRO AHAP
AISA AKRA AKSI ALDO AMAG AMFG AMMN AMRT ANJT ANTM APLN ARCI ARGO ARII ARNA ARTO
ASGR ASII ASRI ASSA AUTO AVIA BACA BALI BANK BAPA BBCA BBHI BBKP BBLD BBNI BBRI
BBTN BBYB BCAP BDMN BEBS BEEF BFIN BGTG BHIT BIKA BIRD BJBR BJTM BKSL BMRI BMTR
BNBA BNGA BNII BNLI BOBA BOLT BRIS BRMS BRPT BSDE BSSR BTON BUKA BULL BUMI BYAN
CARS CASA CBUT CFIN CLEO CMRY CPIN CTRA DEWA DILD DMMX DMAS DOID DSNG DSSA EMTK
ENRG ERAA ESSA EXCL FILM FIRE FREN GGRM GJTL GOTO HEAL HMSP HRUM ICBP INCO INDF
INDY INKP INTP IPTV ISAT ITMG JPFA JSMR KAEF KIJA KLBF KPIG LSIP MAIN MAPA MAPI
MARK MBMA MDKA MEDC MIDI MIKA MNCN MTEL MYOR NCKL NISP PGAS PGEO PNBN PNBS PNLF
POWR PRDA PSAB PTBA PTPP PWON RAJA RALS SAME SCMA SIDO SILO SIMP SMGR SMRA SRTG
SSIA SSMS TBIG TINS TKIM TLKM TOWR TPIA UNTR UNVR WIKA WSKT WTON
""".split()

ALL_IDX_TICKERS = sorted(list(set([x.strip().upper() + ".JK" for x in IDX_CODES if x.strip()])))

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

def get_data(ticker):
    try:
        df = yf.download(
            ticker,
            period="5d",
            interval="5m",
            progress=False,
            auto_adjust=True
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.dropna()

        df["RSI"] = rsi(df["Close"])
        macd_line, signal, hist = macd(df["Close"])
        df["MACD"] = macd_line
        df["MACD_SIGNAL"] = signal
        df["MACD_HIST"] = hist
        df["MA5"] = df["Close"].rolling(5).mean()
        df["MA20"] = df["Close"].rolling(20).mean()
        df["VOL_MA20"] = df["Volume"].rolling(20).mean()
        df["RVOL"] = df["Volume"] / df["VOL_MA20"]

        return df.dropna()
    except Exception:
        return None

# =========================
# LOGIC VOLUME BEFORE PRICE
# =========================
def volume_before_price_logic(row):
    score = 0
    alasan = []

    if row["RVOL"] >= 2:
        score += 30
        alasan.append("RVOL sangat tinggi")
    elif row["RVOL"] >= 1.5:
        score += 20
        alasan.append("RVOL tinggi")

    if -1 <= row["Change %"] <= 1.5:
        score += 25
        alasan.append("Harga belum naik jauh")
    elif 1.5 < row["Change %"] <= 3:
        score += 10
        alasan.append("Harga mulai naik")

    if 40 <= row["RSI"] <= 60:
        score += 20
        alasan.append("RSI sehat")
    elif 60 < row["RSI"] <= 68:
        score += 10
        alasan.append("RSI masih aman")

    if row["MACD Hist"] > 0:
        score += 15
        alasan.append("MACD positif")

    if row["Volume"] >= 10_000_000:
        score += 10
        alasan.append("Volume besar")

    if score >= 80:
        status = "AKUMULASI KUAT"
    elif score >= 60:
        status = "VOLUME MASUK"
    elif score >= 40:
        status = "PANTAU"
    else:
        status = "LEMAH"

    return score, status, ", ".join(alasan)

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
    prev_close = float(prev["Close"])
    change = ((close - prev_close) / prev_close) * 100

    rsi_now = float(last["RSI"])
    rvol = float(last["RVOL"])
    macd_hist = float(last["MACD_HIST"])
    prev_macd_hist = float(prev["MACD_HIST"])
    ma5 = float(last["MA5"])
    ma20 = float(last["MA20"])
    volume = int(last["Volume"])

    entry_manual = float(entry_manual)

    if entry_manual > 0:
        profit_pct = ((close - entry_manual) / entry_manual) * 100
        tp3 = entry_manual * 1.03
        tp5 = entry_manual * 1.05
        sl2 = entry_manual * 0.98
        trailing_stop = close * 0.985
    else:
        profit_pct = np.nan
        tp3 = np.nan
        tp5 = np.nan
        sl2 = np.nan
        trailing_stop = np.nan

    score = 0

    if rvol >= 1.2:
        score += 20
    if macd_hist > prev_macd_hist:
        score += 20
    if 45 <= rsi_now <= 65:
        score += 20
    if close > prev_close:
        score += 20
    if ma5 > ma20:
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

    if entry_manual > 0:
        if close <= sl2:
            exit_signal = "CUT LOSS"
        elif profit_pct >= 5:
            exit_signal = "PAKAI TS"
        elif profit_pct >= 3:
            exit_signal = "TP1"
        elif macd_hist < prev_macd_hist and profit_pct > 0:
            exit_signal = "WASPADA KELUAR"
        else:
            exit_signal = "HOLD"
    else:
        exit_signal = "-"

    row = {
        "Kode": ticker.replace(".JK", ""),
        "Harga": round(close, 2),
        "Entry Manual": entry_manual if entry_manual > 0 else np.nan,
        "Profit %": round(profit_pct, 2) if not np.isnan(profit_pct) else np.nan,
        "TP 3%": round(tp3, 2) if not np.isnan(tp3) else np.nan,
        "TP 5%": round(tp5, 2) if not np.isnan(tp5) else np.nan,
        "SL -2%": round(sl2, 2) if not np.isnan(sl2) else np.nan,
        "Trailing Stop": round(trailing_stop, 2) if not np.isnan(trailing_stop) else np.nan,
        "Signal Masuk": signal,
        "Signal Keluar": exit_signal,
        "Status": status,
        "Score Scalping": score,
        "RSI": round(rsi_now, 2),
        "RVOL": round(rvol, 2),
        "MACD Hist": round(macd_hist, 4),
        "Change %": round(change, 2),
        "Volume": volume
    }

    vol_score, vol_status, alasan = volume_before_price_logic(row)
    row["Vol Score"] = vol_score
    row["Vol Status"] = vol_status
    row["Alasan"] = alasan

    return row, df

# =========================
# SIDEBAR
# =========================
st.sidebar.title("⚙️ Scalping Setting")

auto_refresh = st.sidebar.checkbox("Auto Refresh", value=True)
refresh_sec = st.sidebar.slider("Refresh Detik", 10, 300, 60)

if auto_refresh:
    st_autorefresh(interval=refresh_sec * 1000, key="refresh")

st.sidebar.markdown("### 🔎 Search Semua IDX")

search_ticker = st.sidebar.text_input(
    "Cari emiten",
    placeholder="Contoh: BBRI, GOTO, ANTM"
).upper().strip()

max_scan = st.sidebar.slider(
    "Jumlah maksimal scan",
    min_value=10,
    max_value=200,
    value=50,
    step=10
)

if search_ticker:
    scan_tickers = [
        t for t in ALL_IDX_TICKERS
        if search_ticker in t.replace(".JK", "")
    ]
else:
    scan_tickers = ALL_IDX_TICKERS[:max_scan]

manual_extra = st.sidebar.text_area(
    "Tambah ticker manual",
    placeholder="Contoh: BBRI.JK, GOTO.JK, ANTM.JK"
)

extra_tickers = []
if manual_extra.strip():
    for x in manual_extra.split(","):
        x = x.strip().upper()
        if x:
            if not x.endswith(".JK"):
                x += ".JK"
            extra_tickers.append(x)

scan_tickers = sorted(list(set(scan_tickers + extra_tickers)))
scan_tickers = scan_tickers[:max_scan] if not search_ticker else scan_tickers

st.sidebar.caption(f"Ticker discan: {len(scan_tickers)}")

st.sidebar.markdown("### 💰 Entry Manual")

entries = {}

for t in scan_tickers[:80]:
    code = t.replace(".JK", "")
    entries[t] = st.sidebar.number_input(
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
    <div class="big-title">⚡ Scalping Pro IDX + Volume Before Price</div>
    <div class="sub">
        Cari saham dengan volume tinggi, harga belum naik jauh, entry manual, profit berjalan, TP, SL, trailing stop, dan sinyal keluar.
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# =========================
# SCAN
# =========================
rows = []
charts = {}

with st.spinner(f"Scan {len(scan_tickers)} ticker IDX..."):
    for t in scan_tickers:
        row, df_chart = analyze(t, entries.get(t, 0))
        if row:
            rows.append(row)
            charts[row["Kode"]] = df_chart

df = pd.DataFrame(rows)

if df.empty:
    st.warning("Belum ada data. Coba cari ticker lain atau kurangi jumlah scan.")
    st.stop()

# =========================
# SORT
# =========================
df = df.sort_values(
    by=["Vol Score", "Score Scalping", "RVOL", "Volume"],
    ascending=[False, False, False, False]
)

# =========================
# SUMMARY
# =========================
c1, c2, c3, c4 = st.columns(4)

c1.metric("Entry Kuat", len(df[df["Signal Masuk"] == "MASUK"]))
c2.metric("Volume Masuk", len(df[df["Vol Status"] == "VOLUME MASUK"]))
c3.metric("Akumulasi Kuat", len(df[df["Vol Status"] == "AKUMULASI KUAT"]))
c4.metric("Total Scan", len(df))

# =========================
# FILTER
# =========================
f1, f2, f3 = st.columns([1, 1, 2])

with f1:
    filter_status = st.selectbox(
        "Filter Volume Status",
        ["SEMUA", "AKUMULASI KUAT", "VOLUME MASUK", "PANTAU", "LEMAH"]
    )

with f2:
    min_score = st.slider("Minimal Vol Score", 0, 100, 40)

with f3:
    search_table = st.text_input("Cari di tabel", placeholder="Contoh: BBRI")

filtered = df.copy()

if filter_status != "SEMUA":
    filtered = filtered[filtered["Vol Status"] == filter_status]

filtered = filtered[filtered["Vol Score"] >= min_score]

if search_table:
    filtered = filtered[filtered["Kode"].str.contains(search_table.upper(), na=False)]

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

def color_volume_status(val):
    if val == "AKUMULASI KUAT":
        return "background-color:#14532d;color:#86efac;font-weight:bold"
    if val == "VOLUME MASUK":
        return "background-color:#0c4a6e;color:#7dd3fc;font-weight:bold"
    if val == "PANTAU":
        return "background-color:#713f12;color:#fde68a;font-weight:bold"
    if val == "LEMAH":
        return "background-color:#7f1d1d;color:#fecaca;font-weight:bold"
    return ""

def color_exit(val):
    if val in ["CUT LOSS", "WASPADA KELUAR"]:
        return "background-color:#7f1d1d;color:#fecaca;font-weight:bold"
    if val in ["TP1", "PAKAI TS"]:
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
    .map(color_volume_status, subset=["Vol Status"])
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
        "MACD Hist": "{:.4f}",
        "Change %": "{:.2f}%",
        "Volume": "{:,.0f}"
    })
)

st.markdown("### 📊 Tabel Scalping + Volume Before Price")
st.dataframe(styled, use_container_width=True, height=620)

# =========================
# CHART
# =========================
st.markdown("### 📈 Detail Chart")

if filtered.empty:
    st.warning("Tidak ada data sesuai filter.")
    st.stop()

selected = st.selectbox("Pilih Saham", filtered["Kode"].tolist())

df_chart = charts.get(selected)

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

    row = df[df["Kode"] == selected].iloc[0]

    if not pd.isna(row["Entry Manual"]):
        fig.add_hline(y=row["Entry Manual"], line_dash="dash", annotation_text="Entry")
        fig.add_hline(y=row["TP 3%"], line_dash="dot", annotation_text="TP 3%")
        fig.add_hline(y=row["TP 5%"], line_dash="dot", annotation_text="TP 5%")
        fig.add_hline(y=row["SL -2%"], line_dash="dot", annotation_text="SL -2%")
        fig.add_hline(y=row["Trailing Stop"], line_dash="dot", annotation_text="Trailing Stop")

    fig.update_layout(
        height=520,
        template="plotly_dark",
        paper_bgcolor="#07111f",
        plot_bgcolor="#07111f",
        xaxis_rangeslider_visible=False,
        title=f"Chart {selected}.JK - 5 Menit"
    )

    st.plotly_chart(fig, use_container_width=True)

# =========================
# FOOTER
# =========================
st.info(
    f"Update terakhir: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    "Data yfinance bisa delay. Untuk scalping real-time penuh sebaiknya pakai data broker/API realtime."
)
