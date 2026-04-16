import requests
import json
import time
from datetime import datetime

# ===================== CONFIGURATION =====================
TOKEN = "8779800260:AAG2j2yWHDpULU6_vNxzpVRPwlUy457xZkM"
CHAT_ID = "5967309975"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# Portfolio stocks - symbol: (name, buy_price, quantity)
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

# Trailing stop: sell alert when price drops X% from peak
TRAILING_STOP_PCT = 5.0  # 5% drop from peak triggers sell alert

# Limit buy: alert when price drops X% below current (good stocks)
LIMIT_BUY_DROP_PCT = 10.0  # 10% drop triggers buy alert

# Track highest prices seen for trailing stop
highest_prices = {}
state_file = "/tmp/egx_state.json"

# ===================== HELPERS =====================
def load_state():
    global highest_prices
    try:
        with open(state_file, "r") as f:
            highest_prices = json.load(f)
    except:
        highest_prices = {}

def save_state():
    with open(state_file, "w") as f:
        json.dump(highest_prices, f)

def send_message(text):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Error sending message: {e}")

def get_stock_price(symbol):
    """Get current price from Yahoo Finance"""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
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

# ===================== MAIN LOGIC =====================
def analyze_portfolio():
    load_state()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    report_lines = [f"\U0001f4ca <b>تقرير محفظة EGX</b> - {now}\n"]
    sell_alerts = []
    buy_alerts = []
    
    total_cost = 0
    total_current = 0
    
    for symbol, (name, buy_price, qty) in STOCKS.items():
        current = get_stock_price(symbol)
        if current is None:
            report_lines.append(f"\u26a0\ufe0f {name} ({symbol}): لا توجد بيانات")
            continue
        
        cost = buy_price * qty
        current_value = current * qty
        total_cost += cost
        total_current += current_value
        
        change_pct = pct_change(buy_price, current)
        profit = current_value - cost
        
        # Emoji for gain/loss
        if change_pct >= 5:
            emoji = "\U0001f7e2"  # green
        elif change_pct <= -5:
            emoji = "\U0001f534"  # red
        else:
            emoji = "\U0001f7e1"  # yellow
        
        report_lines.append(
            f"{emoji} <b>{name}</b>: {current:.2f} جنيه "
            f"({'%+.1f' % change_pct}%) | ربح/خسارة: {'%+.0f' % profit} جنيه"
        )
        
        # === TRAILING STOP LOGIC ===
        if symbol not in highest_prices or current > highest_prices[symbol]:
            highest_prices[symbol] = current
        
        peak = highest_prices[symbol]
        drop_from_peak = pct_change(peak, current)
        
        if drop_from_peak <= -TRAILING_STOP_PCT and change_pct < 0:
            sell_alerts.append(
                f"\U0001f6a8 <b>تحذير بيع - {name}</b>\n"
                f"السعر الحالي: {current:.2f} | أعلى سعر: {peak:.2f}\n"
                f"انخفض {abs(drop_from_peak):.1f}% من الذروة - فكر في البيع لتقليل الخسارة!"
            )
        
        # === LIMIT BUY LOGIC (for stocks performing well) ===
        if change_pct > 0:  # Good stock (above buy price)
            prev_peak_drop = pct_change(peak, current)
            if prev_peak_drop <= -LIMIT_BUY_DROP_PCT:
                buy_alerts.append(
                    f"\U0001f4b0 <b>فرصة شراء - {name}</b>\n"
                    f"السعر: {current:.2f} | انخفض {abs(prev_peak_drop):.1f}% من الذروة\n"
                    f"فرصة للشراء عند أقل سعر قبل الارتداد!"
                )
    
    # Portfolio summary
    total_profit = total_current - total_cost
    total_pct = pct_change(total_cost, total_current)
    summary = (
        f"\n\U0001f4b3 <b>ملخص المحفظة:</b>\n"
        f"التكلفة الإجمالية: {total_cost:,.0f} جنيه\n"
        f"القيمة الحالية: {total_current:,.0f} جنيه\n"
        f"إجمالي الربح/الخسارة: {'%+,.0f' % total_profit} جنيه ({'%+.1f' % total_pct}%)"
    )
    report_lines.append(summary)
    
    # Send main report
    send_message("\n".join(report_lines))
    
    # Send alerts
    for alert in sell_alerts:
        send_message(alert)
        time.sleep(0.5)
    
    for alert in buy_alerts:
        send_message(alert)
        time.sleep(0.5)
    
    if not sell_alerts and not buy_alerts:
        send_message("\u2705 لا توجد تنبيهات اليوم. المحفظة في وضع المراقبة.")
    
    save_state()
    print(f"Report sent at {now}")

if __name__ == "__main__":
    analyze_portfolio()
