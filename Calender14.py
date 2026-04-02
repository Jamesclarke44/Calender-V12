import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Strategy Finder", layout="centered")

# ----------------- UNIVERSE (FIXED) -----------------

@st.cache_data
def load_universe():
    # Stable S&P 500 CSV source (no scraping)
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv"
    
    df = pd.read_csv(url)
    sp500 = df["Symbol"].tolist()

    # ETFs
    etfs = [
        "SPY","QQQ","IWM","DIA","VTI","VOO","IVV",
        "XLF","XLK","XLE","XLV","XLI","XLP","XLU","XLY","XLB","XLRE","XLC",
        "ARKK","ARKG","SMH","SOXX","XBI","EEM","GLD","SLV","TLT"
    ]

    universe = list(set(sp500 + etfs))
    return universe

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

# ----------------- STRATEGY LOGIC -----------------

def classify_strategies(price, rsi, adx, atr, vwap, bb_low, bb_high):

    atr_pct = (atr / price) * 100
    vwap_drift = abs(price - vwap) / price

    if bb_high - bb_low == 0:
        bb_position = 0.5
    else:
        bb_position = (price - bb_low) / (bb_high - bb_low)

    strategies = []
    risk_level = None

    # LOW RISK (A+)
    if (
        40 <= rsi <= 60 and
        adx < 25 and
        vwap_drift <= 0.01 and
        0.4 <= bb_position <= 0.6 and
        atr_pct <= 2.5
    ):
        strategies += ["Single Calendar", "Double Calendar", "Ratio Calendar"]
        risk_level = "LOW RISK"

    # MODERATE RISK
    if (
        adx < 30 and
        vwap_drift <= 0.015
    ):
        strategies += [
            "Wide Iron Condor",
            "Wide Credit Spread",
            "Broken Wing Butterfly",
            "Jade Lizard"
        ]
        risk_level = risk_level or "MODERATE RISK"

    return risk_level, strategies, bb_position, atr_pct, vwap_drift

# ----------------- SCANNER -----------------

def scan_universe(tickers, progress_bar, status_text, counter_text):

    results = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):

        counter_text.markdown(f"### Scanned: {i+1} / {total}")
        status_text.text(f"Scanning {ticker}")

        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)

            if df is None or df.empty:
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

            risk_level, strategies, bb_pos, atr_pct, vwap_drift = classify_strategies(
                price, rsi, adx, atr, vwap, bb_low, bb_high
            )

            if risk_level:
                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "RSI": round(rsi, 1),
                    "ADX": round(adx, 1),
                    "ATR %": round(atr_pct, 2),
                    "VWAP Drift %": round(vwap_drift * 100, 2),
                    "BB Position": round(bb_pos, 2),
                    "Risk Level": risk_level,
                    "Strategies": ", ".join(strategies)
                })

        except Exception:
            continue

        progress_bar.progress((i + 1) / total)

    status_text.text("Scan complete ✅")

    return pd.DataFrame(results)

# ----------------- UI -----------------

st.title("🧠 Strategy Finder")

mode = st.radio("Mode", ["Scan Universe", "Single Ticker"])

# ----------------- SINGLE TICKER -----------------

if mode == "Single Ticker":

    ticker = st.text_input("Enter Ticker", value="SPY").upper()

    if st.button("Analyze"):

        with st.spinner("Analyzing... ⏳"):
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

            risk_level, strategies, bb_pos, atr_pct, vwap_drift = classify_strategies(
                price, rsi, adx, atr, vwap, bb_low, bb_high
            )

            st.subheader(f"{ticker} — {price:.2f}")

            if risk_level == "LOW RISK":
                st.success("🟢 Low Risk A+ Setup")
            elif risk_level == "MODERATE RISK":
                st.warning("🟡 Moderate Risk Setup")
            else:
                st.error("❌ No Setup")

            st.write(f"RSI: {rsi:.1f}")
            st.write(f"ADX: {adx:.1f}")
            st.write(f"VWAP Drift: {vwap_drift*100:.2f}%")
            st.write(f"ATR %: {atr_pct:.2f}%")
            st.write(f"BB Position: {bb_pos:.2f}")

            st.subheader("Recommended Strategies")

            if strategies:
                for s in strategies:
                    st.write(f"• {s}")
            else:
                st.write("No suitable strategies found")

# ----------------- UNIVERSE SCAN -----------------

if mode == "Scan Universe":

    if st.button("Run Scan"):

        tickers = load_universe()

        progress_bar = st.progress(0)
        status_text = st.empty()
        counter_text = st.empty()

        with st.spinner("Scanning market..."):

            df_results = scan_universe(tickers, progress_bar, status_text, counter_text)

        if df_results.empty:
            st.warning("❌ No opportunities found")
        else:
            low_risk_df = df_results[df_results["Risk Level"] == "LOW RISK"]
            moderate_df = df_results[df_results["Risk Level"] == "MODERATE RISK"]

            st.subheader("🟢 Low Risk Opportunities")

            if not low_risk_df.empty:
                st.dataframe(low_risk_df, use_container_width=True)
            else:
                st.info("No low-risk setups found.")

            st.subheader("🟡 Moderate Risk Opportunities")

            if not moderate_df.empty:
                st.dataframe(moderate_df, use_container_width=True)
            else:
                st.info("No moderate-risk setups found.")

            if low_risk_df.empty and moderate_df.empty:
                st.warning("❌ No trade opportunities found based on current criteria.")