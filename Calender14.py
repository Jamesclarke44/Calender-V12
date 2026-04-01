import streamlit as st
import math
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import VolumeWeightedAveragePrice
from datetime import datetime, date

st.set_page_config(page_title="Calendar Spread Decision Engine V7 (Auto)", layout="centered")

# ----------------- STYLE -----------------

st.markdown("""
<style>
div.stButton > button {
    width: 100%;
    height: 60px;
    font-size: 20px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ----------------- CORE FUNCTIONS -----------------

def expected_move(price, iv, dte):
    return price * (iv / 100) * math.sqrt(dte / 365)


def classify_trade(price, vwap, rsi, adx, atr_pct, ivr,
                   bbl_low, bbl_high, vwap_drift,
                   atr_trend, trend_structure):
    reasons = []
    env_score = 0

    # ---------- HARD NO-GO ----------

    if adx > 25:
        return "NO GO", 0, ["Trending market (ADX > 25)"]

    if rsi < 40 or rsi > 60:
        return "NO GO", 0, [f"Directional momentum (RSI {rsi:.1f})"]

    if vwap_drift > 0.01:
        return "NO GO", 0, [f"VWAP drift too large ({vwap_drift*100:.2f}%)"]

    if price <= bbl_low or price >= bbl_high:
        return "NO GO", 0, ["Price at/through Bollinger Bands"]

    if atr_trend == "Expanding":
        return "NO GO", 0, ["ATR expanding (volatility increasing)"]

    if ivr < 20:
        return "NO GO", 0, [f"IVR too low ({ivr:.1f})"]

    if trend_structure != "Neutral":
        return "NO GO", 0, [f"Trend not neutral ({trend_structure})"]

    # ---------- ENVIRONMENT SCORING (0–6) ----------

    if adx < 20 and trend_structure == "Neutral":
        env_score += 1
        reasons.append("Neutral, non-trending environment (ADX < 20, structure neutral)")
    else:
        reasons.append("Trend acceptable but not ideal")

    if 45 <= rsi <= 55:
        env_score += 1
        reasons.append("RSI in tight neutral band (45–55)")
    else:
        reasons.append("RSI neutral but not ideal (40–60)")

    if atr_pct < 2.0 and atr_trend in ["Stable", "Shrinking"]:
        env_score += 1
        reasons.append("Low and stable/shrinking ATR")
    else:
        reasons.append("ATR acceptable but not ideal")

    if vwap_drift < 0.005:
        env_score += 1
        reasons.append(f"Price tightly anchored to VWAP ({vwap_drift*100:.2f}% drift)")
    elif vwap_drift < 0.01:
        reasons.append(f"Price near VWAP but slightly loose ({vwap_drift*100:.2f}% drift)")
    else:
        reasons.append(f"Price too far from VWAP ({vwap_drift*100:.2f}% drift)")

    if bbl_low < price < bbl_high:
        env_score += 1
        reasons.append("Price inside Bollinger range")
    else:
        reasons.append("Price near or outside Bollinger bands")

    if 20 <= ivr <= 45:
        env_score += 1
        reasons.append(f"IVR in ideal range ({ivr:.1f})")
    else:
        reasons.append(f"IVR acceptable but not ideal ({ivr:.1f})")

    if env_score >= 5:
        decision = "GO"
    elif env_score >= 3:
        decision = "CAUTION"
    else:
        decision = "NO GO"

    return decision, env_score, reasons


# ----------------- STRATEGY & SIZING -----------------

def double_calendar_go_no_go(adx, rsi, vwap_drift, atr_pct, ivr,
                             atr_trend, trend_structure, env_score):
    reasons = []

    if adx > 25:
        reasons.append("ADX too high (market trending)")
    if rsi < 40 or rsi > 60:
        reasons.append(f"RSI too directional ({rsi:.1f})")
    if vwap_drift > 0.01:
        reasons.append(f"VWAP drift too large ({vwap_drift*100:.2f}%)")
    if atr_pct > 2.5:
        reasons.append(f"ATR too high ({atr_pct:.2f}%)")
    if atr_trend == "Expanding":
        reasons.append("ATR expanding (volatility increasing)")
    if ivr < 20:
        reasons.append(f"IVR too low ({ivr:.1f})")
    if trend_structure != "Neutral":
        reasons.append(f"Trend not neutral ({trend_structure})")

    if reasons:
        return "NO GO", reasons

    go_reasons = []
    if adx < 20:
        go_reasons.append("Low ADX (non-trending)")
    if 45 <= rsi <= 55:
        go_reasons.append("RSI neutral (45–55)")
    if vwap_drift < 0.0075:
        go_reasons.append(f"Tight VWAP drift ({vwap_drift*100:.2f}%)")
    if atr_pct < 2.0:
        go_reasons.append(f"Low ATR ({atr_pct:.2f}%)")
    if atr_trend in ["Stable", "Shrinking"]:
        go_reasons.append(f"ATR {atr_trend.lower()}")
    if 20 <= ivr <= 45:
        go_reasons.append(f"IVR ideal ({ivr:.1f})")
    if env_score >= 4:
        go_reasons.append(f"Strong environment score ({env_score}/6)")

    if len(go_reasons) >= 5:
        return "GO", go_reasons

    caution_reasons = ["Environment acceptable but not ideal for a double calendar"]
    return "CAUTION", caution_reasons


def recommend_strategy(adx, rsi, vwap_drift, ivr,
                       trend_structure, atr_trend, env_score,
                       dc_decision):
    if (env_score >= 5 and
        adx < 20 and
        45 <= rsi <= 55 and
        vwap_drift < 0.005 and
        20 <= ivr <= 40 and
        trend_structure == "Neutral" and
        atr_trend in ["Stable", "Shrinking"]):
        return "Single Calendar — A+ Neutral Setup"

    if (env_score >= 4 and
        adx < 20 and
        40 <= rsi <= 60 and
        vwap_drift < 0.0075 and
        20 <= ivr <= 45 and
        trend_structure == "Neutral" and
        dc_decision in ["GO", "CAUTION"]):
        return "Double Calendar — Extra Safe, Wide Neutral Tent"

    if (3 <= env_score <= 4 and
        20 <= adx <= 25 and
        50 <= rsi <= 60 and
        0.005 <= vwap_drift <= 0.01 and
        ivr >= 30):
        return "Wide Iron Condor — Neutral but Drifting Environment"

    if (adx < 20 and
        ivr > 40 and
        rsi < 60 and
        trend_structure != "Strong Downtrend"):
        return "Jade Lizard — High IV, Low Trend, No Upside Risk"

    if (adx < 25 and
        ivr >= 30 and
        40 <= rsi <= 60):
        return "Wide Credit Spread — Defined-Risk Theta Play"

    return "No Clear Edge — Stay Flat or Use Very Small Calendar Size"


def position_sizing(env_score, decision):
    if decision != "GO":
        if env_score >= 3:
            return "Small size only — 0.5–1x normal risk."
        else:
            return "No trade — environment not supportive."

    if env_score == 6:
        return "2–3 Calendars (or 2–3x base unit) — A+ conditions."
    if env_score == 5:
        return "1–2 Calendars — Strong neutral environment."
    if env_score == 4:
        return "1 Small Calendar — Decent but not perfect."
    if env_score == 3:
        return "Tiny size — 0.5x or paper trade."

    return "No trade — environment too weak."


# ----------------- REAL P&L ENGINE -----------------

def real_calendar_pnl(price, strike, move, front_iv, back_iv, debit):
    prices = np.linspace(price - move * 2, price + move * 2, 100)
    pnl = []

    for p in prices:
        distance = abs(p - strike)

        front_decay = front_iv * (1 - (distance / move))
        back_value = back_iv * (1 - (distance / (move * 1.5)))

        front_decay = max(front_decay, 0)
        back_value = max(back_value, 0)

        value = back_value - front_decay
        pnl_value = (value * 10) - debit

        pnl.append(pnl_value)

    pnl = np.array(pnl)

    fig, ax = plt.subplots()
    ax.plot(prices, pnl)
    ax.axvline(strike, linestyle="--")
    ax.axhline(0)

    ax.set_title("Real Calendar P&L")
    ax.set_xlabel("Price")
    ax.set_ylabel("Profit / Loss ($)")

    return fig


# ----------------- DOUBLE CALENDAR OPTIMIZER -----------------

def double_calendar_optimizer(price, move, front_dte, back_dte, front_iv, back_iv):
    strikes = [
        round(price - move * 0.5),
        round(price),
        round(price + move * 0.5)
    ]

    front_range = range(max(5, int(front_dte) - 3), int(front_dte) + 4)
    back_range = range(max(20, int(back_dte) - 7), int(back_dte) + 8)

    best = None
    best_score = -999

    for strike in strikes:
        for f in front_range:
            for b in back_range:
                score = 0

                center_dist = abs(price - strike) / move if move > 0 else 0
                score += max(0, 1 - center_dist)

                if back_iv > front_iv:
                    score += 2
                else:
                    score -= 1

                if 7 <= f <= 14:
                    score += 1
                if 30 <= b <= 60:
                    score += 1

                ratio = b / f if f > 0 else 0
                if 2.5 <= ratio <= 5:
                    score += 1

                if score > best_score:
                    best_score = score
                    best = {
                        "strike": strike,
                        "front_dte": f,
                        "back_dte": b,
                        "score": score
                    }

    return best


# ----------------- DATA & INDICATOR ENGINE (DAILY, AUTO) -----------------

def fetch_daily_data(ticker: str, period: str = "1y"):
    df = yf.download(ticker, period=period, interval="1d", auto_adjust=False)
    if df.empty:
        return None
    return df


def compute_indicators(df: pd.DataFrame):
    df = df.copy()

    # --- FIXES FOR YFINANCE DATA ---

    # Flatten multi-index columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    # Ensure numeric types
    for col in ["Close", "High", "Low", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows missing essential data
    df = df.dropna(subset=["Close", "High", "Low", "Volume"])

    if df.empty:
        return df

    # --- INDICATORS ---

    rsi_ind = RSIIndicator(close=df["Close"], window=14)
    df["RSI"] = rsi_ind.rsi()

    adx_ind = ADXIndicator(high=df["High"], low=df["Low"], close=df["Close"], window=14)
    df["ADX"] = adx_ind.adx()

    atr_ind = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14)
    df["ATR"] = atr_ind.average_true_range()

    bb_ind = BollingerBands(close=df["Close"], window=20, window_dev=2)
    df["BB_High"] = bb_ind.bollinger_hband()
    df["BB_Low"] = bb_ind.bollinger_lband()

    vwap_ind = VolumeWeightedAveragePrice(
        high=df["High"], low=df["Low"], close=df["Close"], volume=df["Volume"], window=20
    )
    df["VWAP"] = vwap_ind.volume_weighted_average_price()

    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=200).mean()

    return df


def infer_trend_structure(row):
    if pd.isna(row["SMA50"]) or pd.isna(row["SMA200"]):
        return "Neutral"
    if row["SMA50"] > row["SMA200"] * 1.01:
        return "Uptrend"
    if row["SMA50"] < row["SMA200"] * 0.99:
        return "Downtrend"
    return "Neutral"


def infer_atr_trend(df: pd.DataFrame, lookback: int = 10):
    recent = df["ATR"].dropna().tail(lookback)
    if len(recent) < 3:
        return "Stable"
    first = recent.iloc[0]
    last = recent.iloc[-1]
    change_pct = (last - first) / first * 100 if first != 0 else 0
    if change_pct > 10:
        return "Expanding"
    if change_pct < -10:
        return "Shrinking"
    return "Stable"


def fetch_iv_and_ivr():
    vix = yf.download("^VIX", period="1y", interval="1d")
    if vix.empty:
        return 20.0, 30.0
    vix["Close"] = vix["Close"].fillna(method="ffill")
    iv = float(vix["Close"].iloc[-1])
    iv_min = float(vix["Close"].min())
    iv_max = float(vix["Close"].max())
    if iv_max == iv_min:
        ivr = 50.0
    else:
        ivr = (iv - iv_min) / (iv_max - iv_min) * 100
    return iv, ivr


def detect_market_closed(last_bar_date: date):
    today = datetime.now().date()
    if last_bar_date < today:
        return True, last_bar_date
    return False, last_bar_date


# ----------------- UI -----------------

st.title("📊 Calendar Spread Decision Engine V7 — Automated Daily Data")

ticker = st.text_input("Ticker", value="SPY").upper().strip()

debit = st.number_input("Debit Paid ($) for Calendar P&L Approximation", value=2.50)

if st.button("🚀 Evaluate Trade (Auto Data)"):

    if not ticker:
        st.error("Please enter a ticker (e.g., SPY).")
    else:
        df = fetch_daily_data(ticker)
        if df is None or df.empty:
            st.error("Could not fetch data for this ticker.")
        else:
            df = compute_indicators(df)
            if df.empty:
                st.error("Not enough clean data to compute indicators.")
            else:
                last = df.iloc[-1]

                price = float(last["Close"])
                vwap = float(last["VWAP"]) if not math.isnan(last["VWAP"]) else price
                rsi = float(last["RSI"])
                adx = float(last["ADX"])
                atr = float(last["ATR"])
                bbl_low = float(last["BB_Low"])
                bbl_high = float(last["BB_High"])

                trend_structure = infer_trend_structure(last)
                atr_trend = infer_atr_trend(df)

                iv, ivr = fetch_iv_and_ivr()
                dte = 30

                atr_pct = (atr / price) * 100 if price > 0 else 0
                move = expected_move(price, iv, dte)
                vwap_drift = abs(price - vwap) / price if price > 0 else 0

                last_bar_date = df.index[-1].date()
                market_closed, last_data_date = detect_market_closed(last_bar_date)

                decision, env_score, reasons = classify_trade(
                    price, vwap, rsi, adx, atr_pct, ivr,
                    bbl_low, bbl_high, vwap_drift,
                    atr_trend, trend_structure
                )

                strike = round(price)

                st.markdown("---")
                st.subheader(f"📈 {ticker} Analysis")

                if market_closed:
                    st.warning(f"Market is closed — using last available daily data ({last_data_date.isoformat()}).")

                if decision == "GO":
                    st.success(f"GO ✅ (Environment Score {env_score}/6)")
                elif decision == "CAUTION":
                    st.warning(f"CAUTION ⚠️ (Environment Score {env_score}/6)")
                else:
                    st.error(f"NO GO ⛔ (Environment Score {env_score}/6)")

                st.subheader("🧠 Reasoning")
                for r in reasons:
                    st.write(f"- {r}")

                st.subheader("📊 Key Metrics (Auto-Fetched)")
                st.write(f"- Price: {price:.2f}")
                st.write(f"- VWAP: {vwap:.2f}")
                st.write(f"- VWAP Drift: {vwap_drift*100:.2f}%")
                st.write(f"- ATR: {atr:.2f}")
                st.write(f"- ATR %: {atr_pct:.2f}%")
                st.write(f"- ATR Trend: {atr_trend}")
                st.write(f"- ADX: {adx:.1f}")
                st.write(f"- RSI: {rsi:.1f}")
                st.write(f"- BB Low: {bbl_low:.2f}")
                st.write(f"- BB High: {bbl_high:.2f}")
                st.write(f"- IV (proxy from VIX): {iv:.2f}%")
                st.write(f"- IV Rank (proxy): {ivr:.1f}")
                st.write(f"- Trend Structure: {trend_structure}")

                # ----------------- DOUBLE CALENDAR GO / NO-GO -----------------

                st.subheader("📘 Double Calendar GO / NO-GO")

                dc_decision, dc_reasons = double_calendar_go_no_go(
                    adx, rsi, vwap_drift, atr_pct, ivr,
                    atr_trend, trend_structure, env_score
                )

                if dc_decision == "GO":
                    st.success("Double Calendar: GO")
                    for r in dc_reasons:
                        st.write(f"- {r}")
                elif dc_decision == "CAUTION":
                    st.warning("Double Calendar: CAUTION")
                    for r in dc_reasons:
                        st.write(f"- {r}")
                else:
                    st.error("Double Calendar: NO GO")
                    st.write("Reasons:")
                    for r in dc_reasons:
                        st.write(f"- {r}")

                # ----------------- STRATEGY & SIZING -----------------

                st.subheader("🎯 Strategy Recommendation")
                strategy = recommend_strategy(
                    adx, rsi, vwap_drift, ivr,
                    trend_structure, atr_trend, env_score,
                    dc_decision
                )
                st.write(strategy)

                st.subheader("📏 Position Sizing")
                sizing = position_sizing(env_score, decision)
                st.write(sizing)

                st.subheader("📈 Expected Move (30D, IV Proxy)")
                st.write(f"± {move:.2f}")

                max_profit_low = strike - (move * 0.25)
                max_profit_high = strike + (move * 0.25)

                st.subheader("💰 Profit Zone (Single Calendar Approximation)")
                st.write(f"🟢 Max Profit: {max_profit_low:.2f} → {max_profit_high:.2f}")
                st.write(f"🟡 Expected Range: {price - move:.2f} → {price + move:.2f}")

                # ----------------- DOUBLE CALENDAR OPTIMIZER -----------------

                st.subheader("🎯 Double Calendar Optimizer")

                front_dte = 10
                back_dte = 45
                front_iv = iv * 0.8
                back_iv = iv

                if dc_decision == "NO GO":
                    st.info("Optimizer hidden — Double Calendar is a NO GO.")
                else:
                    best = double_calendar_optimizer(price, move, front_dte, back_dte, front_iv, back_iv)

                    if best:
                        st.write(f"Strike: {best['strike']}")
                        st.write(f"Front DTE: {best['front_dte']}")
                        st.write(f"Back DTE: {best['back_dte']}")
                        st.write(f"Score: {best['score']:.2f}")
                    else:
                        st.write("No suitable double-calendar configuration found.")

                # ----------------- REAL P&L -----------------

                st.subheader("📈 Real P&L Visualization (Single Calendar Approximation)")

                fig = real_calendar_pnl(price, strike, move, front_iv, back_iv, debit)
                st.pyplot(fig)

                # ----------------- JOURNAL -----------------

                if "journal" not in st.session_state:
                    st.session_state.journal = []

                st.session_state.journal.append({
                    "time": datetime.now().strftime("%H:%M"),
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "ticker": ticker,
                    "decision": decision,
                    "env_score": env_score,
                    "strike": strike,
                    "strategy": strategy,
                    "sizing": sizing
                })

# ----------------- JOURNAL -----------------

st.markdown("---")
st.subheader("📓 Trade Journal")

if "journal" in st.session_state:
    for j in reversed(st.session_state.journal):
        st.write(j)
else:
    st.write("No trades yet.")
