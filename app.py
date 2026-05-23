import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime, timedelta
from scipy.stats import norm

# 1. PENGIRAAN MATEMATIK (DIGABUNGKAN UNTUK ELAK ERROR IMPORT)
def calculate_gamma(S, K, T, r, sigma):
    if T <= 0: return 0
    d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))

# 2. CACHING UNTUK ELAK YAHOO FINANCE BLOCK
@st.cache_data(ttl=3600)
def get_cached_option_chain(ticker_symbol, expiry):
    ticker = yf.Ticker(ticker_symbol)
    return ticker.option_chain(expiry)

def get_options_data(ticker_symbol):
    url = f"http://168.144.134.211:8000/get_data/{ticker_symbol}"
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else {"error": "API Error"}
    except Exception:
        return {"error": "Connection Failed"}

# 3. UI DASHBOARD
st.set_page_config(page_title="Rajiv Exposure Matrix", layout="wide")
st.title("📊 Rajiv Exposure Matrix (Live Edition)")

ticker_symbol = st.sidebar.text_input("Simbol Saham:", value="GLD").upper().strip()

if ticker_symbol:
    with st.spinner("Menarik data..."):
        data = get_options_data(ticker_symbol)
        
        if data and 'error' not in data:
            spot_price = float(data.get('spot_price', 0))
            expirations = data.get('expirations', [])
            
            selected_expiry = st.sidebar.selectbox("Pilih Tarikh Tamat:", options=expirations)
            
            if selected_expiry:
                # GUNA CACHE UNTUK ELAK RATE LIMIT
                opt = get_cached_option_chain(ticker_symbol, selected_expiry)
                
                t_days = (datetime.strptime(selected_expiry, "%Y-%m-%d") - datetime.now()).days
                t = max(t_days / 365.0, 0.001)
                
                df = opt.calls.copy()
                df['impliedVolatility'] = df['impliedVolatility'].fillna(0.2)
                df['gamma'] = df.apply(lambda x: calculate_gamma(spot_price, x['strike'], t, 0.01, x['impliedVolatility']), axis=1)
                
                st.success(f"Data berjaya dipaparkan untuk {selected_expiry}")
                
                # GRAF
                fig = go.Figure(go.Bar(x=df['strike'], y=df['gamma'], marker_color='#0D47A1'))
                fig.update_layout(title=f"Gamma Exposure: {ticker_symbol}", xaxis_title="Strike", yaxis_title="Gamma")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error("Gagal sambung ke Server. Pastikan server anda aktif.")
