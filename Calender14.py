import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

# -----------------------------
# APP TITLE
# -----------------------------
st.title("📊 Market Scanner (Neutral Setups)")

# -----------------------------
# UNIVERSAL WATCHLIST
# -----------------------------
@st.cache_data
def load_universe():
    return [
        # ETFs
        "SPY","QQQ","DIA","IWM","VTI","XLF","XLV","XLE","XLK","XLY","XLU",

        # Large Cap Stocks
        "AAPL","MSFT","NVDA","TSLA","AMZN","META","GOOGL","BRK-B",
        "JPM","BAC","WMT","UNH","HD","LLY","XOM","COST","AVGO","NFLX"
    ]

universe = load_universe()

st.write(f"Scanning {len(universe)} symbols...")

# -----------------------------
# DATA FETCH
# -----------------------------
def fetch_data(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df is not None and not df.empty:
            df.reset_index(inplace=True)
        return df
    except Exception:
        return None

# -----------------------------
# INDICATORS
# -----------------------------
def compute_indicators(df):
    df = df.copy()

    # Moving averages
    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # ATR
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Close"].shift()).abs()
    tr3 = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # VWAP (approx)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = tp.rolling(20).mean()

    # ADX (clean implementation)
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr = tr.rolling(14).mean()

    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)

    plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(14).mean()

    # Ensure 1-D numeric Series
    df["ADX"] = pd.to_numeric(adx, errors="coerce")

    return df

# -----------------------------
# SCANNER LOGIC
# -----------------------------
def is_neutral(adx, rsi, vwap_drift):
    return (
        adx < 25 and
        45 <= rsi <= 55 and
        vwap_drift < 0.01
    )

# -----------------------------
# SCAN BUTTON
# -----------------------------
if st.button("Run Scan"):

    results = []

    progress_bar = st.progress(0)
    total = len(universe)

    for i, ticker in enumerate(universe):

        df = fetch_data(ticker)

        if df is None or df.empty:
            progress_bar.progress((i + 1) / total)
            continue

        df = compute_indicators(df)
        last = df.iloc[-1]

        price = last["Close"]

        if pd.isna(price):
            progress_bar.progress((i + 1) / total)
            continue

        rsi = last["RSI"]
        adx = last["ADX"]
        atr = last["ATR"]
        vwap = last["VWAP"]

        sma50 = last["SMA50"]
        sma200 = last["SMA200"]

        if pd.isna(adx) or pd.isna(rsi) or pd.isna(vwap):
            progress_bar.progress((i + 1) / total)
            continue

        vwap_drift = abs(price - vwap) / price if price else 0

        if is_neutral(adx, rsi, vwap_drift):

            neutral_score = (
                (25 - adx) +
                (1 - abs(rsi - 50) / 50) * 10 +
                (1 - vwap_drift) * 10
            )

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "RSI": round(rsi, 2),
                "ADX": round(adx, 2),
                "VWAP Drift": round(vwap_drift, 4),
                "Score": round(neutral_score, 2)
            })

        progress_bar.progress((i + 1) / total)

    # -----------------------------
    # DISPLAY RESULTS
    # -----------------------------
    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Score", ascending=False)

        st.subheader("🎯 Neutral Market Setups")
        st.dataframe(df_results)

    else:
        st.write("No neutral setups found.")
