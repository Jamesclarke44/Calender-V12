import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

# -----------------------------
# APP TITLE
# -----------------------------
st.title("📊 Smart Multi-Ticker Scanner")

# -----------------------------
# INPUT
# -----------------------------
tickers_input = st.text_input(
    "Enter tickers (comma separated)",
    "SPY,QQQ,DIA"
).upper()

ticker_list = [t.strip() for t in tickers_input.split(",") if t.strip()]

# -----------------------------
# DATA FETCH
# -----------------------------
def fetch_data(ticker):
    df = yf.download(ticker, period="6mo", interval="1d", progress=False)
    df.reset_index(inplace=True)
    return df

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

    # VWAP (rolling approximation)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = tp.rolling(20).mean()

    # -----------------------------
    # ADX (ROBUST + SAFE)
    # -----------------------------
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    # True Range
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Directional Movement
    plus_dm = high.diff()
    minus_dm = low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # ATR smoothing
    atr = tr.rolling(14).mean()

    # DI calculations
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)

    # DX
    dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100
    dx = dx.replace([np.inf, -np.inf], np.nan)

    # ADX
    adx = dx.rolling(14).mean()

    # Assign safely
    df["ADX"] = adx

    return df

# -----------------------------
# DECISION ENGINE
# -----------------------------
def decision_engine(adx, rsi, vwap_drift):
    if adx < 25 and 45 <= rsi <= 55 and vwap_drift < 0.01:
        return "GO", "Range + neutral conditions"
    elif adx >= 25:
        return "CAUTION", "Trending market"
    return "NO GO", "No clear edge"

def get_bias(price, sma50, sma200):
    if price > sma50 and sma50 > sma200:
        return "Bullish"
    elif price < sma50 and sma50 < sma200:
        return "Bearish"
    return "Neutral"

def get_regime(adx):
    if adx > 25:
        return "Trending"
    return "Range"

# -----------------------------
# SCORING SYSTEM
# -----------------------------
def score_setup(adx, rsi, vwap_drift, atr_pct):
    score = 0

    if adx < 20:
        score += 2
    elif adx < 25:
        score += 1

    if 45 <= rsi <= 55:
        score += 2
    elif 40 <= rsi <= 60:
        score += 1

    if vwap_drift < 0.005:
        score += 2
    elif vwap_drift < 0.01:
        score += 1

    if atr_pct < 2:
        score += 2
    elif atr_pct < 3:
        score += 1

    return score

# -----------------------------
# SCAN
# -----------------------------
if st.button("Run Scan"):

    results = []

    for ticker in ticker_list:
        df = fetch_data(ticker)

        if df is None or df.empty:
            continue

        df = compute_indicators(df)
        last = df.iloc[-1]

        price = last["Close"]

        if pd.isna(price):
            continue

        rsi = last["RSI"]
        adx = last["ADX"]
        atr = last["ATR"]
        vwap = last["VWAP"]

        sma50 = last["SMA50"]
        sma200 = last["SMA200"]

        atr_pct = (atr / price) * 100 if price else 0
        vwap_drift = abs(price - vwap) / price if price else 0

        decision, reason = decision_engine(adx, rsi, vwap_drift)
        bias = get_bias(price, sma50, sma200)
        regime = get_regime(adx)
        score = score_setup(adx, rsi, vwap_drift, atr_pct)

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Decision": decision,
            "Bias": bias,
            "Regime": regime,
            "Score": score,
            "RSI": round(rsi, 2) if not pd.isna(rsi) else None,
            "ADX": round(adx, 2) if not pd.isna(adx) else None,
            "Reason": reason
        })

    if results:
        df_results = pd.DataFrame(results)

        # Sort: GO first, then highest score
        df_results = df_results.sort_values(
            by=["Decision", "Score"],
            ascending=[True, False]
        )

        # Highlight rows
        def highlight(row):
            if row["Decision"] == "GO":
                return ["background-color: lightgreen"] * len(row)
            elif row["Decision"] == "CAUTION":
                return ["background-color: lightyellow"] * len(row)
            return [""] * len(row)

        st.subheader("📊 Scan Results (Ranked)")
        st.dataframe(df_results.style.apply(highlight, axis=1))

    else:
        st.write("No valid results returned.")