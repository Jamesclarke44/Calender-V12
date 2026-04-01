import streamlit as st
import pandas as pd

# -----------------------------
# INPUT
# -----------------------------
st.title("📊 Smart Market Scanner")

tickers_input = st.text_input("Enter tickers (comma separated)", "SPY,QQQ,DIA").upper()
ticker_list = [t.strip() for t in tickers_input.split(",") if t.strip()]

# -----------------------------
# PLACEHOLDER FUNCTIONS
# (You already have these)
# -----------------------------
def fetch_data(ticker):
    # Replace with your IBKR / data source
    return pd.DataFrame()

def compute_indicators(df):
    # Replace with your indicator logic
    return df

def decision_engine(adx, rsi, vwap_drift, atr_pct):
    # Replace with your logic
    if adx < 25 and 45 <= rsi <= 55:
        return "GO", "Range conditions met"
    return "NO GO", "No edge"

def get_bias(price, sma50, sma200, rsi, vwap):
    if price > sma50 and sma50 > sma200:
        return "Bullish"
    elif price < sma50 and sma50 < sma200:
        return "Bearish"
    return "Neutral"

def get_regime(adx, atr_pct):
    if adx > 25:
        return "Trending"
    return "Range"

# -----------------------------
# SCORING FUNCTION
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
# SCANNER
# -----------------------------
results = []

if st.button("Run Scan"):

    for ticker in ticker_list:

        df = fetch_data(ticker)

        if df is None or df.empty:
            continue

        df = compute_indicators(df)
        last = df.iloc[-1]

        price = last.get("Close", 0)
        rsi = last.get("RSI", 0)
        adx = last.get("ADX", 0)
        atr = last.get("ATR", 0)
        vwap = last.get("VWAP", price)

        sma50 = last.get("SMA50", price)
        sma200 = last.get("SMA200", price)

        atr_pct = (atr / price) * 100 if price else 0
        vwap_drift = abs(price - vwap) / price if price else 0

        decision, reason = decision_engine(adx, rsi, vwap_drift, atr_pct)
        bias = get_bias(price, sma50, sma200, rsi, vwap)
        regime = get_regime(adx, atr_pct)

        score = score_setup(adx, rsi, vwap_drift, atr_pct)

        results.append({
            "Ticker": ticker,
            "Price": round(price, 2),
            "Decision": decision,
            "Bias": bias,
            "Regime": regime,
            "Score": score,
            "Reason": reason
        })

# -----------------------------
# DISPLAY
# -----------------------------
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
        else:
            return [""] * len(row)

    st.subheader("📊 Scan Results (Ranked)")

    st.dataframe(df_results.style.apply(highlight, axis=1))

else:
    st.write("No results yet. Click 'Run Scan'.")