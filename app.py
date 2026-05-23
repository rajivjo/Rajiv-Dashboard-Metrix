import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

# --- 1. FUNGSI PENGAMBILAN DATA (Wajib di atas) ---
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

# --- 2. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Rajiv Exposure Matrix", layout="wide")
st.title("📊 Rajiv Exposure Matrix")

# Fungsi untuk menentukan Weekly/Monthly Expiry
def get_expiry_tag(date_str):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        year, month = dt.year
