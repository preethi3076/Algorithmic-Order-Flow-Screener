import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time

st.set_page_config(page_title="App 2: Sniper Dashboard", layout="wide")

# Constants
CAPITAL = 6800
MAX_RISK = 80
CIRCUIT_LIMIT = 19.5

st.title("🎯 App 2: The Sniper Dashboard")

# 1. Read State File
state_file = "session_state.json"
if not os.path.exists(state_file):
    st.error("❌ `session_state.json` not found! Please run App 1 (Pre-Market Oracle) first.")
    st.stop()

with open(state_file, "r") as f:
    state = json.load(f)

bias = state.get("bias", "UNKNOWN")
hot_index = state.get("hot_index", "UNKNOWN")
watchlist = state.get("watchlist", [])

st.markdown(f"**Daily Bias:** `{bias}` | **Hot Index:** `{hot_index}` | **Active Watchlist:** `{len(watchlist)} stocks`")
if st.button("Refresh Data", type="primary"):
    pass # Streamlit reruns on button click automatically

def calculate_vwap_and_metrics(ticker):
    try:
        # Fetch 2 days of 1-minute data (to get yesterday's close and today's intraday)
        # Using 5m here for robustness if 1m is too sparse, but we aim for 1m
        df = yf.download(ticker, period="2d", interval="1m", progress=False)
        if df.empty:
            return None
            
        # Flatten MultiIndex columns if yf returns them
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Get yesterday's close
        dates = df.index.normalize().unique()
        if len(dates) < 2:
            # Need at least some previous data for prev_close
            prev_close = df['Close'].iloc[0] 
        else:
            yesterday_data = df[df.index.normalize() == dates[-2]]
            prev_close = yesterday_data['Close'].iloc[-1] if not yesterday_data.empty else df['Close'].iloc[0]
            
        # Isolate Today's Data
        today = dates[-1]
        df_today = df[df.index.normalize() == today].copy()
        
        if df_today.empty:
            return None
            
        live_price = df_today['Close'].iloc[-1]
        data_timestamp = df_today.index[-1].strftime("%H:%M")
        
        # 🔴 Fix 1 & 3: Circuit Breaker Filter
        if prev_close > 0:
            circuit_pct = ((live_price - prev_close) / prev_close) * 100
            if abs(circuit_pct) >= CIRCUIT_LIMIT:
                return {"Ticker": ticker, "Signal": "❌ CIRCUIT", "Reason": f"Near {round(circuit_pct,1)}% circuit limit", "Timestamp": data_timestamp}
                
        # 🔴 Fix 2: VWAP Anchor Reset at 9:15 AM
        # We ensure we only calculate VWAP for today's slice
        df_today['Typical_Price'] = (df_today['High'] + df_today['Low'] + df_today['Close']) / 3
        df_today['Volume_Price'] = df_today['Typical_Price'] * df_today['Volume']
        df_today['Cum_Volume'] = df_today['Volume'].cumsum()
        df_today['Cum_Volume_Price'] = df_today['Volume_Price'].cumsum()
        df_today['VWAP'] = df_today['Cum_Volume_Price'] / df_today['Cum_Volume']
        
        current_vwap = df_today['VWAP'].iloc[-1]
        
        # 🟡 Priority 3: First-Candle Range Filter
        first_candle = df_today.iloc[0]
        first_range = first_candle['High'] - first_candle['Low']
        
        # Approximate ATR-14 (Using a simple 14-period rolling TR on 1m data for proxy, real ATR needs daily data)
        # We will just calculate Intraday ATR based on last 14 1m candles
        df_today['TR'] = df_today['High'] - df_today['Low']
        atr_14 = df_today['TR'].rolling(14).mean().iloc[-1]
        
        if first_range > (2 * atr_14) and pd.notna(atr_14):
            return {"Ticker": ticker, "Signal": "❌ EXTREME OPEN", "Reason": "9:15 candle too large", "Timestamp": data_timestamp}
            
        # Volume Velocity (Current vs Average of previous 10 candles)
        avg_vol = df_today['Volume'].rolling(10).mean().shift(1).iloc[-1]
        current_vol = df_today['Volume'].iloc[-1]
        vol_velocity = (current_vol / avg_vol) if avg_vol > 0 else 0
        
        # Signal Generation Logic (Aggressive Scalp: Price crosses VWAP with high volume)
        signal = "WAIT"
        reason = ""
        entry = 0
        sl = current_vwap
        qty = 0
        target = 0
        
        distance_to_vwap = (live_price - current_vwap) / current_vwap * 100
        
        if bias == "BULLISH":
            if live_price > current_vwap and abs(distance_to_vwap) < 0.5 and vol_velocity > 2.0:
                signal = "🔥 BUY"
                entry = live_price
                sl = current_vwap - (atr_14 * 0.5) # Stop just below VWAP
                sl_dist = entry - sl
                
                if sl_dist > 0:
                    qty = int(MAX_RISK / sl_dist)
                    target = entry + (sl_dist * 2) # 1:2 R:R
                else:
                    signal = "❌ PASS"
                    reason = "Invalid SL distance"
                    
        return {
            "Ticker": ticker,
            "Price": round(live_price, 2),
            "VWAP": round(current_vwap, 2),
            "Signal": signal,
            "Entry": round(entry, 2) if entry > 0 else "-",
            "Target": round(target, 2) if target > 0 else "-",
            "Stop Loss": round(sl, 2) if entry > 0 else "-",
            "Qty": qty if qty > 0 else "-",
            "Vol Vel": f"{round(vol_velocity, 1)}x",
            "Reason": reason,
            "Timestamp": data_timestamp
        }
            
    except Exception as e:
        return {"Ticker": ticker, "Signal": "❌ ERROR", "Reason": str(e)}

with st.spinner("Scanning for Sniper Entries..."):
    results = []
    # Add a tiny delay to respect yfinance rate limits
    for ticker in watchlist:
        res = calculate_vwap_and_metrics(ticker)
        if res:
            results.append(res)
        time.sleep(0.5) 
        
    if results:
        df_results = pd.DataFrame(results)
        
        def highlight_signal(val):
            if val == '🔥 BUY': return 'background-color: #2e7d32; color: white'
            elif '❌' in str(val): return 'background-color: #c62828; color: white'
            return ''
            
        st.dataframe(df_results.style.map(highlight_signal, subset=['Signal']))
        
        # Note on Data Lag
        st.caption("⚠️ **Data Lag Warning:** Check the `Timestamp` column. Free yfinance data is typically delayed by 1-5 minutes. **DO NOT blindly place limit orders if the current price on Groww has already passed the Entry Price.**")
        
        st.subheader("💡 Position Sizing Math")
        st.markdown(f"`Qty = Maximum Risk (₹{MAX_RISK}) / (Entry Price - Stop Loss Price)`")
        st.markdown(f"Always verify this math before executing. Max capital allowed is ₹{CAPITAL}.")
