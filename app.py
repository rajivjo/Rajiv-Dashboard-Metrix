import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

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

# --- 2. FUNGSI EXPIRY TAG (DENGAN STRUKTUR TRY-EXCEPT YANG LENGKAP) ---
def get_expiry_tag(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year, month = dt.year, dt.month
        first_day = datetime(year, month, 1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
        third_friday = first_friday + timedelta(weeks=2)
        
        if month == 6 and third_friday.day == 19:
            monthly_expiry_day = 18
        else:
            monthly_expiry_day = third_friday.day
            
        if dt.day == monthly_expiry_day:
            return f"{date_str} (m)"
        else:
            return f"{date_str} (w)"
    except Exception:
        return date_str

# --- 3. KONFIGURASI & SIDEBAR ---
st.set_page_config(page_title="Rajiv Exposure Matrix", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()

if ticker_symbol:
    with st.spinner(f"Menyambung ke VPS untuk data {ticker_symbol}..."):
        data = get_options_data(ticker_symbol)
        
        if data and 'error' not in data:
            spot_price = data.get('spot_price', 0)
            expirations = data.get('expirations', [])
            
            st.sidebar.metric(label=f"Harga Semasa", value=f"${spot_price:,.2f}")
            
            expiry_mapping = {get_expiry_tag(d): d for d in expirations}
            selected_display = st.sidebar.multiselect("Pilih Tarikh:", options=list(expiry_mapping.keys()), default=[list(expiry_mapping.keys())[0]])
            
            if selected_display:
                st.success("Data berjaya ditarik dari VPS!")
                st.write("Sistem API anda kini berfungsi dengan stabil.")
        else:
            st.error(f"Gagal mendapatkan data: {data.get('error', 'Unknown Error')}")
