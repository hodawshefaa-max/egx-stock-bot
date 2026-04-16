#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gold Scalping Bot - Professional Scalping Strategy for XAU/USD
Target: $5 per trade with high-frequency signals
Features: Support/Resistance bounces, momentum scalps, trade tracking
"""

import os
import requests
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import time
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import EMAIndicator, MACD
from ta.volatility import BollingerBands, AverageTrueRange

# Telegram Configuration
TELEGRAM_TOKEN = os.getenv('GOLD_TELEGRAM_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Trading Configuration
TARGET_PROFIT = 5  # $5 per trade
SCALP_TIMEFRAME = '5m'  # 5-minute candles for scalping
LOOKBACK_PERIODS = 100
STATE_FILE = 'gold_scalping_state.json'

class GoldScalpingBot:
    def __init__(self):
        self.active_trades = {}
        self.load_state()
        
    def load_state(self):
        """Load previous trade states"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                    self.active_trades = data.get('active_trades', {})
        except:
            self.active_trades = {}
    
    def save_state(self):
        """Save trade states"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump({'active_trades': self.active_trades}, f)
        except:
            pass
    
    def send_telegram(self, message):
        """Send message to Telegram"""
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage'
            data = {'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
            requests.post(url, data=data, timeout=10)
            return True
        except:
            return False
    
    def get_gold_data(self):
        """Fetch real-time gold data"""
        try:
            ticker = yf.Ticker('GC=F')  # Gold Futures
            df = ticker.history(period='1d', interval=SCAMP_TIMEFRAME)
            
            if df.empty or len(df) < 20:
                # Fallback to XAU/USD
                ticker = yf.Ticker('XAUUSD=X')
                df = ticker.history(period='1d', interval=SCAMP_TIMEFRAME)
            
            return df if not df.empty else None
        except:
            return None
    
    def calculate_indicators(self, df):
        """Calculate all technical indicators"""
        # Price levels
        df['High_20'] = df['High'].rolling(20).max()
        df['Low_20'] = df['Low'].rolling(20).min()
        df['Pivot'] = (df['High'] + df['Low'] + df['Close']) / 3
        
        # Momentum
        df['RSI'] = RSIIndicator(df['Close'], window=14).rsi()
        df['RSI_fast'] = RSIIndicator(df['Close'], window=7).rsi()
        stoch = StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
        
        # Trend
        df['EMA_8'] = EMAIndicator(df['Close'], window=8).ema_indicator()
        df['EMA_21'] = EMAIndicator(df['Close'], window=21).ema_indicator()
        df['EMA_50'] = EMAIndicator(df['Close'], window=50).ema_indicator()
        
        macd = MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_hist'] = macd.macd_diff()
        
        # Volatility
        bb = BollingerBands(df['Close'], window=20, window_dev=2)
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_middle'] = bb.bollinger_mavg()
        df['BB_lower'] = bb.bollinger_lband()
        df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle'] * 100
        
        atr = AverageTrueRange(df['High'], df['Low'], df['Close'], window=14)
        df['ATR'] = atr.average_true_range()
        
        # Volume
        df['Volume_MA'] = df['Volume'].rolling(20).mean()
        
        return df
    
    def detect_support_resistance(self, df, lookback=20):
        """Detect key support and resistance levels"""
        highs = df['High'].tail(lookback)
        lows = df['Low'].tail(lookback)
        
        resistance = highs.nlargest(3).mean()
        support = lows.nsmallest(3).mean()
        
        return support, resistance
    
    def generate_scalping_signal(self, df):
        """Generate high-probability scalping signals"""
        if len(df) < 50:
            return None
        
        df = self.calculate_indicators(df)
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        support, resistance = self.detect_support_resistance(df)
        current_price = latest['Close']
        
        signal = None
        confidence = 0
        entry_reason = []
        
        # === STRATEGY 1: Support/Resistance Bounce (High Confidence) ===
        distance_to_support = ((current_price - support) / support) * 100
        distance_to_resistance = ((resistance - current_price) / current_price) * 100
        
        # BUY at Support Bounce
        if distance_to_support < 0.3 and distance_to_support > -0.2:
            if latest['RSI'] < 35 and latest['Stoch_K'] < 25:
                if latest['Close'] > latest['BB_lower']:
                    signal = 'BUY'
                    confidence = 85
                    entry_reason.append('🎯 ارتداد من الدعم القوي')
                    entry_reason.append(f'السعر قرب الدعم {support:.2f}')
        
        # SELL at Resistance Bounce
        elif distance_to_resistance < 0.3 and distance_to_resistance > -0.2:
            if latest['RSI'] > 65 and latest['Stoch_K'] > 75:
                if latest['Close'] < latest['BB_upper']:
                    signal = 'SELL'
                    confidence = 85
                    entry_reason.append('🎯 ارتداد من المقاومة القوية')
                    entry_reason.append(f'السعر قرب المقاومة {resistance:.2f}')
        
        # === STRATEGY 2: Bollinger Bounce (Medium-High) ===
        if signal is None:
            bb_position = (current_price - latest['BB_lower']) / (latest['BB_upper'] - latest['BB_lower'])
            
            # BUY at BB Lower
            if bb_position < 0.15:
                if latest['RSI'] < 40 and latest['RSI_fast'] < latest['RSI']:
                    if latest['Close'] > prev['Close']:  # Bullish candle
                        signal = 'BUY'
                        confidence = 75
                        entry_reason.append('📊 ارتداد من حد البولينجر السفلي')
            
            # SELL at BB Upper
            elif bb_position > 0.85:
                if latest['RSI'] > 60 and latest['RSI_fast'] > latest['RSI']:
                    if latest['Close'] < prev['Close']:  # Bearish candle
                        signal = 'SELL'
                        confidence = 75
                        entry_reason.append('📊 ارتداد من حد البولينجر العلوي')
        
        # === STRATEGY 3: Momentum Scalp (Quick reversal) ===
        if signal is None:
            # RSI Divergence + MACD crossover
            if latest['RSI'] < 30 and latest['MACD'] > latest['MACD_signal']:
                if prev['MACD'] <= prev['MACD_signal']:  # Fresh crossover
                    if latest['EMA_8'] > latest['EMA_21']:  # Trending up
                        signal = 'BUY'
                        confidence = 70
                        entry_reason.append('⚡ فرصة زخم صعودي سريع')
            
            elif latest['RSI'] > 70 and latest['MACD'] < latest['MACD_signal']:
                if prev['MACD'] >= prev['MACD_signal']:  # Fresh crossover
                    if latest['EMA_8'] < latest['EMA_21']:  # Trending down
                        signal = 'SELL'
                        confidence = 70
                        entry_reason.append('⚡ فرصة زخم هبوطي سريع')
        
        if signal:
            # Calculate targets
            atr = latest['ATR']
            if signal == 'BUY':
                entry = current_price
                target = entry + TARGET_PROFIT
                stop_loss = entry - min(atr * 1.5, TARGET_PROFIT * 0.8)  # Tight stop
            else:
                entry = current_price
                target = entry - TARGET_PROFIT
                stop_loss = entry + min(atr * 1.5, TARGET_PROFIT * 0.8)
            
            return {
                'signal': signal,
                'entry': entry,
                'target': target,
                'stop_loss': stop_loss,
                'confidence': confidence,
                'reasons': entry_reason,
                'support': support,
                'resistance': resistance,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    def format_signal_message(self, signal_data):
        """Format signal for Telegram"""
        signal = signal_data['signal']
        emoji = '🟢' if signal == 'BUY' else '🔴'
        arrow = '↑' if signal == 'BUY' else '↓'
        
        msg = f"{emoji} <b>إشارة سكالبنج ذهب - {signal}</b> {arrow}\n\n"
        msg += f"📍 <b>السعر الحالي:</b> ${signal_data['entry']:.2f}\n"
        msg += f"🎯 <b>الهدف:</b> ${signal_data['target']:.2f} (+${TARGET_PROFIT})\n"
        msg += f"⛔ <b>وقف الخسارة:</b> ${signal_data['stop_loss']:.2f}\n\n"
        msg += f"📊 <b>الثقة:</b> {signal_data['confidence']}%\n\n"
        
        msg += "<b>🔍 سبب الصفقة:</b>\n"
        for reason in signal_data['reasons']:
            msg += f"• {reason}\n"
        
        msg += f"\n📈 دعم: ${signal_data['support']:.2f}\n"
        msg += f"📉 مقاومة: ${signal_data['resistance']:.2f}\n\n"
        msg += f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        
        return msg
    
    def track_trade_result(self, trade_id, signal_data):
        """Track and report trade outcomes"""
        if trade_id not in self.active_trades:
            self.active_trades[trade_id] = {
                'signal': signal_data['signal'],
                'entry': signal_data['entry'],
                'target': signal_data['target'],
                'stop_loss': signal_data['stop_loss'],
                'start_time': datetime.now().isoformat(),
                'status': 'ACTIVE'
            }
            self.save_state()
    
    def check_trade_outcomes(self):
        """Check if active trades hit target or stop"""
        df = self.get_gold_data()
        if df is None or df.empty:
            return
        
        current_price = df['Close'].iloc[-1]
        completed = []
        
        for trade_id, trade in self.active_trades.items():
            if trade['status'] != 'ACTIVE':
                continue
            
            outcome = None
            
            if trade['signal'] == 'BUY':
                if current_price >= trade['target']:
                    outcome = 'WIN'
                    profit = TARGET_PROFIT
                elif current_price <= trade['stop_loss']:
                    outcome = 'LOSS'
                    profit = -(trade['entry'] - trade['stop_loss'])
            
            else:  # SELL
                if current_price <= trade['target']:
                    outcome = 'WIN'
                    profit = TARGET_PROFIT
                elif current_price >= trade['stop_loss']:
                    outcome = 'LOSS'
                    profit = -(trade['stop_loss'] - trade['entry'])
            
            if outcome:
                emoji = '✅' if outcome == 'WIN' else '❌'
                msg = f"{emoji} <b>تقرير الصفقة</b>\n\n"
                msg += f"📊 <b>النتيجة:</b> {outcome}\n"
                msg += f"💵 <b>الربح/الخسارة:</b> ${profit:.2f}\n"
                msg += f"📍 <b>دخول:</b> ${trade['entry']:.2f}\n"
                msg += f"🎯 <b>خروج:</b> ${current_price:.2f}\n"
                msg += f"⏱️ <b>المدة:</b> {trade_id}\n"
                
                self.send_telegram(msg)
                trade['status'] = outcome
                trade['close_price'] = current_price
                trade['profit'] = profit
                completed.append(trade_id)
        
        if completed:
            self.save_state()
    
    def run(self):
        """Main bot execution"""
        print(f"[✓] Gold Scalping Bot Started - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Check existing trades first
        self.check_trade_outcomes()
        
        # Get fresh data
        df = self.get_gold_data()
        if df is None or df.empty:
            print("[!] No data available")
            return
        
        # Generate signal
        signal_data = self.generate_scalping_signal(df)
        
        if signal_data:
            # Send signal
            message = self.format_signal_message(signal_data)
            if self.send_telegram(message):
                print(f"[✓] Signal sent: {signal_data['signal']} @ ${signal_data['entry']:.2f}")
                
                # Track this trade
                trade_id = f"{signal_data['signal']}_{int(time.time())}"
                self.track_trade_result(trade_id, signal_data)
            else:
                print("[!] Failed to send signal")
        else:
            print("[-] No signal generated")

if __name__ == "__main__":
    try:
        bot = GoldScalpingBot()
        bot.run()
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
