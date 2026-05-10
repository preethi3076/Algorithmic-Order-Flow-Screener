# Algorithmic Order-Flow & Risk Management Dashboard

A decoupled microservice architecture built in Python to analyze real-time National Stock Exchange (NSE) data. This system acts as an execution dashboard for intraday trading, focusing on Relative Volume (RVOL) anomalies, time-anchored VWAP pullbacks, and strict mathematical position sizing.

## Architecture

The system is divided into two separate applications to decouple heavy macro-scanning from the ultra-fast execution engine, preventing API rate-limiting and maintaining low latency.

1. **The Pre-Market Oracle (`macro_dashboard.py`)**
   - **Top-Down Index Scanning:** Scans 15 major indices to identify sector-wide Relative Strength (RS) anomalies before querying individual stocks.
   - **State Generation:** Generates a dynamic watchlist of the highest-probability stocks and writes them to a decoupled state file (`session_state.json`).

2. **The Execution Engine (`live_screener.py`)**
   - **Time-Anchored VWAP:** Calculates Volume Weighted Average Price strictly anchored to the 9:15 AM open, discarding stale historical data.
   - **Dynamic Position Sizing:** Automatically calculates the exact share quantity allowed based on a hardcoded maximum capital risk constraint and the real-time distance to the VWAP stop-loss.
   - **Fail-safes:** Includes automated circuit-breaker filters (rejecting stocks nearing 20% limits) and extreme open-range filters.

## System Trade-Offs (Free API vs. Paid Feeds)

This system is built using the free `yfinance` API to demonstrate institutional logic without the overhead of paid data subscriptions. 

### Pros
*   **Zero Cost:** Demonstrates professional order-flow logic without the $2,000/month cost of institutional data terminals.
*   **Highly Targeted:** Unlike commercial screeners that dump thousands of alerts, this system forces a top-down approach, presenting only 5-10 mathematically sound setups.
*   **Automated Risk Management:** Completely removes the emotional aspect of manual position sizing.

### Cons
*   **Data Latency:** Free APIs carry an inherent 1-to-5 minute delay during high-volume periods. This dashboard is intended as an **Alert System**, and actual entry prices must be verified against live broker feeds before execution.
*   **Rate Limits:** Scanning hundreds of stocks at 1-minute intervals will result in an IP ban. The dual-app architecture mitigates this by restricting the live scanner to a targeted watchlist of 10 stocks.

## Local Installation

1. Clone the repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the Macro Dashboard to generate the session state:
   ```bash
   python -m streamlit run macro_dashboard.py
   ```
4. In a separate terminal, run the Execution Engine:
   ```bash
   python -m streamlit run live_screener.py
   ```
