import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import requests  # PENTING: Untuk sambungan ke VPS
from datetime import datetime, timedelta
from utils.math_engine import calculate_gamma, calculate_vanna, calculate_charm, find_gamma_flip

# --- FUNGSI PENGAMBILAN DATA DARI VPS ---
def get_chain_from_vps(ticker, expiry):
    url = f"http://168.144.134.211:8000/get_options_chain/{ticker}/{expiry}"
    response = requests.get(url)
    data = response.json()
    # Tukar balik kepada DataFrame
    return pd.DataFrame(data['calls']), pd.DataFrame(data['puts'])
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"VPS Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Gagal berhubung dengan VPS: {e}")
        return None

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Institutional GEX, VEX & CEX Dashboard", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

# [KOD ASAL FUNGSI get_expiry_tag DIBIARKAN KEKAL]
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
    except:
        return date_str

# --- INPUT SIDEBAR ---
st.sidebar.header("Tetapan Parameter")
ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()
risk_free_rate = st.sidebar.number_input("Risk-Free Rate (r):", value=0.04, step=0.01)
spot_range_pct = st.sidebar.slider("Julat Strike dari Harga Spot (%):", min_value=5, max_value=30, value=7)

if ticker_symbol:
    with st.spinner(f"Memproses data bagi {ticker_symbol} (dari VPS)..."):
        # PANGGIL API VPS
        cached_data = get_options_data(ticker_symbol)
        
        if cached_data and 'error' not in cached_data:
            spot_price = cached_data['spot_price']
            expirations = cached_data['expirations']
            
            st.sidebar.metric(label=f"Harga Semasa ({ticker_symbol})", value=f"${spot_price:,.2f}")
            
            # --- SELEBIHNYA KOD LOGIK ANDA KEKAL SEPERTI ASAL ---
            expiry_mapping = {get_expiry_tag(d): d for d in expirations}
            display_options = list(expiry_mapping.keys())
            
            selected_display_expiries = st.sidebar.multiselect(
                "Pilih Tarikh Tamat Opsyen:", options=display_options,
                default=[display_options[0]] if display_options else None
            )
            
            if not selected_display_expiries:
                st.warning("Sila pilih tarikh.")
                st.stop()
            
            selected_expiries = [expiry_mapping[tag] for tag in selected_display_expiries]
            
            # [SAMBUNGAN LOGIK KOD ASAL ANDA DI SINI...]
            # (Pastikan anda simpan logic pengiraan Greeks anda di bawah bahagian ini)
            st.success("Data berjaya ditarik dari VPS!")
            # --- SAMBUNGAN LOGIK PENGIRAAN GREEKS ---
            ticker = yf.Ticker(ticker_symbol)
            all_calls_list = []
            all_puts_list = []
            today = datetime.now().date()
            t_total = 0
            
            for expiry in selected_expiries:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                t_expiry = max((expiry_date - today).days, 0.5) / 365.0
                t_total += t_expiry
                
                opt_chain = ticker.option_chain(expiry)
                c_df = opt_chain.calls[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
                p_df = opt_chain.puts[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
                
                # Pembersihan data asas
                for df in [c_df, p_df]:
                    df['impliedVolatility'] = df['impliedVolatility'].fillna(0.15)
                    df.loc[df['impliedVolatility'] <= 0.01, 'impliedVolatility'] = 0.15
                    df['openInterest'] = df['openInterest'].fillna(0)
                    df['volume'] = df['volume'].fillna(0)
                
                all_calls_list.append(c_df)
                all_puts_list.append(p_df)
            
            t = t_total / len(selected_expiries)
            
            # Gabung dan Kira Greeks (seperti kod asal anda)
            calls_combined = pd.concat(all_calls_list).groupby('strike').agg({'openInterest': 'sum', 'volume': 'sum', 'impliedVolatility': 'mean'}).reset_index()
            puts_combined = pd.concat(all_puts_list).groupby('strike').agg({'openInterest': 'sum', 'volume': 'sum', 'impliedVolatility': 'mean'}).reset_index()
            
            # ... (Teruskan dengan kod pengiraan GEX/VEX/CEX anda di sini) ...
        else:
            st.error("Data tidak ditemui atau VPS tidak dapat diakses.")
