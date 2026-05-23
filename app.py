import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta
from utils.data_fetcher import get_options_data
from utils.math_engine import calculate_gamma, calculate_vanna, calculate_charm, find_gamma_flip

# 1. KONFIGURASI CACHE UNTUK STREAMLIT CLOUD
@st.cache_data(ttl=600)
def get_option_chain_cached(ticker_symbol, expiry):
    ticker = yf.Ticker(ticker_symbol)
    return ticker.option_chain(expiry)

st.set_page_config(page_title="Institutional GEX, VEX & CEX Dashboard", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

# SIDEBAR
st.sidebar.header("Tetapan Parameter")
ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()
risk_free_rate = st.sidebar.number_input("Risk-Free Rate (r):", value=0.04, step=0.01)
spot_range_pct = st.sidebar.slider("Julat Strike dari Harga Spot (%):", min_value=5, max_value=30, value=7)

def get_expiry_tag(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year, month = dt.year, dt.month
        first_day = datetime(year, month, 1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
        third_friday = first_friday + timedelta(weeks=2)
        monthly_expiry_day = 18 if (month == 6 and third_friday.day == 19) else third_friday.day
        return f"{date_str} (m)" if dt.day == monthly_expiry_day else f"{date_str} (w)"
    except: return date_str

if ticker_symbol:
    with st.spinner(f"Memproses data bagi {ticker_symbol}..."):
        try:
            # Panggil API VPS anda
            cached_data = get_options_data(ticker_symbol)
            spot_price = cached_data['spot_price']
            expirations = cached_data['expirations']
            
            st.sidebar.metric(label=f"Harga Semasa ({ticker_symbol})", value=f"${spot_price:,.2f}")
            
            expiry_mapping = {get_expiry_tag(d): d for d in expirations}
            selected_display_expiries = st.sidebar.multiselect("Pilih Tarikh:", options=list(expiry_mapping.keys()), default=[list(expiry_mapping.keys())[0]])
            
            if not selected_display_expiries: st.stop()
            
            selected_expiries = [expiry_mapping[tag] for tag in selected_display_expiries]
            all_calls_list, all_puts_list = [], []
            t_total, today = 0, datetime.now().date()
            
            # PROSES TARIK DATA DENGAN CACHE
            for expiry in selected_expiries:
                t_total += max((datetime.strptime(expiry, "%Y-%m-%d").date() - today).days, 0.5) / 365.0
                opt_chain = get_option_chain_cached(ticker_symbol, expiry)
                
                c_df = opt_chain.calls[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
                p_df = opt_chain.puts[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
                
                for df in [c_df, p_df]:
                    df['impliedVolatility'] = df['impliedVolatility'].fillna(0.15)
                    df.loc[df['impliedVolatility'] <= 0.01, 'impliedVolatility'] = 0.15
                    df['openInterest'] = df['openInterest'].fillna(0)
                    df['volume'] = df['volume'].fillna(0)
                
                all_calls_list.append(c_df)
                all_puts_list.append(p_df)
            
            t = t_total / len(selected_expiries)
            
            # AGREGASI DATA
            calls_combined = pd.concat(all_calls_list).groupby('strike').agg({'openInterest':'sum', 'volume':'sum', 'impliedVolatility':'mean'}).reset_index().rename(columns={'strike':'Strike', 'volume':'Call_Vol', 'openInterest':'Call_OI', 'impliedVolatility':'Call_IV'})
            puts_combined = pd.concat(all_puts_list).groupby('strike').agg({'openInterest':'sum', 'volume':'sum', 'impliedVolatility':'mean'}).reset_index().rename(columns={'strike':'Strike', 'volume':'Put_Vol', 'openInterest':'Put_OI', 'impliedVolatility':'Put_IV'})
            
            lower, upper = spot_price * (1 - (spot_range_pct/100)), spot_price * (1 + (spot_range_pct/100))
            strikes = sorted(list(set(calls_combined['Strike']).union(set(puts_combined['Strike']))))
            df_gex = pd.DataFrame({'Strike': strikes})
            df_gex = df_gex[(df_gex['Strike'] >= lower) & (df_gex['Strike'] <= upper)].merge(calls_combined, on='Strike', how='left').merge(puts_combined, on='Strike', how='left').fillna(0)
            
            # PENGIRAAN GREEKS
            for col, iv_col, type in [('Call_Gamma', 'Call_IV', 'call'), ('Put_Gamma', 'Put_IV', 'put')]:
                df_gex[col] = df_gex.apply(lambda r: calculate_gamma(spot_price, r['Strike'], t, risk_free_rate, r[iv_col]), axis=1)
                
            # (Tambahkan pengiraan Vanna, Charm, dan Plotly seperti kod asal anda...)
            st.success("Dashboard Berjaya Dijana!")
            st.dataframe(df_gex.head()) # Paparan contoh

        except Exception as e:
            st.error(f"Ralat Sistem: {e}")
