import streamlit as st
import math
import time
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Trading Engine Lite", layout="centered")

# ----------------- FUNCTIONS -----------------

def fetch_data(ticker):
    df = yf.download(ticker, period="6mo", interval="1d")
    if df.empty:
        return None
    return df

def compute_indicators(df):
    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df = df.dropna()

    df["RSI"] = RSIIndicator(df["Close"]).rsi()
    df["ADX"] = ADXIndicator(df["High"], df["Low"], df["Close"]).adx()
    df["ATR"] = AverageTrueRange(df["High"], df["Low"], df["Close"]).average_true_range()

    bb = BollingerBands(df["Close"])
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Low"] = bb.bollinger_lband()

    vwap = VolumeWeightedAveragePrice(
        df["High"], df["Low"], df["Close"], df["Volume"]
    )
    df["VWAP"] = vwap.volume_weighted_average_price()

    df["SMA50"] = df["Close"].rolling(50).mean()
    df["SMA200"] = df["Close"].rolling(200).mean()

    return df

# ----------------- LOGIC -----------------

def get_bias(price, sma50, sma200, rsi, vwap):
    score = 0

    score += 1 if price > sma50 else -1
    score += 1 if sma50 > sma200 else -1

    if rsi > 55:
        score += 1
    elif rsi < 45:
        score -= 1

    score += 1 if price > vwap else -1

    if score >= 2:
        return "BULLISH"
    elif score <= -2:
        return "BEARISH"
    return "NEUTRAL"

def get_regime(adx, atr_pct):
    if adx < 20 and atr_pct < 2:
        return "RANGE (IDEAL)"
    elif adx < 25:
        return "TRANSITION"
    return "TRENDING"

def decision_engine(adx, rsi, vwap_drift, atr_pct):
    if adx > 25:
        return "NO GO", "Trending market"
    if rsi < 40 or rsi > 60:
        return "NO GO", "Momentum not neutral"
    if vwap_drift > 0.01:
        return "NO GO", "Too far from VWAP"
    if atr_pct > 2.5:
        return "NO GO", "Volatility too high"

    return "GO", "Clean neutral environment"

# ----------------- UI -----------------

st.title("📊 Trading Engine Lite")

ticker = st.text_input("Ticker", value="SPY").upper()

auto = st.checkbox("Auto Refresh (60s)", value=True)

run = st.button("Run") if not auto else True

if run and ticker:

    df = fetch_data(ticker)

    if df is None:
        st.error("Invalid ticker")
    else:
        df = compute_indicators(df)
        last = df.iloc[-1]

        price = last["Close"]
        rsi = last["RSI"]
        adx = last["ADX"]
        atr = last["ATR"]
        vwap = last["VWAP"]

        sma50 = last["SMA50"]
        sma200 = last["SMA200"]

        atr_pct = (atr / price) * 100
        vwap_drift = abs(price - vwap) / price

        # --- CORE OUTPUT ---

        decision, reason = decision_engine(adx, rsi, vwap_drift, atr_pct)
        bias = get_bias(price, sma50, sma200, rsi, vwap)
        regime = get_regime(adx, atr_pct)

        st.subheader(f"{ticker} — {price:.2f}")

        if decision == "GO":
            st.success("GO ✅")
        else:
            st.error("NO GO ⛔")

        st.write(reason)

        st.markdown("---")

        st.subheader("🧭 Direction")
        st.write(bias)

        st.subheader("🌎 Regime")
        st.write(regime)

        st.markdown("---")

        st.subheader("📊 Indicators")
        st.write(f"RSI: {rsi:.1f}")
        st.write(f"ADX: {adx:.1f}")
        st.write(f"ATR %: {atr_pct:.2f}%")
        st.write(f"VWAP Drift: {vwap_drift*100:.2f}%")

# ----------------- AUTO REFRESH -----------------

if auto:
    time.sleep(60)
    st.rerun()