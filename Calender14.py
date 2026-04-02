import streamlit as st
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
        "SPY","QQQ","DIA","IWM","VTI","VOO","IVV",

        "XLF","XLV","XLE","XLK","XLY","XLI","XLP","XLU","XLB","XLRE","XLC",

        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AVGO","NFLX",
        "AMD","INTC","CRM","ORCL","ADBE","CSCO","NOW","PANW","SNOW",

        "JPM","BAC","GS","MS","C","WFC","SCHW","BLK","USB","PNC",

        "WMT","COST","HD","LOW","NKE","SBUX","MCD","TGT","PG","KO","PEP",

        "JNJ","UNH","PFE","MRK","ABBV","TMO","DHR","ABT","MDT","BMY",

        "NEE","DUK","SO","AEP","EXC","XEL","ED","PEG","ES",

        "O","PLD","SPG","AMT","CCI","EQIX","PSA","WELL","VTR",

        "HON","UPS","UNP","CAT","DE","MMM","EMR","ITW","GD",

        "VZ","T","TMUS",

        "XOM","CVX","COP","EOG","SLB","OXY",

        "SHOP.TO","RY.TO","TD.TO","BNS.TO","BMO.TO","ENB.TO","TRP.TO"
    ]

# ----------------- UTIL -----------------

def chunk_list(lst, size=50):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# ----------------- DATA -----------------

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

# ----------------- PRE-FILTER -----------------

def pre_filter(price, rsi, adx, atr_pct):
    if price < 10:
        return False

    if pd.isna(rsi) or pd.isna(adx):
        return False

    if adx > 30:
        return False

    if rsi < 30 or rsi > 70:
        return False

    if atr_pct < 0.3 or atr_pct > 5:
        return False

    return True

# ----------------- DECISION ENGINE -----------------

def decision_engine(adx, rsi, vwap_drift, atr_pct, bb_position):

    if adx > 25:
        return "NO GO", "Trending market"

    if rsi < 40 or rsi > 60:
        return "NO GO", "Momentum not neutral"

    if vwap_drift > 0.01:
        return "NO GO", "Too far from VWAP"

    if atr_pct > 2.5:
        return "NO GO", "Volatility too high"

    if bb_position < 0.4 or bb_position > 0.6:
        return "NO GO", "Price not centered in Bollinger Bands"

    return "GO", "All conditions aligned"

# ----------------- BIAS -----------------

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

# ----------------- UI -----------------

st.title("📊 Trading Engine Scanner (Scaled)")

max_scan = st.slider("Max tickers to scan", 50, 600, 300)

if st.button("Run Scan"):

    universe = load_universe()[:max_scan]

    results = []
    progress = st.progress(0)

    batch_size = 50
    batches = list(chunk_list(universe, batch_size))

    for b_idx, batch in enumerate(batches):

        data = yf.download(
            tickers=batch,
            period="6mo",
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False
        )

        for ticker in batch:

            try:
                df = data[ticker].dropna()

                if df.empty or len(df) < 50:
                    continue

                df = compute_indicators(df)
                last = df.iloc[-1]

                price = last["Close"]
                rsi = last["RSI"]
                adx = last["ADX"]
                atr = last["ATR"]
                vwap = last["VWAP"]

                atr_pct = (atr / price) * 100
                vwap_drift = abs(price - vwap) / price

                # -------- PRE FILTER --------
                if not pre_filter(price, rsi, adx, atr_pct):
                    continue

                # -------- BB POSITION --------
                bb_range = last["BB_High"] - last["BB_Low"]

                if bb_range == 0 or pd.isna(bb_range):
                    bb_position = 0.5
                else:
                    bb_position = (price - last["BB_Low"]) / bb_range

                # -------- DECISION --------
                decision, reason = decision_engine(adx, rsi, vwap_drift, atr_pct, bb_position)

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

            except:
                continue

        progress.progress((b_idx + 1) / len(batches))

    if results:
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by="Score", ascending=False)
        df_results = df_results.reset_index(drop=True)
        df_results.insert(0, "Rank", df_results.index + 1)

        st.subheader("🎯 Neutral Setups (Ranked)")
        st.dataframe(df_results, hide_index=True)

    else:
        st.warning("No setups found.")