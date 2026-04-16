#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import requests

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Test signal message
message = """🟢 <b>إشارة شراء عالية الاحتمالية</b> ↗️
📊 <b>الأصل:</b> XAUUSD | الذهب
⏰ <b>الوقت:</b> 2026-04-16 19:00:00
🎯 <b>نوع الصفقة:</b> شراء

<b>─── تفاصيل الصفقة ───</b>
💲 <b>سعر الدخول:</b> 2385.50
🛡️ <b>وقف الخسارة (SL):</b> 2378.00
🎯 <b>الهدف الأول (TP1):</b> 2396.75
🎯🎯 <b>الهدف الثاني (TP2):</b> 2408.00  
🎯🎯🎯 <b>الهدف الثالث (TP3):</b> 2430.50

<b>─── إدارة المخاطرة ───</b>
📋 <b>الاسبريد:</b> 0.5
⚠️ <b>الخطر بالبيبس:</b> 75 نقطة
💰 <b>العائد بالبيبس:</b> 225 نقطة
⚖️ <b>نسبة عائد/مخاطرة (RR):</b> 3.0:1
⏱️ <b>المدة المتوقعة:</b> 3-6 ساعات

<b>─── التحليل الفني ───</b>
📈 <b>الاتجاه العام (يومي):</b> صاعد
🏗️ <b>البنية السعرية:</b> BULLISH
💯 <b>احتمالية النجاح:</b> 82%
██████████░░

<b>✔️ أسباب الدخول:</b>
• اتجاه صاعد على اليومي
• RSI في منطقة تشبع بيع
• StochRSI إشارة شراء
• MACD تقاطع صاعد
• بالقرب من الدعم

<b>─── تعليمات الدخول ───</b>
1️⃣ انتظر تأكيد السعر عند 2385.50
2️⃣ ضع SL عند 2378.00 بالضبط
3️⃣ اخرج نصف الصفقة عند TP1 = 2396.75
4️⃣ أحرك SL للتعادل بعد TP1
5️⃣ اجلس للهدف TP2 = 2408.00

⚠️ <i>هذا المحتوى تعليمي فقط وليس نصيحة مالية متخصصة.</i>
🔒 <b>دائماً ادر مخاطرك!</b>
"""

try:
    url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
    data = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    response = requests.post(url, data=data, timeout=10)
    if response.status_code == 200:
        print("✅ Test signal sent successfully to Telegram!")
    else:
        print(f"❌ Failed to send: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
