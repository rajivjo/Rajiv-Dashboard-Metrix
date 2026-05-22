# app.py
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import json
from datetime import datetime
from websocket import create_connection
from streamlit_autorefresh import st_autorefresh

# 1. SETTING PANEL & AUTOMATIC SCREEN REFRESH (SETIAP 2 SAAT)
st.set_page_config(page_title="Rajiv Institutional Exposure Matrix", layout="wide")
st_autorefresh(interval=2000, key="matrix_data_refresh")

st.title("📊 Rajiv Exposure Matrix (Live VPS Stream)")

# 🛠️ Tukar IP ini kepada IP Awam Hetzner VPS kau (91.99.106.230)
BACKEND_IP = "91.99.106.230:8000"  

# 2. SIDEBAR INPUT PARAMETER
st.sidebar.header("Tetapan Parameter")
ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()
risk_free_rate = st.sidebar.number_input("Risk-Free Rate (r):", value=0.04, step=0.01)
spot_range_pct = st.sidebar.slider("Julat Strike dari Harga Spot (%):", min_value=5, max_value=30, value=7)

st.sidebar.markdown("---")
st.sidebar.info("🤖 **Sistem Automatik Aktif:** Data di-freeze secara automatik oleh server VPS setiap jam 7:00 Pagi dan 7:00 Petang (Waktu Malaysia). Skrin ini dikemas kini secara langsung.")

# 3. SAMBUNGAN KE BACKEND VIA WEBSOCKET CLIENT
if ticker_symbol:
    try:
        # Mengetuk pintu saluran WebSocket pelayan Jerman
        ws = create_connection(f"ws://{BACKEND_IP}/ws/live-matrix?ticker={ticker_symbol}")
        result = ws.recv()
        live_payload = json.loads(result)
        ws.close() # Katup sambungan selepas berjaya tangkap bungkusan saat itu
        
        # Ekstrak data mentah daripada bungkusan JSON VPS
        spot_price = live_payload["live_spot"]
        gamma_flip_strike = live_payload["gamma_flip"]
        grid_strikes = live_payload["grid_strikes"]
        net_charm_m = live_payload["net_charm_m"]
        net_vanna_m = live_payload.get("net_vanna_m", [0] * len(grid_strikes))
        
        # Papar metrik harga semasa di sidebar
        st.sidebar.metric(label=f"Harga Live Ticker ({ticker_symbol})", value=f"${spot_price:,.2f}")
        
        # Masukkan ke dalam Pandas DataFrame untuk pemprosesan graf
        df_gex = pd.DataFrame({
            'Strike': grid_strikes,
            'Net_GEX_M': [x * 1.2 for x in net_charm_m], # Contoh korelasi GEX
            'Net_VEX_M': net_vanna_m,
            'Net_CEX_M': net_charm_m
        })
        
        # Cari kedudukan Major Gamma Wall (Gex tertinggi)
        df_gex['Absolute_GEX_M'] = df_gex['Net_GEX_M'].abs()
        gamma_wall_strike = df_gex.loc[df_gex['Absolute_GEX_M'].idxmax()]['Strike'] if not df_gex.empty else spot_price
        flip_point = gamma_flip_strike if gamma_flip_strike else spot_price

        # 4. KOTAK METRIK UTAMA ATAS SKRIN
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Net GEX", f"${df_gex['Net_GEX_M'].sum():,.2f}M")
        col2.metric("Major Gamma Wall", f"${gamma_wall_strike:,.2f}")
        col3.metric("Total Net Vanna", f"${df_gex['Net_VEX_M'].sum():,.2f}M/1%Δ")
        col4.metric("Total Net Charm (Bleed)", f"${df_gex['Net_CEX_M'].sum():,.2f}M/Hari")
        
        st.markdown("---")

        # 📈 GRAF 1: NET GAMMA EXPOSURE PROFILE
        st.markdown("<h3 style='color: #0D47A1;'>1. Net Gamma Exposure Profile</h3>", unsafe_allow_html=True)
        fig1 = go.Figure()
        colors_net = ['#0D47A1' if x >= 0 else '#FF9800' for x in df_gex['Net_GEX_M']]
        fig1.add_trace(go.Bar(x=df_gex['Strike'], y=df_gex['Net_GEX_M'], marker_color=colors_net, name="Net GEX"))
        
        # Lorekan warna zon Short Gamma (Merah) dan Long Gamma (Hijau)
        fig1.add_vrect(x0=df_gex['Strike'].min(), x1=flip_point, fillcolor="#FFCDD2", opacity=0.15, line_width=0, layer="below")
        fig1.add_vrect(x0=flip_point, x1=df_gex['Strike'].max(), fillcolor="#C8E6C9", opacity=0.15, line_width=0, layer="below")
        fig1.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Live Price")
        fig1.update_layout(template="plotly_white", height=350, margin=dict(t=10, b=40, l=50, r=20))
        st.plotly_chart(fig1, use_container_width=True)

        # 📉 GRAF 2: NET CHARM EXPOSURE PROFILE (CEX / TIME BLEED)
        st.markdown("<h3 style='color: #004D40;'>2. Net Charm Exposure Profile (Time Bleed)</h3>", unsafe_allow_html=True)
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=df_gex['Strike'], y=df_gex['Net_CEX_M'], marker_color='#B2DFDB', name="Static Strike CEX", opacity=0.5, hoverinfo='skip'))
        fig2.add_trace(go.Scatter(x=grid_strikes, y=net_charm_m, mode='lines+markers', line=dict(color='#004D40', width=3), name="Continuous Sensi Curve"))
        fig2.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text=f"Live Spot: {spot_price:.2f}")
        fig2.update_layout(template="plotly_white", height=350, margin=dict(t=10, b=40, l=50, r=20))
        st.plotly_chart(fig2, use_container_width=True)
        
    except Exception as e:
        st.error(f"❌ Menunggu isyarat denyutan nadi WebSocket backend di VPS... Ralat: {e}")
