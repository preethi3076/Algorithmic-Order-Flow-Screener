import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
from datetime import datetime

st.set_page_config(page_title="App 1: Pre-Market Oracle", layout="wide")

# Define the major indices and their top liquid stocks (for Yahoo Finance)
SECTORS = {
    "NIFTY_METAL": {
        "index_symbol": "^CNXMETAL",
        "stocks": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "VEDL.NS", "NMDC.NS"]
    },
    "NIFTY_IT": {
        "index_symbol": "^CNXIT",
        "stocks": ["INFY.NS", "TCS.NS", "HCLTECH.NS", "TECHM.NS", "WIPRO.NS"]
    },
    "NIFTY_BANK": {
        "index_symbol": "^NSEBANK",
        "stocks": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"]
    },
    "NIFTY_AUTO": {
        "index_symbol": "^CNXAUTO",
        "stocks": ["TATAMOTORS.NS", "M&M.NS", "MARUTI.NS", "EICHERMOT.NS", "BAJAJ-AUTO.NS"]
    },
    "NIFTY_PHARMA": {
        "index_symbol": "^CNXPHARMA",
        "stocks": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"]
    }
}

st.title("🔮 App 1: The Pre-Market Oracle")
st.markdown("Run this at 9:00 AM to determine the Daily Bias and find the Hottest Sector.")

def get_index_performance():
    data = []
    # Fetch 20 days of data to calculate ATR-20 for Relative Strength Score
    tickers = [s["index_symbol"] for s in SECTORS.values()]
    tickers.append("^NSEI") # Nifty 50 for baseline
    
    st.write(f"Fetching data for {len(tickers)} indices...")
    hist_data = yf.download(tickers, period="1mo", interval="1d", group_by="ticker", progress=False)
    
    for sector_name, info in SECTORS.items():
        symbol = info["index_symbol"]
        try:
            # Handle single vs multi ticker download structure in yfinance
            if len(tickers) == 1:
                df = hist_data
            else:
                df = hist_data[symbol]
                
            if df.empty:
                continue
                
            df = df.dropna()
            # Calculate ATR (Approximate 20-day Average True Range)
            df['High-Low'] = df['High'] - df['Low']
            df['High-PrevClose'] = abs(df['High'] - df['Close'].shift(1))
            df['Low-PrevClose'] = abs(df['Low'] - df['Close'].shift(1))
            df['TrueRange'] = df[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
            atr_20 = df['TrueRange'].rolling(20).mean().iloc[-1]
            
            # Today's performance
            prev_close = df['Close'].iloc[-2]
            current_price = df['Close'].iloc[-1]
            pct_change = ((current_price - prev_close) / prev_close) * 100
            
            # Relative Strength Score (Normalized by ATR)
            rs_score = pct_change / (atr_20 / prev_close * 100) if atr_20 > 0 else 0
            
            data.append({
                "Sector": sector_name,
                "Symbol": symbol,
                "Today %": round(pct_change, 2),
                "ATR (20)": round(atr_20, 2),
                "RS Score": round(rs_score, 2),
                "Stocks": info["stocks"]
            })
        except Exception as e:
            st.error(f"Error processing {symbol}: {e}")
            
    return pd.DataFrame(data)

if st.button("Scan Indices & Generate Heatmap"):
    with st.spinner("Scanning Top-Down..."):
        df = get_index_performance()
        if not df.empty:
            # Sort by RS Score (Highest first)
            df = df.sort_values(by="RS Score", ascending=False).reset_index(drop=True)
            
            st.subheader("🔥 Sector Heatmap (Ranked by Relative Strength)")
            st.dataframe(df.style.background_gradient(subset=['RS Score', 'Today %'], cmap='RdYlGn'))
            
            # Select the hottest index
            hot_index_row = df.iloc[0]
            hot_sector = hot_index_row["Sector"]
            watchlist = hot_index_row["Stocks"]
            bias = "BULLISH" if hot_index_row["RS Score"] > 0 else "BEARISH"
            
            st.success(f"**Winning Sector Today:** {hot_sector} ({bias})")
            st.info(f"**Watchlist generated for Live Screener:** {', '.join(watchlist)}")
            
            # Write State File
            state_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "hot_index": hot_sector,
                "bias": bias,
                "watchlist": watchlist
            }
            with open("session_state.json", "w") as f:
                json.dump(state_data, f, indent=4)
                
            st.markdown("✅ `session_state.json` saved successfully! You can now close this app and open **App 2: Live Screener**.")
        else:
            st.warning("Failed to fetch data. Check your internet connection or market hours.")
