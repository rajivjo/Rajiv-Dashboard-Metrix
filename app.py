import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import yfinance as yf
from datetime import datetime, timedelta
# Import fungsi pengiraan dari folder utils
from utils.math_engine import calculate_gamma 

# --- 1. FUNGSI PENGAMBILAN DATA ---
def get_options_data(ticker_symbol):
    url = f"http://168.144.134.211:8000/get_data/{ticker_symbol}"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Status API: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_expiry_tag(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year, month = dt.year, dt.month
        first_day = datetime(year, month, 1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
        third_friday = first_friday + timedelta(weeks=2)
        monthly_expiry_day = 18 if (month == 6 and third_friday.day == 19) else third_friday.day
        return f"{date_str} (m)" if dt.day == monthly_expiry_day else f"{date_str} (w)"
    except Exception:
        return date_str

# --- 2. KONFIGURASI & SIDEBAR ---
st.set_page_config(page_title="Rajiv Exposure Matrix", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()

if ticker_symbol:
    with st.spinner(f"Menyambung ke VPS..."):
        data = get_options_data(ticker_symbol)
        
        if data and 'error' not in data:
            spot_price = float(data.get('spot_price', 0))
            expirations = data.get('expirations', [])
            st.sidebar.metric(label="Harga Semasa", value=f"${spot_price:,.2f}")
            
            expiry_mapping = {get_expiry_tag(d): d for d in expirations}
            selected_display = st.sidebar.multiselect("Pilih Tarikh:", options=list(expiry_mapping.keys()))
            
            if selected_display:
                st.success("Data berjaya ditarik dari VPS!")
                
                # --- 3. PENGIRAAN & GRAF ---
                ticker = yf.Ticker(ticker_symbol)
                r = 0.01 # Kadar faedah 1%
                
                for display_name in selected_display:
                    expiry = expiry_mapping[display_name]
                    opt = ticker.option_chain(expiry)
                    
                    # Kira t (time to maturity dalam tahun)
                    t_days = (datetime.strptime(expiry, "%Y-%m-%d") - datetime.now()).days
                    t = max(t_days / 365.0, 0.001) # Elak pembahagian dengan sifar
                    
                    # Bersihkan data: Isi nilai kosong IV dengan 0.2 (20%)
                    df = opt.calls.copy()
                    df['impliedVolatility'] = df['impliedVolatility'].fillna(0.2)
                    
                    # Kira Gamma bagi setiap baris (strike)
                    df['gamma'] = df.apply(lambda x: calculate_gamma(spot_price, x['strike'], t, r, x['impliedVolatility']), axis=1)
                    
                    # Papar Graf
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=df['strike'], y=df['gamma'], name="Gamma Exposure"))
                    fig.update_layout(title=f"Gamma Exposure: {ticker_symbol} - {expiry}")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.error(f"Gagal mendapatkan data: {data.get('error', 'Unknown Error')}")
