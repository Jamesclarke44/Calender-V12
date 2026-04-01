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
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    # ATR
    high_low = df["High"] - df["Low"]
    high_close = np.abs(df["High"] - df["Close"].shift())
    low_close = np.abs(df["Low"] - df["Close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(14).mean()

    # VWAP (approx using typical price)
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    df["VWAP"] = tp.rolling(20).mean()

    # ADX (simplified approximation)
    plus_dm = df["High"].diff()
    minus_dm = df["Low"].diff()

    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0

    tr14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / tr14)
    minus_di = 100 * (minus_dm.abs().rolling(14).mean() / tr14)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    df["ADX"] = dx.rolling(14).mean()

    return df

# -----------------------------
# DECISION ENGINE
# -----------------------------
def decision_engine(adx, rsi, vwap_drift, atr_pct):
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
# SCAN BUTTON
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
        rsi = last["RSI"]
        adx = last["ADX"]
        atr = last["ATR"]
        vwap = last["VWAP"]

        sma50 = last["SMA50"]
        sma200 = last["SMA200"]

        if pd.isna(price):
            continue

        atr_pct = (atr / price) * 100 if price else 0
        vwap_drift = abs(price - vwap) / price if price else 0

        decision, reason = decision_engine(adx, rsi, vwap_drift, atr_pct)
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

        # Sort best setups first
        df_results = df_results.sort_values(
            by=["Decision", "Score"],
            ascending=[True, False]
        )

        # Highlight function
        def highlight(row):
            if row["Decision"] == "GO":
                return ["background-color: lightgreen"] * len(row)
            elif row["Decision"] == "CAUTION":
                return ["background-color: lightyellow"] * len(row)
            return [""] * len(row)

        st.subheader("📊 Scan Results (Ranked)")

        st.dataframe(df_results.style.apply(highlight, axis=1))

    else:
        st.write("No valid data returned.")