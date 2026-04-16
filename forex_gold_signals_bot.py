#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Forex & Gold Professional Technical Analysis Signal Bot
بوت تحليل فني احترافي للفوركس والذهب

Features:
- Advanced Technical Analysis (Market Structure, S&R, Supply/Demand, Fibonacci)
- Multi-Indicator Confirmation (RSI, MACD, Stochastic RSI)
- High-Probability Setups Only
- Spread Calculation & Risk Management
- Real-time Telegram Alerts
- Focus on XAUUSD + Top 3-5 Clear Forex Pairs
"""

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from ta.momentum import RSIIndicator, StochasticOscillator, StochRSIIndicator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator

# ==================== CONFIGURATION ====================

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Assets to analyze (Priority: XAUUSD)
ASSETS = {
    'XAUUSD': {'symbol': 'GC=F', 'name': 'الذهب', 'spread': 0.50, 'pip_value': 0.10, 'priority': 1},
    'EURUSD': {'symbol': 'EURUSD=X', 'name': 'اليورو/دولار', 'spread': 0.00015, 'pip_value': 0.0001, 'priority': 2},
    'GBPUSD': {'symbol': 'GBPUSD=X', 'name': 'الجنيه/دولار', 'spread': 0.00020, 'pip_value': 0.0001, 'priority': 3},
    'USDJPY': {'symbol': 'USDJPY=X', 'name': 'دولار/ين', 'spread': 0.015, 'pip_value': 0.01, 'priority': 4},
    'AUDUSD': {'symbol': 'AUDUSD=X', 'name': 'الدولار الاسترالي', 'spread': 0.00018, 'pip_value': 0.0001, 'priority': 5},
}

# Minimum confidence score to send signal (0-100)
MIN_CONFIDENCE = 75

# Risk Management
RISK_REWARD_RATIO = 2.0  # Minimum RR ratio
MAX_RISK_PERCENT = 2.0  # Max risk per trade

# Timeframes for analysis
TIMEFRAMES = {
    'trend': '1d',  # Daily for trend
    'entry': '15m'  # 15-minute for entry
}

STATE_FILE = 'forex_signals_state.json'

# ==================== HELPER FUNCTIONS ====================

class ForexSignalBot:
    def __init__(self):
        self.sent_signals = {}
        self.load_state()
    
    def load_state(self):
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.sent_signals = data.get('sent_signals', {})
        except:
            self.sent_signals = {}
    
    def save_state(self):
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({'sent_signals': self.sent_signals}, f)
        except:
            pass
    
    def send_telegram(self, message):
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
            data = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def get_data(self, symbol, timeframe='15m', period='5d'):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=timeframe)
            return df if not df.empty else None
        except:
            return None
    
    def calculate_indicators(self, df):
        """Calculate all technical indicators"""
        # Trend indicators
        df['EMA_8'] = EMAIndicator(df['Close'], window=8).ema_indicator()
        df['EMA_21'] = EMAIndicator(df['Close'], window=21).ema_indicator()
        df['EMA_50'] = EMAIndicator(df['Close'], window=50).ema_indicator()
        df['EMA_200'] = EMAIndicator(df['Close'], window=200).ema_indicator()
        
        # Momentum
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        df['RSI_fast'] = RSIIndicator(df['Close'], window=7).rsi()
        
        # Stochastic RSI
        stoch_rsi = StochRSIIndicator(df['Close'], window=14, smooth1=3, smooth2=3)
        df['StochRSI_K'] = stoch_rsi.stochrsi_k()
        df['StochRSI_D'] = stoch_rsi.stochrsi_d()
        
        # MACD
        macd = MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_hist'] = macd.macd_diff()
        
        # ADX for trend strength
        adx = ADXIndicator(df['High'], df['Low'], df['Close'], window=14)
        df['ADX'] = adx.adx()
        df['DI_plus'] = adx.adx_pos()
        df['DI_minus'] = adx.adx_neg()
        
        # Volatility
        bb = BollingerBands(df['Close'], window=20, window_dev=2)
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_middle'] = bb.bollinger_mavg()
        df['BB_lower'] = bb.bollinger_lband()
        df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle'] * 100
        
        atr = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14)
        df['ATR'] = atr.average_true_range()
        
        # Support & Resistance
        df['Resistance'] = df['High'].rolling(20).max()
        df['Support'] = df['Low'].rolling(20).min()
        
        # Volume
        if 'Volume' in df.columns:
            df['Volume_MA'] = df['Volume'].rolling(20).mean()
            df['OBV'] = OnBalanceVolumeIndicator(df['Close'], df['Volume']).on_balance_volume()
        
        return df

    def detect_market_structure(self, df):
        """Detect market structure (Higher Highs, Lower Lows)"""
        latest = df.iloc[-1]
        prev_high = df['High'].iloc[-20:-1].max()
        prev_low = df['Low'].iloc[-20:-1].min()
        
        if latest['High'] > prev_high and latest['Low'] > prev_low:
            return 'BULLISH'  # Higher highs, higher lows
        elif latest['High'] < prev_high and latest['Low'] < prev_low:
            return 'BEARISH'  # Lower highs, lower lows
        else:
            return 'RANGING'  # Sideways
    
    def calculate_fibonacci(self, df, lookback=100):
        """Calculate Fibonacci retracement levels"""
        recent_data = df.tail(lookback)
        high = recent_data['High'].max()
        low = recent_data['Low'].min()
        diff = high - low
        
        levels = {
            '0': high,
            '23.6': high - (diff * 0.236),
            '38.2': high - (diff * 0.382),
            '50.0': high - (diff * 0.5),
            '61.8': high - (diff * 0.618),
            '78.6': high - (diff * 0.786),
            '100': low
        }
        return levels
    
    def generate_signal(self, asset_name, asset_info):
        """Generate high-probability trading signal"""
        symbol = asset_info['symbol']
        spread = asset_info['spread']
        
        # Get data for both timeframes
        df_trend = self.get_data(symbol, '1d', '90d')
        df_entry = self.get_data(symbol, '15m', '7d')
        
        if df_trend is None or df_entry is None:
            return None
        
        if len(df_trend) < 50 or len(df_entry) < 200:
            return None
        
        # Calculate indicators
        df_trend = self.calculate_indicators(df_trend)
        df_entry = self.calculate_indicators(df_entry)
        
        latest_trend = df_trend.iloc[-1]
        latest_entry = df_entry.iloc[-1]
        prev_entry = df_entry.iloc[-2]
        
        # Market structure
        structure = self.detect_market_structure(df_entry)
        
        # Fibonacci levels
        fib_levels = self.calculate_fibonacci(df_entry, 200)
        
        current_price = latest_entry['Close']
        
        # === SIGNAL GENERATION WITH STRICT CONDITIONS ===
        
        signal = None
        confidence = 0
        reasons = []
        
        # Check trend alignment (Daily)
        trend_bullish = (latest_trend['EMA_8'] > latest_trend['EMA_21'] and
                        latest_trend['EMA_21'] > latest_trend['EMA_50'])
        trend_bearish = (latest_trend['EMA_8'] < latest_trend['EMA_21'] and
                        latest_trend['EMA_21'] < latest_trend['EMA_50'])
        
        # === BUY CONDITIONS ===
        buy_conditions = 0
        buy_reasons = []
        
        if trend_bullish:
            buy_conditions += 1
            buy_reasons.append('اتجاه صاعد على اليومي')
        
        # RSI oversold + bounce
        if latest_entry['RSI'] < 35 and latest_entry['RSI'] > prev_entry['RSI']:
            buy_conditions += 1
            buy_reasons.append('RSI في منطقة تشبع بيع')
        
        # StochRSI buy signal
        if (latest_entry['StochRSI_K'] < 20 and latest_entry['StochRSI_K'] > latest_entry['StochRSI_D']):
            buy_conditions += 1
            buy_reasons.append('StochRSI إشارة شراء')
        
        # MACD bullish crossover
        if (latest_entry['MACD'] > latest_entry['MACD_signal'] and
            prev_entry['MACD'] <= prev_entry['MACD_signal']):
            buy_conditions += 1
            buy_reasons.append('MACD تقاطع صاعد')
        
        # Price near support
        distance_to_support = ((current_price - latest_entry['Support']) / current_price) * 100
        if distance_to_support < 0.5:
            buy_conditions += 1
            buy_reasons.append('بالقرب من الدعم')
        
        # Bullish market structure
        if structure == 'BULLISH':
            buy_conditions += 1
            buy_reasons.append('بنية سعرية صاعدة')
        
        # Strong trend (ADX)
        if latest_entry['ADX'] > 25 and latest_entry['DI_plus'] > latest_entry['DI_minus']:
            buy_conditions += 1
            buy_reasons.append('اتجاه قوي صاعد')
        
        # === SELL CONDITIONS ===
        sell_conditions = 0
        sell_reasons = []
        
        if trend_bearish:
            sell_conditions += 1
            sell_reasons.append('اتجاه هابط على اليومي')
        
        # RSI overbought + rejection
        if latest_entry['RSI'] > 65 and latest_entry['RSI'] < prev_entry['RSI']:
            sell_conditions += 1
            sell_reasons.append('RSI في منطقة تشبع شراء')
        
        # StochRSI sell signal
        if (latest_entry['StochRSI_K'] > 80 and latest_entry['StochRSI_K'] < latest_entry['StochRSI_D']):
            sell_conditions += 1
            sell_reasons.append('StochRSI إشارة بيع')
        
        # MACD bearish crossover
        if (latest_entry['MACD'] < latest_entry['MACD_signal'] and
            prev_entry['MACD'] >= prev_entry['MACD_signal']):
            sell_conditions += 1
            sell_reasons.append('MACD تقاطع هابط')
        
        # Price near resistance
        distance_to_resistance = ((latest_entry['Resistance'] - current_price) / current_price) * 100
        if distance_to_resistance < 0.5:
            sell_conditions += 1
            sell_reasons.append('بالقرب من المقاومة')
        
        # Bearish market structure
        if structure == 'BEARISH':
            sell_conditions += 1
            sell_reasons.append('بنية سعرية هابطة')
        
        # Strong trend (ADX)
        if latest_entry['ADX'] > 25 and latest_entry['DI_minus'] > latest_entry['DI_plus']:
            sell_conditions += 1
            sell_reasons.append('اتجاه قوي هابط')
        
        # === DECISION ===
        # Require minimum 5 conditions for high probability
        if buy_conditions >= min_conditions_required:            signal = 'BUY'
            confidence = min(100, 50 + (buy_conditions * 8))
            reasons = buy_reasons
        elif sell_conditions >= min_conditions_required:                    # Lower threshold for Gold (XAUUSD) for more signals
                                    signal = 'SELL'
            reasons = sell_reasons
        
        if signal is None or confidence < MIN_CONFIDENCE:
            return None
        
        # === CALCULATE ENTRY, SL, TP ===
        atr = latest_entry['ATR']
        
        if signal == 'BUY':
            entry_price = current_price + spread  # Account for spread
            stop_loss = max(latest_entry['Support'], entry_price - (atr * 1.5))
            risk = entry_price - stop_loss
            target1 = entry_price + (risk * 1.5)
            target2 = entry_price + (risk * 2.0)
            target3 = entry_price + (risk * 3.0)
        else:  # SELL
            entry_price = current_price - spread
            stop_loss = min(latest_entry['Resistance'], entry_price + (atr * 1.5))
            risk = stop_loss - entry_price
            target1 = entry_price - (risk * 1.5)
            target2 = entry_price - (risk * 2.0)
            target3 = entry_price - (risk * 3.0)
        
        # Check risk/reward ratio
        rr_ratio = (target2 - entry_price) / risk if signal == 'BUY' else (entry_price - target2) / risk
        if rr_ratio < RISK_REWARD_RATIO:
            return None  # Not worth the risk
        
        # Estimate duration based on ATR and historical volatility
        volatility = df_entry['Close'].pct_change().std() * 100
        if volatility > 2:
            estimated_duration = '1-3 ساعات'  # High volatility = fast
        elif volatility > 1:
            estimated_duration = '3-6 ساعات'
        else:
            estimated_duration = '6-12 ساعة'
        
        return {
            'asset': asset_name,
            'asset_ar': asset_info['name'],
            'signal': signal,
            'entry': round(entry_price, 5),
            'stop_loss': round(stop_loss, 5),
            'target1': round(target1, 5),
            'target2': round(target2, 5),
            'target3': round(target3, 5),
            'confidence': confidence,
            'reasons': reasons,
            'spread': spread,
            'risk_pips': abs(round((entry_price - stop_loss) / asset_info['pip_value'], 1)),
            'reward_pips': abs(round((target2 - entry_price) / asset_info['pip_value'], 1)),
            'rr_ratio': round(rr_ratio, 2),
            'duration': estimated_duration,
            'structure': structure,
            'trend': 'صاعد' if trend_bullish else 'هابط' if trend_bearish else 'عرضي',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def format_signal_message(self, signal_data):
        """Format professional Arabic signal message for Telegram"""
        d = signal_data
        signal = d['signal']
        emoji = '🟢' if signal == 'BUY' else '🔴'
        arrow = '↗️' if signal == 'BUY' else '↘️'
        signal_ar = 'شراء' if signal == 'BUY' else 'بيع'
        
        # Confidence bar
        conf = d['confidence']
        conf_bar = '█' * (conf // 10) + '░' * (10 - conf // 10)
        
        msg = f"""{emoji} <b>إشارة {signal_ar} عالية الاحتمالية</b> {arrow}

