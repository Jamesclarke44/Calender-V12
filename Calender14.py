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
        "SPY","QQQ","DIA","IWM","VTI","VOO","IVV",
        "XLF","XLK","XLE","XLV","XLI","XLP","XLU","XLY","XLB","XLRE","XLC",
        "ARKK","ARKG","SMH","SOXX","XBI","EEM","GLD","SLV","TLT",
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA",
        "AMD","INTC","CRM","ORCL","ADBE","CSCO","NOW","SNOW","PANW",
        "JPM","BAC","GS","MS","C","WFC","SCHW","BLK","USB","PNC",
        "WMT","COST","HD","LOW","NKE","SBUX","MCD","TGT","DG",
        "JNJ","UNH","PFE","MRK","ABBV","TMO","DHR","ABT","BMY","LLY",
        "XOM","CVX","COP","EOG","SLB","OXY","KMI","PSX",
        "CAT","DE","MMM","HON","UPS","UNP","RTX","GE","LMT",
        "NEE","DUK","SO","AEP","EXC","XEL","ED","PEG",
        "VZ","T","TMUS",
        "PG","KO","PEP","PM","MO","KHC","CL",
        "O","PLD","AMT","CCI","EQIX","PSA","SPG","WELL","VTR","DLR"
    ]

# ----------------- INDICATORS -----------------

def compute_indicators(df):
    df = df.copy()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()

    close = df["Close"].squeeze()
    high = df["High"].squeeze()
    low = df["Low"].squeeze()
    volume = df["Volume"].squeeze()

    df["RSI"] = RSIIndicator(close=close).rsi()
    df["ADX"] = ADXIndicator(high=high, low=low, close=close).adx()
    df["ATR"] = AverageTrueRange(high=high, low=low, close=close).average_true_range()

    bb = BollingerBands(close=close)
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Low"] = bb.bollinger_lband()

    vwap = VolumeWeightedAveragePrice(
        high=high, low=low, close=close, volume=volume
    )
    df["VWAP"] = vwap.volume_weighted_average_price()

    return df

# ----------------- STRATEGY RECOMMENDATION -----------------

def recommend_strategy(score, rsi):

    if score == 5:
        return "Iron Condor / Short Strangle"

    if score == 4:
        if rsi < 45:
            return "Bull Put Spread"
        elif rsi > 55:
            return "Bear Call Spread"
        else:
            return "Iron Condor (Wide)"

    if score == 3:
        return "Credit Spread (Directional Bias)"

    return "No Trade"

# ----------------- A+ DECISION ENGINE -----------------

def evaluate_setup(price, rsi, adx, atr, vwap, bb_low, bb_high):

    atr_pct = (atr / price) * 100
    vwap_drift = abs(price - vwap) / price

    # BB position
    if bb_high - bb_low == 0:
        bb_position = 0.5
    else:
        bb_position = (price - bb_low) / (bb_high - bb_low)

    score = 0
    reasons = []

    # ADX
    if adx <= 25:
        score += 1
    else:
        reasons.append("Trending")

    # RSI
    if 40 <= rsi <= 60:
        score += 1
    else:
        reasons.append("RSI")

    # VWAP
    if vwap_drift <= 0.01:
        score += 1
    else:
        reasons.append("VWAP > 1%")

    # ATR
    if atr_pct <= 2.5:
        score += 1
    else:
        reasons.append("Volatility")

    # BB
    if 0.4 <= bb_position <= 0.6:
        score += 1
    else:
        reasons.append("BB")

    if score == 5:
        return "A+", "Perfect", score, bb_position, atr_pct, vwap_drift
    elif score >= 3:
        return "GOOD", ", ".join(reasons), score, bb_position, atr_pct, vwap_drift
    else:
        return "BAD", ", ".join(reasons), score, bb_position, atr_pct, vwap_drift

# ----------------- UI -----------------

st.title("🧠 A+ Trading Scanner")

mode = st.radio("Mode", ["Scan Universe", "Single Ticker"])

# ----------------- SINGLE TICKER -----------------

if mode == "Single Ticker":

    ticker = st.text_input("Enter Ticker", value="SPY").upper()

    if st.button("Analyze"):

        df = yf.download(ticker, period="6mo", interval="1d", progress=False)

        if df is None or df.empty:
            st.error("No data found")
        else:
            df = compute_indicators(df)
            last = df.iloc[-1]

            price = last["Close"]
            rsi = last["RSI"]
            adx = last["ADX"]
            atr = last["ATR"]
            vwap = last["VWAP"]

            bb_low = last["BB_Low"]
            bb_high = last["BB_High"]

            result, reason, score, bb_pos, atr_pct, vwap_drift = evaluate_setup(
                price, rsi, adx, atr, vwap, bb_low, bb_high
            )

            strategy = recommend_strategy(score, rsi)

            st.subheader(f"{ticker} — {price:.2f}")

            if result == "A+":
                st.success("GO ✅ A+ Setup")
            elif result == "GOOD":
                st.info("GOOD Setup")
            else:
                st.error(f"NO GO ⛔ — {reason}")

            st.write(f"RSI: {rsi:.1f}")
            st.write(f"ADX: {adx:.1f}")
            st.write(f"ATR %: {atr_pct:.2f}")
            st.write(f"VWAP Drift: {vwap_drift:.4f}")
            st.write(f"BB Position: {bb_pos:.2f}")
            st.write(f"Score: {score}/5")
            st.write(f"Recommended Strategy: **{strategy}**")

# ----------------- SCANNER -----------------

else:

    max_scan = st.slider("Max tickers", 50, 500, 200)

    if st.button("Run Scan"):

        universe = load_universe()[:max_scan]
        results = []

        progress = st.progress(0)

        for i, ticker in enumerate(universe):

            try:
                df = yf.download(ticker, period="6mo", interval="1d", progress=False)

                if df is None or df.empty or len(df) < 50:
                    continue

                df = compute_indicators(df)
                last = df.iloc[-1]

                price = last["Close"]
                rsi = last["RSI"]
                adx = last["ADX"]
                atr = last["ATR"]
                vwap = last["VWAP"]

                bb_low = last["BB_Low"]
                bb_high = last["BB_High"]

                result, reason, score, bb_pos, atr_pct, vwap_drift = evaluate_setup(
                    price, rsi, adx, atr, vwap, bb_low, bb_high
                )

                strategy = recommend_strategy(score, rsi)

                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "Grade": result,
                    "Score": score,
                    "Strategy": strategy,
                    "Reason": reason,
                    "RSI": round(rsi, 1),
                    "ADX": round(adx, 1),
                    "ATR %": round(atr_pct, 2),
                    "VWAP Drift": round(vwap_drift, 4),
                    "BB Position": round(bb_pos, 2)
                })

            except:
                continue

            progress.progress((i + 1) / len(universe))

        if results:
            df_results = pd.DataFrame(results)

            df_results = df_results.sort_values(by="Score", ascending=False)

            st.subheader("📊 All Results")
            st.dataframe(df_results, hide_index=True)

            st.subheader("🎯 A+ Setups")
            st.dataframe(df_results[df_results["Grade"] == "A+"], hide_index=True)

        else:
            st.warning("No results found.")