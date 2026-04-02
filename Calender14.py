import streamlit as st
import math
import time
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Trading Engine Scanner", layout="centered")

# ----------------- UNIVERSE -----------------

@st.cache_data
def load_universe():
    return [
        "SPY","QQQ","DIA","IWM","VTI",
        "XLF","XLV","XLE","XLK","XLY","XLI","XLP","XLU","XLB","XLRE",
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","BRK-B",
        "AVGO","NFLX","AMD","INTC","CRM","ORCL","ADBE","CSCO",
        "JPM","BAC","GS","MS","C","WFC","SCHW","BLK",
        "WMT","COST","HD","LOW","NKE","SBUX","MCD","TGT",
        "UNH","LLY","JNJ","PFE","MRK","ABBV","TMO","DHR",
        "XOM","CVX","COP","SLB","EOG","OXY",
        "CAT","DE","GE","HON","BA","UPS","FDX",
        "DIS","CMCSA","TMUS","VZ","T",
        "PYPL","SQ","SHOP","UBER","LYFT","SNAP","ROKU",
        "PLTR","COIN","RIOT","MARA","SOFI",
        "SHOP.TO","RY.TO","TD.TO","ENB.TO","BNS.TO"
    ]

# ----------------- S&P 500 -----------------

@st.cache_data
def load_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    table = tables[0]

    tickers = table["Symbol"].tolist()
    tickers = [t.replace(".", "-") for t in tickers]

    return tickers

# ----------------- DATA -----------------

def fetch_data(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False, threads=False)
        if df is None or df.empty:
            return None
        return df
    except:
        return None

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

def decision_engine(adx, rsi, vwap_drift, atr_pct, bb_position):

    if adx > 25:
        return "NO GO", "Trending market"

    if rsi < 40 or rsi > 60:
        return "NO GO", "Momentum not neutral"

    if vwap_drift > 0.01:
        return "NO GO", "Too far from VWAP"

    if atr_pct > 2.5:
        return "NO GO", "Volatility too high"

    # Bollinger Band neutrality (40–60%)
    if bb_position < 0.4 or bb_position > 0.6:
        return "NO GO", "Price not centered in Bollinger Bands"

    return "GO", "All conditions aligned"

# ----------------- UI -----------------

st.title("📊 Trading Engine Scanner")

mode = st.radio("Mode", ["Single Ticker", "Market Scan"])

# ----------------- SINGLE -----------------

if mode == "Single Ticker":

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

            bb_range = last["BB_High"] - last["BB_Low"]

            if bb_range == 0 or pd.isna(bb_range):
                bb_position = 0.5
            else:
                bb_position = (price - last["BB_Low"]) / bb_range

            decision, reason = decision_engine(adx, rsi, vwap_drift, atr_pct, bb_position)
            bias = get_bias(price, sma50, sma200, rsi, vwap)
            regime = get_regime(adx, atr_pct)

            st.subheader(f"{ticker} — {price:.2f}")

            if decision == "GO":
                st.success("GO ✅")
            else:
                st.error("NO GO ⛔")

            st.write(reason)

            st.subheader("🧭 Direction")
            st.write(bias)

            st.subheader("🌎 Regime")
            st.write(regime)

            st.subheader("📊 Indicators")
            st.write(f"RSI: {rsi:.1f}")
            st.write(f"ADX: {adx:.1f}")
            st.write(f"ATR %: {atr_pct:.2f}%")
            st.write(f"VWAP Drift: {vwap_drift*100:.2f}%")
            st.write(f"BB Position: {bb_position:.2f}")

# ----------------- MARKET SCAN -----------------

if mode == "Market Scan":

    universe_choice = st.selectbox(
        "Universe",
        ["Custom Universe", "S&P 500"]
    )

    if st.button("Run Market Scan"):

        if universe_choice == "S&P 500":
            universe = load_sp500()
        else:
            universe = load_universe()

        results = []
        progress = st.progress(0)

        for i, ticker in enumerate(universe):

            df = fetch_data(ticker)

            if df is None or len(df) < 50:
                continue

            df = compute_indicators(df)
            last = df.iloc[-1]

            price = last["Close"]
            rsi = last["RSI"]
            adx = last["ADX"]
            atr = last["ATR"]
            vwap = last["VWAP"]

            if pd.isna(adx) or pd.isna(rsi):
                continue

            atr_pct = (atr / price) * 100
            vwap_drift = abs(price - vwap) / price

            bb_range = last["BB_High"] - last["BB_Low"]

            if bb_range == 0 or pd.isna(bb_range):
                bb_position = 0.5
            else:
                bb_position = (price - last["BB_Low"]) / bb_range

            decision, _ = decision_engine(adx, rsi, vwap_drift, atr_pct, bb_position)

            if decision == "GO":

                score = (
                    (25 - adx) +
                    (1 - abs(rsi - 50) / 50) * 10 +
                    (1 - vwap_drift) * 10 +
                    (1 - abs(bb_position - 0.5)) * 10
                )

                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "RSI": round(rsi, 1),
                    "ADX": round(adx, 1),
                    "ATR %": round(atr_pct, 2),
                    "VWAP Drift": round(vwap_drift, 4),
                    "BB Position": round(bb_position, 2),
                    "Score": round(score, 2)
                })

            progress.progress((i + 1) / len(universe))

        if results:
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values(by="Score", ascending=False)
            df_results = df_results.reset_index(drop=True)
            df_results.insert(0, "Rank", df_results.index + 1)

            st.subheader("🎯 Neutral Setups (Ranked)")
            st.dataframe(df_results, hide_index=True)

        else:
            st.warning("No setups found.")

# ----------------- AUTO REFRESH -----------------

if mode == "Single Ticker" and auto:
    time.sleep(60)
    st.rerun()