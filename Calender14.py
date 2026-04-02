import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Strategy Finder", layout="centered")

# ----------------- UNIVERSE -----------------

@st.cache_data
def load_universe():
    return [
        "SPY","QQQ","DIA","IWM","VTI","VOO",
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA",
        "AMD","INTC","CRM","ORCL","ADBE","CSCO","NOW",
        "JPM","BAC","GS","MS","C","WFC",
        "WMT","COST","HD","LOW","NKE","SBUX","MCD",
        "JNJ","UNH","PFE","MRK","ABBV","TMO",
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

# ----------------- REGIME DETECTION -----------------

def detect_regime(adx, rsi, atr_pct):

    if adx < 25 and 40 <= rsi <= 60:
        return "NEUTRAL"

    elif adx >= 25:
        return "TRENDING"

    elif atr_pct > 2.5:
        return "VOLATILE"

    return "NEUTRAL"

# ----------------- STRATEGY MAPPING -----------------

def suggest_strategies(regime, bb_position):

    if regime == "NEUTRAL":

        if 0.3 < bb_position < 0.7:
            return ["Credit Spread", "Iron Condor", "Calendar Spread"]
        elif bb_position <= 0.3:
            return ["Bull Put Spread", "Put Credit Spread"]
        elif bb_position >= 0.7:
            return ["Bear Call Spread", "Call Credit Spread"]

    elif regime == "TRENDING":
        return ["Pullback Trade", "Breakout", "Debit Spread"]

    elif regime == "VOLATILE":
        return ["Straddle", "Strangle", "Long Options"]

    return ["Watch"]

# ----------------- BB POSITION -----------------

def get_bb_position(price, bb_low, bb_high):
    if bb_high - bb_low == 0:
        return 0.5
    return (price - bb_low) / (bb_high - bb_low)

# ----------------- UI -----------------

st.title("🧠 Strategy Finder Scanner")

max_scan = st.slider("Max tickers to scan", 50, 200, 100)

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
            rsi = last["RSI"]
            adx = last["ADX"]
            atr = last["ATR"]

            atr_pct = (atr / price) * 100
            bb_low = last["BB_Low"]
            bb_high = last["BB_High"]

            bb_position = get_bb_position(price, bb_low, bb_high)

            regime = detect_regime(adx, rsi, atr_pct)

            strategies = suggest_strategies(regime, bb_position)

            results.append({
                "Ticker": ticker,
                "Price": round(price, 2),
                "Regime": regime,
                "Strategies": ", ".join(strategies),
                "RSI": round(rsi, 1),
                "ADX": round(adx, 1),
                "BB Position": round(bb_position, 2),
                "ATR %": round(atr_pct, 2)
            })

        except:
            continue

        progress.progress((i + 1) / len(universe))

    if results:
        df_results = pd.DataFrame(results)

        # ---------------- FILTER UI ----------------

        st.subheader("🔎 Filters")

        regime_filter = st.selectbox(
            "Filter by Regime",
            ["ALL", "NEUTRAL", "TRENDING", "VOLATILE"]
        )

        strategy_filter = st.text_input("Search Strategy (e.g. Iron Condor)")

        if regime_filter != "ALL":
            df_results = df_results[df_results["Regime"] == regime_filter]

        if strategy_filter:
            df_results = df_results[
                df_results["Strategies"].str.contains(strategy_filter, case=False)
            ]

        st.subheader("📊 Strategy Candidates")

        st.dataframe(df_results.sort_values(by="BB Position"), hide_index=True)

    else:
        st.warning("No results found.")