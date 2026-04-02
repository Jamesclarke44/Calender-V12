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

# ----------------- A+ DECISION ENGINE -----------------

def evaluate_setup(price, rsi, adx, atr, vwap, bb_low, bb_high):

    atr_pct = (atr / price) * 100
    vwap_drift = abs(price - vwap) / price

    # BB position
    if bb_high - bb_low == 0:
        bb_position = 0.5
    else:
        bb_position = (price - bb_low) / (bb_high - bb_low)

    # A+ criteria
    if adx > 25:
        return "NO", "Trending", bb_position, atr_pct, vwap_drift

    if rsi < 40 or rsi > 60:
        return "NO", "RSI not neutral", bb_position, atr_pct, vwap_drift

    if vwap_drift > 0.01:
        return "NO", "Far from VWAP", bb_position, atr_pct, vwap_drift

    if atr_pct > 2.5:
        return "NO", "Too volatile", bb_position, atr_pct, vwap_drift

    if bb_position < 0.4 or bb_position > 0.6:
        return "NO", "BB not centered", bb_position, atr_pct, vwap_drift

    return "YES", "A+ Setup", bb_position, atr_pct, vwap_drift

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

            result, reason, bb_pos, atr_pct, vwap_drift = evaluate_setup(
                price, rsi, adx, atr, vwap, bb_low, bb_high
            )

            st.subheader(f"{ticker} — {price:.2f}")

            if result == "YES":
                st.success("GO ✅ A+ Setup")
            else:
                st.error(f"NO GO ⛔ — {reason}")

            st.write(f"RSI: {rsi:.1f}")
            st.write(f"ADX: {adx:.1f}")
            st.write