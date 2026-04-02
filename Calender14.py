import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="Market Scanner", layout="wide")

# =========================
# LOAD S&P 500
# =========================
@st.cache_data
def load_sp500():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    table = pd.read_html(url)[0]
    tickers = table["Symbol"].tolist()
    tickers = [t.replace(".", "-") for t in tickers]
    return tickers

# =========================
# LOAD UNIVERSE
# =========================
def load_universe(selection):
    if selection == "SPY / DIA / QQQ":
        return ["SPY", "DIA", "QQQ"]
    elif selection == "S&P 500":
        return load_sp500()
    else:
        return []

# =========================
# INDICATORS
# =========================
def compute_indicators(df):
    df = df.copy()

    # Bollinger Bands
    window = 20
    df["MA"] = df["Close"].rolling(window).mean()
    df["STD"] = df["Close"].rolling(window).std()
    df["Upper"] = df["MA"] + 2 * df["STD"]
    df["Lower"] = df["MA"] - 2 * df["STD"]

    # Bollinger Position (0 = lower band, 1 = upper band)
    df["BB_Pos"] = (df["Close"] - df["Lower"]) / (df["Upper"] - df["Lower"])

    return df

# =========================
# SCORING FUNCTION
# =========================
def score_setup(row):
    score = 0

    # Bollinger Band condition (40%–60%)
    if 0.4 <= row["BB_Pos"] <= 0.6:
        score += 2

    # Price near MA (mean reversion / neutral)
    if abs(row["Close"] - row["MA"]) / row["MA"] < 0.02:
        score += 1

    return score

# =========================
# FETCH DATA
# =========================
def get_data(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)
        if df.empty:
            return None
        df = compute_indicators(df)
        return df
    except:
        return None

# =========================
# SCAN FUNCTION
# =========================
def scan_market(tickers, progress_bar):
    results = []

    total = len(tickers)

    for i, ticker in enumerate(tickers):
        df = get_data(ticker)

        if df is None:
            continue

        latest = df.iloc[-1]

        score = score_setup(latest)

        if score > 0:
            results.append({
                "Ticker": ticker,
                "Price": latest["Close"],
                "BB_Pos": latest["BB_Pos"],
                "Score": score
            })

        progress_bar.progress((i + 1) / total)

    if results:
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values(by="Score", ascending=False)
        return results_df
    else:
        return pd.DataFrame()

# =========================
# UI
# =========================
st.title("📊 Market Scanner")

mode = st.radio("Mode", ["Single Ticker", "Market Scan"])

# =========================
# SINGLE TICKER MODE
# =========================
if mode == "Single Ticker":
    ticker = st.text_input("Enter Ticker", "SPY")

    if st.button("Run"):
        df = get_data(ticker)

        if df is not None:
            st.line_chart(df["Close"])
            st.write(df.tail())
        else:
            st.error("No data found.")

# =========================
# MARKET SCAN MODE
# =========================
else:
    universe_option = st.selectbox(
        "Select Universe",
        ["SPY / DIA / QQQ", "S&P 500"]
    )

    if st.button("Run Scan"):
        st.info("Scanning market...")

        tickers = load_universe(universe_option)

        progress_bar = st.progress(0)

        results_df = scan_market(tickers, progress_bar)

        if not results_df.empty:
            st.success(f"Found {len(results_df)} setups")

            st.dataframe(results_df, use_container_width=True)

        else:
            st.warning("No setups found.")