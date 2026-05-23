import sys
import os
# Paksa Streamlit untuk melihat folder semasa supaya folder 'utils' dijumpai
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime, timedelta
# Import fungsi dari folder utils anda
from utils.math_engine import calculate_gamma

# 1. CACHING DATAFRAME SAHAJA (ELAK ERROR UNSERIALIZABLE)
@st.cache_data(ttl=3600)
def get_clean_option_chain(ticker_symbol, expiry):
    ticker = yf.Ticker(ticker_symbol)
    opt = ticker.option_chain(expiry)
    # Simpan hanya dataframe (Format yang Streamlit boleh simpan dalam cache)
    return opt.calls, opt.puts

# 2. FUNGSI AMBIL DATA VPS
def get_options_data(ticker_symbol):
    url = f"http://168.144.134.211:8000/get_data/{ticker_symbol}"
    try:
        response = requests.get(url, timeout=15)
        return response.json() if response.status_code == 200 else {"error": "API Error"}
    except Exception as e:
        return {"error": str(e)}

# 3. UI DASHBOARD
st.set_page_config(page_title="Rajiv Exposure Matrix", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()

if ticker_symbol:
    with st.spinner("Menyambung ke VPS & Mengambil Data..."):
        data = get_options_data(ticker_symbol)
        
        if data and 'error' not in data:
            spot_price = float(data.get('spot_price', 0))
            expirations = data.get('expirations', [])
            st.sidebar.metric(label="Harga Semasa", value=f"${spot_price:,.2f}")
            
            selected_expiry = st.sidebar.selectbox("Pilih Tarikh Tamat:", options=expirations)
            
            if selected_expiry:
                # Ambil data dari cache
                calls_df, _ = get_clean_option_chain(ticker_symbol, selected_expiry)
                
                t_days = (datetime.strptime(selected_expiry, "%Y-%m-%d") - datetime.now()).days
                t = max(t_days / 365.0, 0.001)
                
                # Pembersihan Data
                df = calls_df.copy()
                df['impliedVolatility'] = df['impliedVolatility'].fillna(0.2)
                
                # Pengiraan Gamma menggunakan fungsi dari folder 'utils'
                df['gamma'] = df.apply(lambda x: calculate_gamma(spot_price, x['strike'], t, 0.01, x['impliedVolatility']), axis=1)
                
                st.success("Data berjaya dijana!")
                
                # Graf
                fig = go.Figure(go.Bar(x=df['strike'], y=df['gamma'], marker_color='#0D47A1'))
                fig.update_layout(title=f"Gamma Exposure: {ticker_symbol} - {selected_expiry}", xaxis_title="Strike", yaxis_title="Gamma")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f"Gagal dapatkan data: {data.get('error')}")
