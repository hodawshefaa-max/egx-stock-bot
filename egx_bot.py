import requests
from datetime import datetime

TOKEN = "8728052970:AAEUs3BOSvqSS_O2dvAVzVhvsO3vG3PqLxo"
CHAT_ID = "5967309975"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

STOCKS = {
    "MCQE.CA": "MCQE - ميدار",
    "ABUK.CA": "ABUK - ابو قير",
    "CIRA.CA": "CIRA - سيرا",
    "IRON.CA": "IRON - الحديد والصلب",
    "CCRS.CA": "CCRS - كيما",
    "PHDC.CA": "PHDC - التعمير",
    "SWDY.CA": "SWDY - السويدي",
    "MNHD.CA": "MNHD - مدينة نصر",
    "EFIH.CA": "EFIH - ايفي",
    "CLHO.CA": "CLHO - سيلا",
    "ORWE.CA": "ORWE - اورى",
    "ALCN.CA": "ALCN - الكندي",
    "SCEM.CA": "SCEM - سيمكو",
    "ARCC.CA": "ARCC - النصر",
    "PRTM.CA": "PRTM - بريم",
    "EGTS.CA": "EGTS - مصر",
    "DCRC.CA": "DCRC - ديلتا",
}

def get_stock_data(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, timeout=15, headers=headers)
        data = r.json()
        result = data["chart"]["result"]
        if not result:
            return None
        meta = result[0]["meta"]
        return {
            "price": meta.get("regularMarketPrice", 0),
            "high52": meta.get("fiftyTwoWeekHigh", 0),
            "low52": meta.get("fiftyTwoWeekLow", 0),
            "prev_close": meta.get("chartPreviousClose", 0),
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def analyze_stock(name, data):
    price = data["price"]
    high52 = data["high52"]
    low52 = data["low52"]
    prev = data["prev_close"]

    change = ((price - prev) / prev * 100) if prev else 0
    total_range = high52 - low52
    range_pos = ((price - low52) / total_range * 100) if total_range else 50

    if price >= high52 * 0.95:
        signal = "SELL - وصل للقمة"
        emoji = "\U0001f534"
    elif range_pos <= 20:
        signal = "BUY - عند القاع"
        emoji = "\U0001f7e2"
    elif range_pos <= 45:
        signal = "ACCUMULATE - فرصة جيدة"
        emoji = "\U0001f7e1"
    else:
        signal = "HOLD - انتظر"
        emoji = "\u26aa"

    change_icon = "\U0001f4c8" if change > 0 else "\U0001f4c9" if change < 0 else "\u27a1\ufe0f"

    return (
        f"{emoji} <b>{name}</b>\n"
        f"   {price:.2f} ج {change_icon} {change:+.2f}%\n"
        f"   52W: {low52:.2f} - {high52:.2f} | موقع: {range_pos:.0f}%\n"
        f"   {signal}\n"
    ), signal

def send_daily_report():
    today = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [f"\U0001f4ca <b>تقرير محفظة EGX - {today}</b>\n"]

    urgent_alerts = []
    buy_opps = []

    for symbol, name in STOCKS.items():
        data = get_stock_data(symbol)
        if data and data["price"] > 0:
            analysis, signal = analyze_stock(name, data)
            lines.append(analysis)
            if "SELL" in signal:
                urgent_alerts.append(f"\u26a0\ufe0f {name} @ {data['price']:.2f} ج - BIE: قرب القمة!")
            elif "BUY" in signal:
                buy_opps.append(f"\U0001f4a1 {name} @ {data['price']:.2f} ج - فرصة شراء")
        else:
            lines.append(f"\u26aa <b>{name}</b> - لا يوجد بيانات\n")

    if urgent_alerts:
        lines.append("\n\U0001f6a8 <b>تنبيهات بيع عاجلة:</b>")
        lines.extend(urgent_alerts)

    if buy_opps:
        lines.append("\n\U0001f7e2 <b>فرص شراء:</b>")
        lines.extend(buy_opps)

    lines.append("\n\u23f0 التقرير التالي غدا بإذن الله")

    message = "\n".join(lines)
    response = requests.post(f"{BASE_URL}/sendMessage", data={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    })
    result = response.json()
    if result.get("ok"):
        print("Report sent successfully")
    else:
        print(f"Error: {result}")

if __name__ == "__main__":
    send_daily_report()
