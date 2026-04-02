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

# ----------------- A+ ENGINE -----------------

def evaluate_setup(price, rsi, adx, atr, vwap, bb_low, bb_high):

    atr_pct = (atr / price) * 100
    vwap_drift = abs(price - vwap) / price

    if bb_high - bb_low == 0:
        bb_position = 0.5
    else:
        bb_position = (price - bb_low) / (bb_high - bb_low)

    score = 0
    reasons = []

    if adx <= 25:
        score += 1
    else:
        reasons.append("Trending")

    if 40 <= rsi <= 60:
        score += 1
    else:
        reasons.append("RSI")

    if vwap_drift <= 0.01:
        score += 1
    else:
        reasons.append("VWAP > 1%")

    if atr_pct <= 2.5:
        score += 1
    else:
        reasons.append("Volatility")

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

# ----------------- TIERED STRATEGY ENGINE -----------------

def tiered_strategy(score, rsi, adx, atr_pct, bb_position):

    low_risk = []
    moderate = []

    # LOW RISK (Calendars first)
    if adx < 20 and atr_pct < 2:
        low_risk.append("Single Calendar")

    if adx < 18 and 0.45 <= bb_position <= 0.55:
        low_risk.append("Double Calendar")

    if adx < 20 and score >= 3:
        low_risk.append("Ratio Calendar")

    # MODERATE RISK
    if score == 5:
        moderate.append("Iron Condor")

    if score == 4:
        moderate.append("Wide Iron Condor")

    if score >= 3:
        if rsi < 50:
            moderate.append("Bull Put Spread")
        else:
            moderate.append("Bear Call Spread")

    if score == 5 and 0.45 <= bb_position <= 0.55:
        moderate.append("Broken Wing Butterfly")

    if score >= 4 and rsi > 55:
        moderate.append("Jade Lizard")

    # PRIORITY LOGIC
    if low_risk:
        return "LOW RISK", ", ".join(low_risk)

    elif moderate:
        return "MODERATE RISK", ", ".join(moderate)

    else:
        return "NO TRADE", "No suitable setups"

# ----------------- UI -----------------

st.title("🧠 Strategy Finder Scanner")

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

            risk_level, strategies = tiered_strategy(score, rsi, adx, atr_pct, bb_pos)

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
            st.write(f"Risk Level: **{risk_level}**")
            st.write(f"Strategies: **{strategies}**")

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

                risk_level, strategies = tiered_strategy(score, rsi, adx, atr_pct, bb_pos)

                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "Grade": result,
                    "Score": score,
                    "Risk Level": risk_level,
                    "Strategies": strategies,
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

            st.subheader("📊 All Results")
            st.dataframe(df_results.sort_values(by="Score", ascending=False), hide_index=True)

            low_risk_df = df_results[df_results["Risk Level"] == "LOW RISK"]

            st.subheader("🟢 Low Risk (Calendars First)")

            if low_risk_df.empty:
                st.warning("⚠️ No available calendar spread trades. Showing moderate-risk setups.")
                st.dataframe(df_results[df_results["Risk Level"] == "MODERATE RISK"], hide_index=True)
            else:
                st.success("✅ Low-risk calendar opportunities found")
                st.dataframe(low_risk_df, hide_index=True)

        else:
            st.warning("No results found.")