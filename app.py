import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime
from utils.data_fetcher import get_options_data
from utils.math_engine import calculate_gamma, calculate_vanna, calculate_charm, find_gamma_flip

# CONFIG HALAMAN DASHBOARD
st.set_page_config(page_title="Institutional GEX, VEX & CEX Dashboard", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

# FUNGSI UNTUK MENENTUKAN TAG WEEKLY (w) ATAU MONTHLY (m) WITHOUT CHANGING ANY MAIN ENGINE NAMES
def get_expiry_tag(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Semak jika hari Jumaat (weekday == 4) dan jatuh antara 15hb hingga 21hb (Monthly Expiry)
        if dt.weekday() == 4 and (15 <= dt.day <= 21):
            return f"{date_str} (m)"
        else:
            return f"{date_str} (w)"
    except:
        return date_str

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
                
            # 🟢 BINA PEMETAAN TAG TANPA MENGUBAH STRUKTUR ASAL EXPIRATIONS
            expiry_mapping = {get_expiry_tag(d): d for d in expirations}
            display_options = list(expiry_mapping.keys())
            
            # 🟢 TUKAR KEPADA MULTISELECT AGREGAT MALAYSIA STYLE
            selected_display_expiries = st.sidebar.multiselect(
                "Pilih Tarikh Tamat Opsyen (Boleh Pilih Banyak):", 
                options=display_options,
                default=[display_options[0]] if display_options else None
            )
            
            if not selected_display_expiries:
                st.warning("Sila pilih sekurang-kurangnya satu tarikh tamat opsyen.")
                st.stop()
                
            # Tukar semula string paparan ber-tag kepada tarikh asal untuk kegunaan yfinance
            selected_expiries = [expiry_mapping[tag] for tag in selected_display_expiries]
            
            ticker = yf.Ticker(ticker_symbol)
            all_calls_list = []
            all_puts_list = []
            
            # Kira purata baki masa (t) berasaskan pilihan expiries yang dipilih tanpa ubah formula asal
            today = datetime.now().date()
            t_total = 0
            
            for expiry in selected_expiries:
                expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                t_expiry = max((expiry_date - today).days, 0.5) / 365.0
                t_total += t_expiry
                
                opt_chain = ticker.option_chain(expiry)
                
                c_df = opt_chain.calls[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
                p_df = opt_chain.puts[['strike', 'openInterest', 'volume', 'impliedVolatility']].copy()
                
                all_calls_list.append(c_df)
                all_puts_list.append(p_df)
                
            t = t_total / len(selected_expiries)
            
            # Gabungkan data mengikut Strike Price tanpa mengubah nama kolom asal yang diperlukan di bawah
            calls_combined = pd.concat(all_calls_list).groupby('strike').agg({
                'openInterest': 'sum',
                'volume': 'sum',
                'impliedVolatility': 'mean'
            }).reset_index().rename(columns={'strike': 'Strike', 'volume': 'Call_Vol'})
            
            puts_combined = pd.concat(all_puts_list).groupby('strike').agg({
                'openInterest': 'sum',
                'volume': 'sum',
                'impliedVolatility': 'mean'
            }).reset_index().rename(columns={'strike': 'Strike', 'volume': 'Put_Vol'})
            
            calls_combined = calls_combined[calls_combined['impliedVolatility'] > 0.01]
            puts_combined = puts_combined[puts_combined['impliedVolatility'] > 0.01]
            
            lower_bound = spot_price * (1 - (spot_range_pct / 100))
            upper_bound = spot_price * (1 + (spot_range_pct / 100))
            
            strikes = sorted(list(set(calls_combined['Strike']).union(set(puts_combined['Strike']))))
            df_gex = pd.DataFrame({'Strike': strikes})
            df_gex = df_gex[(df_gex['Strike'] >= lower_bound) & (df_gex['Strike'] <= upper_bound)].copy()
            
            df_gex = df_gex.merge(calls_combined.rename(columns={'openInterest': 'Call_OI', 'impliedVolatility': 'Call_IV'}), on='Strike', how='left')
            df_gex = df_gex.merge(puts_combined.rename(columns={'openInterest': 'Put_OI', 'impliedVolatility': 'Put_IV'}), on='Strike', how='left')
            df_gex = df_gex.fillna(0)
            
            df_gex = df_gex[(df_gex['Call_OI'] > 0) | (df_gex['Put_OI'] > 0)].copy()
            
            if df_gex.empty:
                st.warning("Tiada kecairan data opsyen aktif dalam julat harga ini. Sila luaskan julat % di sidebar.")
                st.stop()
            
            # KEKAL NAMA ENGINE DAN PEMOLEH UBAH ASAL SEPERTI YANG ANDA RENAME
            df_gex['Call_Gamma'] = df_gex.apply(lambda r: calculate_gamma(spot_price, r['Strike'], t, risk_free_rate, r['Call_IV'] if r['Call_IV'] > 0 else 0.1), axis=1)
            df_gex['Put_Gamma'] = df_gex.apply(lambda r: calculate_gamma(spot_price, r['Strike'], t, risk_free_rate, r['Put_IV'] if r['Put_IV'] > 0 else 0.1), axis=1)
            
            df_gex['Call_Vanna'] = df_gex.apply(lambda r: calculate_vanna(spot_price, r['Strike'], t, risk_free_rate, r['Call_IV'] if r['Call_IV'] > 0 else 0.1, "call"), axis=1)
            df_gex['Put_Vanna'] = df_gex.apply(lambda r: calculate_vanna(spot_price, r['Strike'], t, risk_free_rate, r['Put_IV'] if r['Put_IV'] > 0 else 0.1, "put"), axis=1)
            
            df_gex['Call_Charm'] = df_gex.apply(lambda r: calculate_charm(spot_price, r['Strike'], t, risk_free_rate, r['Call_IV'] if r['Call_IV'] > 0 else 0.1, "call"), axis=1)
            df_gex['Put_Charm'] = df_gex.apply(lambda r: calculate_charm(spot_price, r['Strike'], t, risk_free_rate, r['Put_IV'] if r['Put_IV'] > 0 else 0.1, "put"), axis=1)
            
            # RAW EXPOSURE CALCULATIONS
            df_gex['Call_GEX_Raw'] = df_gex['Call_Gamma'] * df_gex['Call_OI'] * (spot_price ** 2) * 0.01
            df_gex['Put_GEX_Raw'] = df_gex['Put_Gamma'] * df_gex['Put_OI'] * (spot_price ** 2) * 0.01 * (-1)
            df_gex['Net_GEX_Raw'] = df_gex['Call_GEX_Raw'] + df_gex['Put_GEX_Raw']
            
            df_gex['Call_VEX_Raw'] = df_gex['Call_Vanna'] * df_gex['Call_OI'] * spot_price * 0.01
            df_gex['Put_VEX_Raw'] = df_gex['Put_Vanna'] * df_gex['Put_OI'] * spot_price * 0.01
            df_gex['Net_VEX_Raw'] = df_gex['Call_VEX_Raw'] + df_gex['Put_VEX_Raw']
            
            df_gex['Call_CEX_Raw'] = df_gex['Call_Charm'] * df_gex['Call_OI'] * spot_price
            df_gex['Put_CEX_Raw'] = df_gex['Put_Charm'] * df_gex['Put_OI'] * spot_price
            df_gex['Net_CEX_Raw'] = df_gex['Call_CEX_Raw'] + df_gex['Put_CEX_Raw']
            
            df_gex = df_gex.sort_values('Strike').reset_index(drop=True)
            
            # TUKAR SKALA KE JUTA (MILLIONS)
            df_gex['Call_GEX_M'] = df_gex['Call_GEX_Raw'] / 1_000_000
            df_gex['Put_GEX_M'] = df_gex['Put_GEX_Raw'] / 1_000_000
            df_gex['Net_GEX_M'] = df_gex['Net_GEX_Raw'] / 1_000_000
            df_gex['Absolute_GEX_M'] = (df_gex['Call_GEX_Raw'].abs() + df_gex['Put_GEX_Raw'].abs()) / 1_000_000
            
            df_gex['Net_VEX_M'] = df_gex['Net_VEX_Raw'] / 1_000_000
            df_gex['Net_CEX_M'] = df_gex['Net_CEX_Raw'] / 1_000_000
            
            gamma_flip_strike = find_gamma_flip(df_gex.rename(columns={'Net_GEX_M': 'Net_GEX'}))
            gamma_wall_strike = df_gex.loc[df_gex['Absolute_GEX_M'].idxmax()]['Strike']
            
            # KPI PANEL ATAS
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Net GEX", f"${df_gex['Net_GEX_M'].sum():,.2f}M")
            col2.metric("Major Gamma Wall", f"${gamma_wall_strike:,.2f}")
            col3.metric("Total Net Vanna", f"${df_gex['Net_VEX_M'].sum():,.2f}M/1%Δ")
            col4.metric("Total Net Charm (Bleed)", f"${df_gex['Net_CEX_M'].sum():,.2f}M/Hari")
            
            st.markdown("---")
            
            flip_point = gamma_flip_strike if gamma_flip_strike else spot_price

            # -----------------------------------------------------------------
            # 1. NET GAMMA EXPOSURE (GRAF 1)
            # -----------------------------------------------------------------
            st.markdown("<h2 style='color: #00838F; font-family: sans-serif; font-size: 26px; font-weight: bold;'>1. Net Gamma Exposure Profile</h2>", unsafe_allow_html=True)
            
            fig1 = go.Figure()
            colors_net = ['#0D47A1' if x >= 0 else '#FF9800' for x in df_gex['Net_GEX_M']]
            
            fig1.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Net_GEX_M'], marker_color=colors_net, 
                name="Net GEX",
                hovertemplate="Net GEX: %{y:.2f}M<extra></extra>"
            ))
            
            fig1.add_vrect(x0=df_gex['Strike'].min(), x1=flip_point, fillcolor="#FFCDD2", opacity=0.15, line_width=0, layer="below")
            fig1.add_vrect(x0=flip_point, x1=df_gex['Strike'].max(), fillcolor="#C8E6C9", opacity=0.15, line_width=0, layer="below")
            fig1.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Last Price")
            if gamma_flip_strike:
                fig1.add_vline(x=gamma_flip_strike, line_dash="dash", line_color="#2E7D32", line_width=2, annotation_text="Gamma Flip")
            
            fig1.update_layout(
                template="plotly_white", height=440, margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
                hovermode="x unified"
            )
            fig1.update_yaxes(title_text="Net GEX (Millions)")
            fig1.update_xaxes(title_text="Strike Price", tickangle=-45, nticks=24, tickformat=".2f")
            st.plotly_chart(fig1, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # -----------------------------------------------------------------
            # 2. ABSOLUTE GAMMA EXPOSURE (GRAF 2) - OVERLAY BAR ATAS/BAWAH
            # -----------------------------------------------------------------
            st.markdown("<h2 style='color: #2E7D32; font-family: sans-serif; font-size: 26px; font-weight: bold;'>2. Absolute Gamma Exposure Profile</h2>", unsafe_allow_html=True)
            
            fig2 = go.Figure()
            
            # Bar Call (Biru - Atas)
            fig2.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Call_GEX_M'], 
                marker_color='#0D47A1', name="Call GEX", 
                hovertemplate="Call GEX: %{y:.2f}M<extra></extra>"
            ))
            
            # Bar Put (Oren - Bawah)
            fig2.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Put_GEX_M'], 
                marker_color='#FF9800', name="Put GEX", 
                hovertemplate="Put GEX: %{y:.2f}M<extra></extra>"
            ))
            
            # Garisan Absolute (Hijau - Terapung Di Atas Mengira Kekuatan Mutlak)
            fig2.add_trace(go.Scatter(
                x=df_gex['Strike'], y=df_gex['Absolute_GEX_M'], 
                mode='lines+markers', line=dict(color='#2E7D32', width=2.5), 
                name="Total Absolute", 
                hovertemplate="Total Abs Wall: %{y:.2f}M<extra></extra>"
            ))
            
            fig2.add_vrect(x0=df_gex['Strike'].min(), x1=flip_point, fillcolor="#FFCDD2", opacity=0.15, line_width=0, layer="below")
            fig2.add_vrect(x0=flip_point, x1=df_gex['Strike'].max(), fillcolor="#C8E6C9", opacity=0.15, line_width=0, layer="below")
            fig2.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Last Price")
            
            fig2.update_layout(
                template="plotly_white", height=440, barmode='overlay', margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
                hovermode="x unified"
            )
            fig2.update_yaxes(title_text="Gamma Exposure (Millions)")
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
                x=df_gex['Strike'], y=df_gex['Net_VEX_M'], marker_color=colors_vex, name="Net Vanna",
                hovertemplate="Net Vanna: %{y:.2f}M per 1% IV Δ<extra></extra>"
            ))
            fig3.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Last Price")
            
            fig3.update_layout(
                template="plotly_white", height=440, margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
                hovermode="x unified"
            )
            fig3.update_yaxes(title_text="Net Vanna Exposure ($M per 1% IV)")
            fig3.update_xaxes(title_text="Strike Price", tickangle=-45, nticks=24, tickformat=".2f")
            st.plotly_chart(fig3, use_container_width=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # -----------------------------------------------------------------
            # 4. NET CHARM EXPOSURE PROFILE (GRAF 4)
            # -----------------------------------------------------------------
            st.markdown("<h2 style='color: #004D40; font-family: sans-serif; font-size: 26px; font-weight: bold;'>4. Net Charm Exposure Profile (CEX / Time Bleed)</h2>", unsafe_allow_html=True)
            
            fig4 = go.Figure()
            colors_cex = ['#00695C' if x >= 0 else '#C62828' for x in df_gex['Net_CEX_M']]
            
            fig4.add_trace(go.Bar(
                x=df_gex['Strike'], y=df_gex['Net_CEX_M'], marker_color=colors_cex, name="Net Charm",
                hovertemplate="Charm Bleed: %{y:.2f}M per Day<extra></extra>"
            ))
            fig4.add_vline(x=spot_price, line_dash="solid", line_color="#212121", line_width=2, annotation_text="Last Price")
            
            fig4.update_layout(
                template="plotly_white", height=440, margin=dict(t=30, b=60, l=60, r=40),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center"),
                hovermode="x unified"
            )
            fig4.update_yaxes(title_text="Net Charm Exposure ($M per Day)")
            fig4.update_xaxes(title_text="Strike Price", tickangle=-45, nticks=24, tickformat=".2f")
            st.plotly_chart(fig4, use_container_width=True)
            
            # SEKSYEN DOWNLOAD
            st.markdown("### 📥 Simpan Data Mentah")
            csv_data = df_gex[['Strike', 'Call_OI', 'Put_OI', 'Call_Vol', 'Put_Vol', 'Net_GEX_M', 'Absolute_GEX_M', 'Net_VEX_M', 'Net_CEX_M']].to_csv(index=False)
            st.download_button(label="Muat Turun Fail CSV", data=csv_data, file_name=f"{ticker_symbol}_aggregated_gex_data.csv", mime="text/csv")
            
        except Exception as e:
            st.error(f"Ralat susunan grafik: {e}")
