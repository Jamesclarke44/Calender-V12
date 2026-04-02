import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice

st.set_page_config(page_title="Strategy Finder", layout="centered")

# ----------------- EXPANDED UNIVERSE -----------------

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

# ----------------- REGIME -----------------

def detect_regime(adx, rsi, atr_pct):
    if adx < 30 and 35 <= rsi <= 65:
        return "NEUTRAL"
    elif adx >= 30:
        return "TRENDING"
    elif atr_pct > 3:
        return "VOLATILE"
    return "NEUTRAL"

# ----------------- STRATEGY -----------------

def suggest_strategies(regime, bb_position):
    if regime == "NEUTRAL":
        if 0.3 < bb_position < 0.7:
            return ["Credit Spread", "Iron Condor", "Calendar Spread"]
        elif bb_position <= 0.3:
            return ["Bull Put Spread"]
        elif bb_position >= 0.7:
            return ["Bear Call Spread"]

    elif regime == "TRENDING":
        return ["Pullback Trade", "Breakout", "Debit Spread"]

    elif regime == "VOLATILE":
        return ["Straddle", "Strangle", "Long Options"]

    return ["Watch"]

def get_bb_position(price, bb_low, bb_high):
    if bb_high - bb_low == 0:
        return 0.5
    return (price - bb_low) / (bb_high - bb_low)

# ----------------- UI -----------------

st.title("🧠 Strategy Finder")

mode = st.radio("Mode", ["Scan Universe", "Single Ticker"])

# ----------------- SINGLE TICKER -----------------

if mode == "Single Ticker":

    ticker = st.text_input("Enter Ticker", value="AAPL")

    if st.button("Analyze Ticker"):

        df = yf.download(ticker, period="6mo", interval="1d", progress=False)

        if df.empty:
            st.error("No data found.")
        else:
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

            st.subheader(f"{ticker} Analysis")

            st.write({
                "Price": round(price,2),
                "RSI": round(rsi,1),
                "ADX": round(adx,1),
                "ATR %": round(atr_pct,2),
                "BB Position": round(bb_position,2),
                "Regime": regime,
                "Strategies": strategies
            })

# ----------------- UNIVERSE SCAN -----------------

else:

    max_scan = st.slider("Max tickers to scan", 50, 500, 200)

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
                    "Price": round(price,2),
                    "Regime": regime,
                    "Strategies": ", ".join(strategies),
                    "RSI": round(rsi,1),
                    "ADX": round(adx,1),
                    "BB Position": round(bb_position,2),
                    "ATR %": round(atr_pct,2)
                })

            except:
                continue

            progress.progress((i+1)/len(universe))

        if results:
            df_results = pd.DataFrame(results)
            st.subheader("📊 Strategy Candidates")
            st.dataframe(df_results.sort_values(by="BB Position"), hide_index=True)
        else:
            st.warning("No results found.")