import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from utils.data_fetcher import get_options_data
from utils.math_engine import calculate_gamma, calculate_vanna, find_gamma_flip

# CONFIG HALAMAN DASHBOARD
st.set_page_config(page_title="Professional GEX & VEX Dashboard", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

# INPUT SIDEBAR
st.sidebar.header("Tetapan Parameter")
ticker_symbol = st.sidebar.text_input("Simbol Saham / ETF (US):", value="GLD").upper().strip()
risk_free_rate = st.sidebar.number_input("Risk-Free Rate (r):", value=0.04, step=0.01)
spot_range_pct = st.sidebar.slider("Julat Strike dari Harga Spot (%):", min_value=5, max_value=30, value=7)

if ticker_symbol:
    with st.spinner(f"Memproses data bagi {ticker_symbol}..."):
        try:
            cached_data = get_options_data(ticker_symbol)
            spot_price = cached_data['spot_price']
            expirations = cached_data['expirations']
            
            st.sidebar.metric(label=f"Harga Semasa ({ticker_symbol})", value=f"${spot_price:,.2f}")
            
            if not expirations:
                st.error("Tiada data opsyen ditemui.")
                st.stop()
                
            selected_expiry = st.sidebar.selectbox("Pilih Tarikh Tamat Opsyen:", expirations)
            
            today = datetime.now().date()
            expiry_date = datetime.strptime(selected_expiry, "%Y-%m-%d").date()
            t = max((expiry_date - today).days, 0.5) / 365.0
            
            ticker = yf.Ticker(ticker_symbol)
            opt_chain = ticker.option_chain(selected_expiry)
            
            calls = opt_chain.calls[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
            puts = opt_chain.puts[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
            
            calls = calls.rename(columns={'strike': 'Strike', 'volume': 'Call_Vol'}).dropna()
            puts = puts.rename(columns={'strike': 'Strike', 'volume': 'Put_Vol'}).dropna()
            
            calls = calls[calls['impliedVolatility'] > 0.01]
            puts = puts[puts['impliedVolatility'] > 0.01]
            
            lower_bound = spot_price * (1 - (spot_range_pct / 100))
            upper_bound = spot_price * (1 + (spot_range_pct / 100))
            
            strikes = sorted(list(set(calls['Strike']).union(set(puts['Strike']))))
            df_gex = pd.DataFrame({'Strike': strikes})
            df_gex = df_gex[(df_gex['Strike'] >= lower_bound) & (df_gex['Strike'] <= upper_bound)].copy()
            
            df_gex = df_gex.merge(calls.rename(columns={'openInterest': 'Call_OI', 'impliedVolatility': 'Call_IV'}), on='Strike', how='left')
            df_gex = df_gex.merge(puts.rename(columns={'openInterest': 'Put_OI', 'impliedVolatility': 'Put_IV'}), on='Strike', how='left')
            df_gex = df_gex.fillna(0)
            
            df_gex = df_gex[(df_gex['Call_OI'] > 0) | (df_gex['Put_OI'] > 0)].copy()
            
            if df_gex.empty:
                st.warning("Tiada kecairan data opsyen aktif dalam julat harga ini. Sila luaskan julat % di sidebar.")
                st.stop()
            
            # PENGIRAAN MODEL GAMMA (GEX)
            df_gex['Call_Gamma'] = df_gex.apply(lambda r: calculate_gamma(spot_price, r['Strike'], t, risk_free_rate, r['Call_IV'] if r['Call_IV'] > 0 else 0.1), axis=1)
            df_gex['Put_Gamma'] = df_gex.apply(lambda r: calculate_gamma(spot_price, r['Strike'], t, risk_free_rate, r['Put_IV'] if r['Put_IV'] > 0 else 0.1), axis=1)
            
            # PENGIRAAN MODEL VANNA (VEX)
            df_gex['Call_Vanna'] = df_gex.apply(lambda r: calculate_vanna(spot_price, r['Strike'], t, risk_free_rate, r['Call_IV'] if r['Call_IV'] > 0 else 0.1, "call"), axis=1)
            df_gex['Put_Vanna'] = df_gex.apply(lambda r: calculate_vanna(spot_price, r['Strike'], t, risk_free_rate, r['Put_IV'] if r['Put_IV'] > 0 else 0.1, "put"), axis=1)
            
            # FORMULA ASAS EXPOSURE RAW
            df_gex['Call_GEX_Raw'] = df_gex['Call_Gamma'] * df_gex['Call_OI'] * (spot_price ** 2) * 0.01
            df_gex['Put_GEX_Raw'] = df_gex['Put_Gamma'] * df_gex['Put_OI'] * (spot_price ** 2) * 0.01 * (-1)
            df_gex['Net_GEX_Raw'] = df_gex['Call_GEX_Raw'] + df_gex['Put_GEX_Raw']
            
            df_gex['Call_VEX_Raw'] = df_gex['Call_Vanna'] * df_gex['Call_OI'] * spot_price * 0.01
            df_gex['Put_VEX_Raw'] = df_gex['Put_Vanna'] * df_gex['Put_OI'] * spot_price * 0.01
            df_gex['Net_VEX_Raw'] = df_gex['Call_VEX_Raw'] + df_gex['Put_VEX_Raw']
            
            df_gex = df_gex.sort_values('Strike').reset_index(drop=True)
            
            # TUKAR KE JUTA (MILLIONS)
            df_gex['Call_GEX_M'] = df_gex['Call_GEX_Raw'] / 1_000_000
            df_gex['Put_GEX_M'] = df_gex['Put_GEX_Raw'] / 1_000_000
            df_gex['Net_GEX_M'] = df_gex['Net_GEX_Raw'] / 1_000_000
            df_gex['Absolute_GEX_M'] = (df_gex['Call_GEX_Raw'].abs() + df_gex['Put_GEX_Raw'].abs()) / 1_000_000
            df_gex['Net_VEX_M'] = df_gex['Net_VEX_Raw'] / 1_000_000
            
            gamma_flip_strike = find_gamma_flip(df_gex.rename(columns={'Net_GEX_M': 'Net_GEX'}))
            gamma_wall_strike = df_gex.loc[df_gex['Absolute_GEX_M'].idxmax()]['Strike']
            
            # KPI PANEL ATAS
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Net GEX", f"${df_gex['Net_GEX_M'].sum():,.2f}M")
            col2.metric("Major Gamma Wall", f"${gamma_wall_strike:,.2f}")
            col3.metric("Total Net Vanna (VEX)", f"${df_gex['Net_VEX_M'].sum():,.2f}M / 1% IV Δ")
            
            st.markdown("---")
            
            # KEMASKINI: Bina custom data string berasingan untuk hilangkan masalah syntax bertindan
            hover_strings = []
            for _, row in df_gex.iterrows():
                h_text = f"Call OI: {row['Call_OI']/1000:,.0f}K<br>Put OI: {row['Put_OI']/1000:,.0f}K<br>Call Vol: {row['Call_Vol']/1000:,.0f}K<br>Put Vol: {row['Put_Vol']/1000:,.0f}K"
                hover_strings.append(h_text)
            df_gex['Hover_Text'] = hover_strings
            
            # -----------------------------------------------------------------
            # 1. NET GAMMA EXPOSURE (GRAF 1)
            # -----------------------------------------------------------------
            st.markdown("<h2 style='color: #00838F; font-family: sans-serif; font-size: 26px; font-weight: bold;'>1. Net Gamma Exposure Profile</h2>", unsafe_allow_html=True)
            
            fig1 = go.Figure()
            colors_net = ['#0D47A1' if x >= 0 else '#FF9800' for x in df_gex['Net_GEX_M']]
            
            fig1.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Net_GEX_M'], marker_color=colors_net, 
                name="Net GEX", customdata=df_gex['Hover_Text'],
                hovertemplate="<b>Strike: $%{x:.2f}</b><br>Net GEX: %{y:.2f}M<br><br>%{customdata}<extra></extra>"
            ))
            
            flip_point = gamma_flip_strike if gamma_flip_strike else spot_price
            fig1.add_vrect(x0=df_gex['Strike'].min(), x1=flip_point, fillcolor="#FFCDD2", opacity=0.15, line_width=0, layer="below")
            fig1.add_vrect(x0=flip_point, x1=df_gex['Strike'].max(), fillcolor="#C8E6C9", opacity=0.15, line_width=0, layer="below")
            
            fig1.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, 
                          annotation_text="Last Price", annotation_position="top left")
            if gamma_flip_strike:
                fig1.add_vline(x=gamma_flip_strike, line_dash="dash", line_color="#2E7D32", line_width=2, 
                              annotation_text="Gamma Flip", annotation_position="top right")
            
            fig1.update_layout(
                template="plotly_white", height=460, hovermode="x unified",
                margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
            )
            fig1.update_yaxes(title_text="Net GEX (Millions)", title_font=dict(size=12))
            fig1.update_xaxes(title_text="Strike Price", tickangle=-45, nticks=24, tickformat=".2f")
            st.plotly_chart(fig1, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # -----------------------------------------------------------------
            # 2. ABSOLUTE GAMMA EXPOSURE (GRAF 2)
            # -----------------------------------------------------------------
            st.markdown("<h2 style='color: #2E7D32; font-family: sans-serif; font-size: 26px; font-weight: bold;'>2. Absolute Gamma Exposure Profile</h2>", unsafe_allow_html=True)
            
            fig2 = go.Figure()
            
            fig2.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Call_GEX_M'], marker_color='#0D47A1', 
                name="Call Gamma Exposure", customdata=df_gex['Hover_Text'],
                hovertemplate="Call GEX: %{y:.2f}M<br>%{customdata}<extra></extra>"
            ))
            
            fig2.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Put_GEX_M'], marker_color='#FF9800', 
                name="Put Gamma Exposure", customdata=df_gex['Hover_Text'],
                hovertemplate="Put GEX: %{y:.2f}M<br>%{customdata}<extra></extra>"
            ))
            
            fig2.add_trace(go.Scatter(
                x=df_gex['Strike'], y=df_gex['Absolute_GEX_M'], mode='lines+markers',
                line=dict(color='#2E7D32', width=2.5), name="Absolute Profile",
                hovertemplate="Total Absolute: %{y:.2f}M<extra></extra>"
            ))
            
            fig2.add_vrect(x0=df_gex['Strike'].min(), x1=flip_point, fillcolor="#FFCDD2", opacity=0.15, line_width=0, layer="below")
            fig2.add_vrect(x0=flip_point, x1=df_gex['Strike'].max(), fillcolor="#C8E6C9", opacity=0.15, line_width=0, layer="below")
            fig2.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Last Price")
            
            fig2.update_layout(
                template="plotly_white", height=460, barmode='relative', hovermode="x unified", 
                margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
            )
            fig2.update_yaxes(title_text="Absolute GEX (Millions)", title_font=dict(size=12))
            fig2.update_xaxes(title_text="Strike Price", tickangle=-45, nticks=24, tickformat=".2f")
            st.plotly_chart(fig2, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # -----------------------------------------------------------------
            # 3. NET VANNA EXPOSURE PROFILE (GRAF 3)
            # -----------------------------------------------------------------
            st.markdown("<h2 style='color: #4A148C; font-family: sans-serif; font-size: 26px; font-weight: bold;'>3. Net Vanna Exposure Profile (VEX)</h2>", unsafe_allow_html=True)
            
            fig3 = go.Figure()
            colors_vex = ['#4A148C' if x >= 0 else '#D32F2F' for x in df_gex['Net_VEX_M']]
            
            fig3.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Net_VEX_M'], marker_color=colors_vex,
                name="Net VEX", customdata=df_gex['Hover_Text'],
                hovertemplate="<b>Strike: $%{x:.2f}</b><br>Net Vanna: %{y:.2f}M per 1% IV Δ<br><br>%{customdata}<extra></extra>"
            ))
            
            fig3.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Last Price")
            
            fig3.update_layout(
                template="plotly_white", height=460, hovermode="x unified",
                margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
            )
            fig3.update_yaxes(title_text="Net Vanna Exposure ($M per 1% IV)", title_font=dict(size=12))
            fig3.update_xaxes(title_text="Strike Price", tickangle=-45, nticks=24, tickformat=".2f")
            st.plotly_chart(fig3, use_container_width=True)
            
            # SEKSYEN DOWNLOAD
            st.markdown("### 📥 Simpan Data Mentah")
            csv_data = df_gex[['Strike', 'Call_OI', 'Put_OI', 'Call_Vol', 'Put_Vol', 'Net_GEX_M', 'Absolute_GEX_M', 'Net_VEX_M']].to_csv(index=False)
            st.download_button(label="Muat Turun Fail CSV", data=csv_data, file_name=f"{ticker_symbol}_gex_vex_data.csv", mime="text/csv")
            
        except Exception as e:
            st.error(f"Ralat susunan grafik: {e}")