import requests
import json
import time
from datetime import datetime

# ===================== CONFIGURATION =====================
TOKEN = "8779800260:AAG2j2yWHDpULU6_vNxzpVRPwlUy457xZkM"
CHAT_ID = "5967309975"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# Portfolio stocks - symbol: (name, buy_price, quantity)
# Using Yahoo Finance symbols for Egyptian Stock Exchange
STOCKS = {
    "MCQE.CA": ("ميدار", 1.50, 1000),
    "ABUK.CA": ("ابو قير", 15.00, 100),
    "CIRA.CA": ("سيرا", 20.00, 100),
    "IRON.CA": ("الحديد والصلب", 5.00, 500),
    "CCRS.CA": ("كيما", 8.00, 300),
    "PHDC.CA": ("التعمير", 10.00, 200),
    "SWDY.CA": ("السويدي", 12.00, 150),
    "MNHD.CA": ("مدينة نصر", 7.00, 400),
    "EFIH.CA": ("ايفي", 3.00, 600),
    "CLHO.CA": ("سيلا", 4.00, 500),
    "ORWE.CA": ("اورى", 6.00, 300),
    "ALCN.CA": ("الكندي", 9.00, 200),
    "SCEM.CA": ("سيمكو", 11.00, 180),
    "ARCC.CA": ("النصر", 2.50, 800),
    "PRTM.CA": ("بريم", 13.00, 120),
    "EGTS.CA": ("مصر", 18.00, 110),
    "DCRC.CA": ("دبكا", 3.50, 700),
}

TRAILING_STOP_PCT = 5.0
LIMIT_BUY_DROP_PCT = 10.0
highest_prices = {}
state_file = "/tmp/egx_state.json"

def load_state():
    global highest_prices
    try:
        with open(state_file, "r") as f:
            highest_prices = json.load(f)
    except Exception:
        highest_prices = {}

def save_state():
    try:
        with open(state_file, "w") as f:
            json.dump(highest_prices, f)
    except Exception:
        pass

def send_message(text):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

def get_stock_price(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        result = data.get("chart", {}).get("result")
        if result is None:
            return None
        closes = result[0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if closes:
            return closes[-1]
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
    return None

def pct_change(old, new):
    if old == 0:
        return 0
    return ((new - old) / old) * 100

def fmt_num(n):
    """Format number with commas and sign"""
    if n >= 0:
        return f"+{n:,.0f}"
    return f"{n:,.0f}"

def fmt_pct(p):
    if p >= 0:
        return f"+{p:.1f}%"
    return f"{p:.1f}%"

def analyze_portfolio():
    load_state()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    report_lines = [f"\U0001f4ca <b>\u062a\u0642\u0631\u064a\u0631 \u0645\u062d\u0641\u0638\u0629 EGX</b> - {now}\n"]
    sell_alerts = []
    buy_alerts = []
    total_cost = 0
    total_current = 0
    found_any = False

    for symbol, (name, buy_price, qty) in STOCKS.items():
        current = get_stock_price(symbol)
        if current is None:
            report_lines.append(f"\u26a0\ufe0f {name}: \u0644\u0627 \u062a\u0648\u062c\u062f \u0628\u064a\u0627\u0646\u0627\u062a")
            continue

        found_any = True
        cost = buy_price * qty
        current_value = current * qty
        total_cost += cost
        total_current += current_value
        change_pct = pct_change(buy_price, current)
        profit = current_value - cost

        if change_pct >= 5:
            emoji = "\U0001f7e2"
        elif change_pct <= -5:
            emoji = "\U0001f534"
        else:
            emoji = "\U0001f7e1"

        report_lines.append(
            f"{emoji} <b>{name}</b>: {current:.2f} \u062c\u0646\u064a\u0647 "
            f"({fmt_pct(change_pct)}) | \u0631\u0628\u062d/\u062e\u0633\u0627\u0631\u0629: {fmt_num(profit)} \u062c\u0646\u064a\u0647"
        )

        if symbol not in highest_prices or current > highest_prices[symbol]:
            highest_prices[symbol] = current

        peak = highest_prices[symbol]
        drop_from_peak = pct_change(peak, current)

        if drop_from_peak <= -TRAILING_STOP_PCT and change_pct < 0:
            sell_alerts.append(
                f"\U0001f6a8 <b>\u062a\u062d\u0630\u064a\u0631 \u0628\u064a\u0639 - {name}</b>\n"
                f"\u0627\u0644\u0633\u0639\u0631 \u0627\u0644\u062d\u0627\u0644\u064a: {current:.2f} | \u0623\u0639\u0644\u0649 \u0633\u0639\u0631: {peak:.2f}\n"
                f"\u0627\u0646\u062e\u0641\u0636 {abs(drop_from_peak):.1f}% - \u0641\u0643\u0631 \u0641\u064a \u0627\u0644\u0628\u064a\u0639!"
            )

        if change_pct > 0 and drop_from_peak <= -LIMIT_BUY_DROP_PCT:
            buy_alerts.append(
                f"\U0001f4b0 <b>\u0641\u0631\u0635\u0629 \u0634\u0631\u0627\u0621 - {name}</b>\n"
                f"\u0627\u0644\u0633\u0639\u0631: {current:.2f} | \u0627\u0646\u062e\u0641\u0636 {abs(drop_from_peak):.1f}% \u0645\u0646 \u0627\u0644\u0630\u0631\u0648\u0629\n"
                f"\u0641\u0631\u0635\u0629 \u0644\u0644\u0634\u0631\u0627\u0621 \u0642\u0628\u0644 \u0627\u0644\u0627\u0631\u062a\u062f\u0627\u062f!"
            )

    if found_any:
        total_profit = total_current - total_cost
        total_pct = pct_change(total_cost, total_current)
        summary = (
            f"\n\U0001f4b3 <b>\u0645\u0644\u062e\u0635 \u0627\u0644\u0645\u062d\u0641\u0638\u0629:</b>\n"
            f"\u0627\u0644\u062a\u0643\u0644\u0641\u0629: {total_cost:,.0f} \u062c\u0646\u064a\u0647\n"
            f"\u0627\u0644\u0642\u064a\u0645\u0629 \u0627\u0644\u062d\u0627\u0644\u064a\u0629: {total_current:,.0f} \u062c\u0646\u064a\u0647\n"
            f"\u0627\u0644\u0631\u0628\u062d/\u0627\u0644\u062e\u0633\u0627\u0631\u0629: {fmt_num(total_profit)} \u062c\u0646\u064a\u0647 ({fmt_pct(total_pct)})"
        )
        report_lines.append(summary)

    send_message("\n".join(report_lines))

    for alert in sell_alerts:
        send_message(alert)
        time.sleep(0.5)

    for alert in buy_alerts:
        send_message(alert)
        time.sleep(0.5)

    if not sell_alerts and not buy_alerts:
        send_message("\u2705 \u0644\u0627 \u062a\u0648\u062c\u062f \u062a\u0646\u0628\u064a\u0647\u0627\u062a \u0627\u0644\u064a\u0648\u0645. \u0627\u0644\u0645\u062d\u0641\u0638\u0629 \u0641\u064a \u0648\u0636\u0639 \u0627\u0644\u0645\u0631\u0627\u0642\u0628\u0629.")

    save_state()
    print(f"Done at {now}")

if __name__ == "__main__":
    analyze_portfolio()
