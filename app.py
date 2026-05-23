import sys
import os
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime
from scipy.stats import norm

# Pastikan folder 'utils' dijumpai oleh Streamlit
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.math_engine import calculate_gamma

# 1. CACHE DATA YANG RINGAN SAHAJA (JANGAN CACHE OBJEK YFINANCE)
@st.cache_data(ttl=3600)
def get_clean_option_data(ticker_symbol, expiry):
    ticker = yf.Ticker(ticker_symbol)
    opt = ticker.option_chain(expiry)
    # Simpan hanya dataframe. Streamlit sangat suka DataFrame!
    return opt.calls, opt.puts

# 2. FUNGSI AMBIL DATA VPS
def get_options_data(ticker_symbol):
    url = f"http://168.144.134.211:8000/get_data/{ticker_symbol}"
    try:
        response = requests.get(url, timeout=10)
        return response.json() if response.status_code == 200 else {"error": f"API {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

# 3. UI DASHBOARD
st.set_page_config(page_title="Rajiv Exposure Matrix", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

ticker_symbol = st.sidebar.text_input("Simbol Saham:", value="GLD").upper().strip()

if ticker_symbol:
    data = get_options_data(ticker_symbol)
    
    if data and 'error' not in data:
        spot_price = float(data.get('spot_price', 0))
        expirations = data.get('expirations', [])
        st.sidebar.metric("Harga Semasa", f"${spot_price:,.2f}")
        
        selected_expiry = st.sidebar.selectbox("Pilih Tarikh:", options=expirations)
        
        if selected_expiry:
            # Guna fungsi cache yang betul
            calls_df, _ = get_clean_option_data(ticker_symbol, selected_expiry)
            
            t_days = (datetime.strptime(selected_expiry, "%Y-%m-%d") - datetime.now()).days
            t = max(t_days / 365.0, 0.001)
            
            df = calls_df.copy()
            df['impliedVolatility'] = df['impliedVolatility'].fillna(0.2)
            df['gamma'] = df.apply(lambda x: calculate_gamma(spot_price, x['strike'], t, 0.01, x['impliedVolatility']), axis=1)
            
            st.success(f"Data dipaparkan untuk {selected_expiry}")
            
            fig = go.Figure(go.Bar(x=df['strike'], y=df['gamma']))
            fig.update_layout(title="Gamma Exposure", xaxis_title="Strike", yaxis_title="Gamma")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.error(f"Ralat: {data.get('error', 'Gagal hubungi VPS')}")
