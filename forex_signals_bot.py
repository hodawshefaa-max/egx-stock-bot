import requests
import os
import json
import time
from datetime import datetime

# =================== CONFIG ===================
TOKEN = os.getenv('TELEGRAM_TOKEN', '8779800260:AAG2j2yWHDpOLU6_vNxzpVRPwlUy457xZkM')
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
CHAT_ID = os.getenv('CHAT_ID', '5967309975')
STATE_FILE = "/tmp/forex_state.json"

# Pairs to monitor
PAIRS = {
    "XAUUSD=X": "ذهب XAU/USD",
    "EURUSD=X": "يورو EUR/USD",
    "GBPUSD=X": "جنيه GBP/USD",
    "USDJPY=X": "دولار/ين USD/JPY",
    "USDCHF=X": "دولار/فرنك USD/CHF",
}

# =================== HELPERS ===================
def send_message(text):
    url = f"{BASE_URL}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        print(f"Send error: {e}")

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except:
        pass

def get_price_data(symbol):
    """Get OHLC data for RSI and MA calculation"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=15m&range=2d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return None
        q = result[0]["indicators"]["quote"][0]
        closes = [c for c in q["close"] if c is not None]
        highs = [h for h in q["high"] if h is not None]
        lows = [l for l in q["low"] if l is not None]
        if len(closes) < 20:
            return None
        return {"closes": closes, "highs": highs, "lows": lows}
    except Exception as e:
        print(f"Price error {symbol}: {e}")
        return None

def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[-period + i] - closes[-period + i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calc_ma(closes, period):
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period

def calc_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1])
        )
        trs.append(tr)
    return sum(trs) / period

def detect_signal(symbol, name, data, state):
    """Detect BUY/SELL signal using RSI + MA crossover + ATR"""
    closes = data["closes"]
    highs = data["highs"]
    lows = data["lows"]
    price = closes[-1]

    rsi = calc_rsi(closes)
    ma20 = calc_ma(closes, 20)
    ma50 = calc_ma(closes, 50)
    ma20_prev = calc_ma(closes[:-1], 20)
    ma50_prev = calc_ma(closes[:-1], 50)
    atr = calc_atr(highs, lows, closes)

    if None in [rsi, ma20, ma50, ma20_prev, ma50_prev, atr]:
        return None

    signals = []
    last_signal = state.get(symbol, {}).get("last_signal", "")
    last_price = state.get(symbol, {}).get("last_price", 0)

    # Avoid spam: only alert if price moved significantly
    price_change_pct = abs(price - last_price) / last_price * 100 if last_price > 0 else 999

    # === BUY SIGNAL: RSI oversold + MA golden cross ===
    buy_condition = (
        rsi < 35 and
        ma20 > ma50 and
        (ma20_prev <= ma50_prev or rsi < 30) and
        last_signal != "BUY"
    )

    # === SELL SIGNAL: RSI overbought + MA death cross ===
    sell_condition = (
        rsi > 65 and
        ma20 < ma50 and
        (ma20_prev >= ma50_prev or rsi > 70) and
        last_signal != "SELL"
    )

    tp_multiplier = 2.0
    sl_multiplier = 1.0

    if buy_condition:
        tp1 = price + (atr * tp_multiplier)
        tp2 = price + (atr * tp_multiplier * 1.5)
        sl = price - (atr * sl_multiplier)
        rr = (tp1 - price) / (price - sl) if (price - sl) > 0 else 0
        if rr >= 1.5:  # Only alert if Risk/Reward >= 1.5
            signals.append(("BUY", price, tp1, tp2, sl, rsi, rr))

    elif sell_condition:
        tp1 = price - (atr * tp_multiplier)
        tp2 = price - (atr * tp_multiplier * 1.5)
        sl = price + (atr * sl_multiplier)
        rr = (price - tp1) / (sl - price) if (sl - price) > 0 else 0
        if rr >= 1.5:
            signals.append(("SELL", price, tp1, tp2, sl, rsi, rr))

    return signals[0] if signals else None

def format_price(symbol, price):
    if "JPY" in symbol:
        return f"{price:.3f}"
    elif "XAU" in symbol:
        return f"{price:.2f} $"
    else:
        return f"{price:.5f}"

def build_message(symbol, name, sig):
    direction, price, tp1, tp2, sl, rsi, rr = sig
    now = datetime.utcnow().strftime("%H:%M UTC")
    emoji_dir = "\U0001f7e2" if direction == "BUY" else "\U0001f534"
    arrow = "\u2191" if direction == "BUY" else "\u2193"

    msg = (
        f"\U0001f6a8 <b>\u0641\u0631\u0635\u0629 {direction} \u0644\u062d\u0638\u064a\u0629!</b>\n"
        f"{emoji_dir} <b>{name}</b> {arrow}\n"
        f"\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\n"
        f"\U0001f4cd \u0633\u0639\u0631 \u0627\u0644\u062f\u062e\u0648\u0644: <b>{format_price(symbol, price)}</b>\n"
        f"\U0001f3af \u0627\u0644\u0647\u062f\u0641 1 (TP1): {format_price(symbol, tp1)}\n"
        f"\U0001f3af \u0627\u0644\u0647\u062f\u0641 2 (TP2): {format_price(symbol, tp2)}\n"
        f"\U0001f6d1 \u0648\u0642\u0641 \u0627\u0644\u062e\u0633\u0627\u0631\u0629 (SL): {format_price(symbol, sl)}\n"
        f"\U0001f4ca RSI: {rsi:.1f} | R/R: 1:{rr:.1f}\n"
        f"\U0001f550 {now}\n"
        f"\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\u2015\n"
        f"\u26a0\ufe0f \u0644\u0644\u062a\u062b\u0642\u064a\u0641 \u0641\u0642\u0637 - \u0644\u064a\u0633 \u0646\u0635\u064a\u062d\u0629 \u0645\u0627\u0644\u064a\u0629"
    )
    return msg

# =================== MAIN ===================
def run():
    state = load_state()
    now = datetime.utcnow()
    hour = now.hour
    # Only run during forex market hours (Mon-Fri, 00:00-22:00 UTC)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:  # Weekend
        print("Weekend - market closed")
        return

    found_any = False
    for symbol, name in PAIRS.items():
        data = get_price_data(symbol)
        if not data:
            continue
        sig = detect_signal(symbol, name, data, state)
        if sig:
            direction = sig[0]
            price = sig[1]
            msg = build_message(symbol, name, sig)
            send_message(msg)
            # Update state to avoid duplicate alerts
            state[symbol] = {"last_signal": direction, "last_price": price}
            found_any = True
            time.sleep(1)

    save_state(state)
    if found_any:
        print(f"Signals sent at {now.strftime('%H:%M')}")
    else:
        print(f"No signals at {now.strftime('%H:%M')} - market scanning...")

if __name__ == "__main__":
    run()