📊 <b>الأصل:</b> {d['asset']} | {d['asset_ar']}
⏰ <b>الوقت:</b> {d['timestamp']}
🎯 <b>نوع الصفقة:</b> {signal_ar}

<b>─── تفاصيل الصفقة ───</b>

💲 <b>سعر الدخول:</b> {d['entry']}
🛡️ <b>وقف الخسارة (SL):</b> {d['stop_loss']}
🎯 <b>الهدف الأول (TP1):</b> {d['target1']}
🎯🎯 <b>الهدف الثاني (TP2):</b> {d['target2']}
🎯🎯🎯 <b>الهدف الثالث (TP3):</b> {d['target3']}

<b>─── إدارة المخاطرة ───</b>

📋 <b>الاسبريد:</b> {d['spread']}
⚠️ <b>الخطر بالبيبس:</b> {d['risk_pips']}
💰 <b>العائد بالبيبس:</b> {d['reward_pips']}
⚖️ <b>نسبة عائد/مخاطرة (RR):</b> {d['rr_ratio']}:1
⏱️ <b>المدة المتوقعة:</b> {d['duration']}

<b>─── التحليل الفني ───</b>

📈 <b>الاتجاه العام (يومي):</b> {d['trend']}
🏗️ <b>البنية السعرية:</b> {d['structure']}
💯 <b>احتمالية النجاح:</b> {conf}%
{conf_bar}

