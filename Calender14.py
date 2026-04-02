import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Trading Engine Scanner + Strategy", layout="centered")

# ----------------- UNIVERSE -----------------

@st.cache_data
def load_universe():
    return [
        "SPY","QQQ","DIA","IWM","VTI","VOO","IVV",
        "XLF","XLV","XLE","XLK","XLY","XLI","XLP","XLU",
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA",
        "AMD","INTC","CRM","ORCL","ADBE","CSCO","NOW",
        "JPM","BAC","GS","MS","C","WFC",
        "WMT","COST","HD","LOW","NKE","SBUX","MCD",
        "JNJ","UNH","PFE","MRK","ABBV","TMO","DHR",
        "NEE","DUK","SO","AEP","EXC",
        "XOM","CVX","COP","EOG","SLB"
    ]

# ----------------- INDICATORS -----------------

def compute_indicators(df):
    df = df.copy()

    df["RSI"] = RSIIndicator(df["Close"]).rsi()
    df["ADX"] = ADXIndicator(df["High"], df["Low"], df["Close"]).adx()
    df["ATR"] = AverageTrueRange(df["High"], df["Low"], df["Close"]).average_true_range()

    bb = BollingerBands(df["Close"])
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Low"] = bb.bollinger_lband()
    df["BB_Mid"] = bb.bollinger_mavg()

    vwap = VolumeWeightedAveragePrice(
        df["High"], df["Low"], df["Close"], df["Volume"]
    )
    df["VWAP"] = vwap.volume_weighted_average_price()

    return df

# ----------------- STRATEGY LOGIC -----------------

def strategy_setup(last):

    price = last["Close"]
    rsi = last["RSI"]
    adx = last["ADX"]
    bb_high = last["BB_High"]
    bb_low = last["BB_Low"]
    bb_mid = last["BB_Mid"]
    vwap = last["VWAP"]
    atr = last["ATR"]

    # Defaults
    setup = "WAIT"
    entry = None
    stop = None
    target = None
    confidence = 0

    # Range condition
    if adx < 25:

        # ---------------- LONG ----------------
        if price <= bb_low and rsi < 45:

            setup = "LONG"

            entry = price
            stop = price - (1.2 * atr)
            target = bb_mid if price < bb_mid else vwap

            confidence = (50 - rsi) + (bb_mid - price)

        # ---------------- SHORT ----------------
        elif price >= bb_high and rsi > 55:

            setup = "SHORT"

            entry = price
            stop = price + (1.2 * atr)
            target = bb_mid if price > bb_mid else vwap

            confidence = (rsi - 50) + (price - bb_mid)

    return setup, entry, stop, target, confidence

# ----------------- UI -----------------

st.title("📊 Trading Scanner + Strategy Engine")

max_scan = st.slider("Max tickers to scan", 50, 300, 150)

if st.button("Run Scan"):

    universe = load_universe()[:max_scan]

    results = []

    progress = st.progress(0)

    for i, ticker in enumerate(universe):

        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)

            if df.empty or len(df) < 50:
                continue

            df = compute_indicators(df)
            last = df.iloc[-1]

            price = last["Close"]

            # Strategy
            setup, entry, stop, target, confidence = strategy_setup(last)

            # Filter: only show meaningful setups
            if setup == "WAIT":
                continue

            results.append({
                "Ticker": ticker,
                "Setup": setup,
                "Price": round(price, 2),
                "Entry": round(entry, 2) if entry else None,
                "Stop": round(stop, 2) if stop else None,
                "Target": round(target, 2) if target else None,
                "Confidence": round(confidence, 2)
            })

        except:
            continue

        progress.progress((i + 1) / len(universe))

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Confidence", ascending=False)
        df_results = df_results.reset_index(drop=True)
        df_results.insert(0, "Rank", df_results.index + 1)

        st.subheader("🎯 Active Trade Setups")
        st.dataframe(df_results, hide_index=True)
    else:
        st.warning("No setups found.")