<b>✔️ أسباب الدخول:</b>"""
        
        for reason in d['reasons']:
            msg += f"\n• {reason}"
        
        msg += f"""

<b>─── تعليمات الدخول ───</b>

1️⃣ انتظر تأكيد السعر عند {d['entry']}
2️⃣ ضع SL عند {d['stop_loss']} بالضبط
3️⃣ اخرج نصف الصفقة عند TP1 = {d['target1']}
4️⃣ أحرك SL للتعادل بعد TP1
5️⃣ اجلس للهدف TP2 = {d['target2']}

⚠️ <i>هذا المحتوى تعليمي فقط وليس نصيحة مالية متخصصة.</i>
🔒 <b>C دائماً ادر مخاطرك!</b>"""
        
        return msg
    
    def is_duplicate_signal(self, asset_name, signal_type):
        """Check if we already sent this signal recently"""
        key = f"{asset_name}_{signal_type}"
        if key in self.sent_signals:
            last_sent = datetime.fromisoformat(self.sent_signals[key])
            # Don't send same signal within 4 hours
            if datetime.now() - last_sent < timedelta(hours=4):
                return True
        return False
    
    def mark_signal_sent(self, asset_name, signal_type):
        """Mark signal as sent"""
        key = f"{asset_name}_{signal_type}"
        self.sent_signals[key] = datetime.now().isoformat()
        self.save_state()
    
    def run(self):
        """Main execution"""
        print(f"[✓] Professional Forex & Gold Signal Bot Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Sort assets by priority
        sorted_assets = sorted(ASSETS.items(), key=lambda x: x[1]['priority'])
        
        signals_sent = 0
        
        for asset_name, asset_info in sorted_assets:
            print(f"[~] Analyzing {asset_name}...")
            try:
                signal_data = self.generate_signal(asset_name, asset_info)
                
                if signal_data is None:
                    print(f"[-] {asset_name}: No high-probability setup")
                    continue
                
                # Check for duplicate
                if self.is_duplicate_signal(asset_name, signal_data['signal']):
                    print(f"[-] {asset_name}: Signal already sent recently")
                    continue
                
                # Format and send
                message = self.format_signal_message(signal_data)
                if self.send_telegram(message):
                    self.mark_signal_sent(asset_name, signal_data['signal'])
                    signals_sent += 1
                    print(f"[✓] {asset_name}: Signal sent! ({signal_data['signal']} @ {signal_data['entry']}, Confidence: {signal_data['confidence']}%)")
                else:
                    print(f"[!] {asset_name}: Failed to send signal")
                
                time.sleep(2)  # Avoid Telegram rate limit
            
            except Exception as e:
                print(f"[ERROR] {asset_name}: {str(e)}")
        
        if signals_sent == 0:
            print("[-] No high-probability signals found this run")
        else:
            print(f"[✓] Total signals sent: {signals_sent}")


if __name__ == "__main__":
    try:
        bot = ForexSignalBot()
        bot.run()
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
