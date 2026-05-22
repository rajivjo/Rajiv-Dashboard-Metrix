# server.py
import json
import asyncio
import numpy as np
import yfinance as yf
from datetime import datetime
import pytz
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="Rajiv Institutional Matrix Engine")

# ❄️ Laci RAM Utama untuk pembekuan data
FROZEN_DATABASE = {}

def get_malaysia_time():
    """Mendapatkan zon waktu semasa di Malaysia (MYT)"""
    tz = pytz.timezone('Asia/Kuala_Lumpur')
    return datetime.now(tz)

def process_and_calculate_greeks(ticker_symbol: str):
    """
    Simulasi enjin pengiraan kuantitatif Greeks (Charm, Vanna, GEX).
    Dalam kod sebenar kau, gantikan bahagian ini dengan formula Black-Scholes kau.
    """
    # Contoh simulasi penjanaan grid strike di sekeliling harga pasaran
    ticker_data = yf.Ticker(ticker_symbol)
    
    try:
        current_spot = float(ticker_data.fast_info['lastPrice'])
    except:
        current_spot = 180.0  # Harga sandaran jika yfinance ralat (cth: GLD)

    grid_strikes = np.arange(current_spot * 0.95, current_spot * 1.05, 0.5)
    grid_strikes = [round(float(x), 2) for x in grid_strikes]
    
    # Menjana data matriks simulasi Greeks
    net_charm_m = [float(x) for x in np.random.uniform(-5.0, 5.0, len(grid_strikes))]
    net_vanna_m = [float(x) for x in np.random.uniform(-8.0, 8.0, len(grid_strikes))]
    gamma_flip = round(float(np.random.choice(grid_strikes)), 2)

    return {
        "base_spot": current_spot,
        "gamma_flip": gamma_flip,
        "grid_strikes": grid_strikes,
        "net_charm_m": net_charm_m,
        "net_vanna_m": net_vanna_m,
        "timestamp": datetime.now().isoformat()
    }

def get_live_market_spot(current_spot, ticker_symbol="GLD"):
    """
    Automatik Tukar Mod: 
    - Jam 7:00 Malam hingga 5:00 Pagi (MYT): Sedut Real-Time Spot Sebenar Pasaran US
    - Waktu Selain Itu: Pakai Simulasi Turun Naik Lembut (Sebab Bursa US Tutup)
    """
    now_myt = get_malaysia_time()
    current_hour = now_myt.hour
    current_weekday = now_myt.weekday() # 0 = Isnin, 4 = Jumaat

    # Pasaran US bergerak Isnin - Jumaat, jam 7:00 Malam (19) hingga 5:00 Pagi (5) esoknya
    is_us_live_hours = (current_hour >= 19 or current_hour < 5) and current_weekday <= 4

    if is_us_live_hours:
        try:
            ticker_data = yf.Ticker(ticker_symbol)
            live_market_price = float(ticker_data.fast_info['lastPrice'])
            if live_market_price > 0:
                print(f"🟢 [MOD LIVE REAL-TIME] {ticker_symbol} Spot: ${live_market_price:.2f}")
                return live_market_price
        except Exception as e:
            print(f"⚠️ Gagal ragut harga live market ({e}), beralih ke mod backup.")
    
    # Mod simulasi pergerakan rawak sen (waktu pasaran US katup)
    random_move = float(np.random.uniform(-0.04, 0.04))
    print(f"❄️ [MOD SIMULASI] {ticker_symbol} Spot: ${current_spot + random_move:.2f}")
    return current_spot + random_move

@app.get("/api/freeze-pagi")
def freeze_pagi(ticker: str = "GLD"):
    """API Endpoint yang dicetuskan oleh Cron Job jam 7 Pagi & 7 Malam"""
    global FROZEN_DATABASE
    print(f"❄️ Menjalankan pembekuan data automatik untuk {ticker}...")
    
    # Sedut data opsyen mutakhir dan kira Greeks awal
    calculated_data = process_and_calculate_greeks(ticker)
    FROZEN_DATABASE[ticker] = calculated_data
    
    return {
        "status": "success",
        "message": f"Data opsyen terbaharu {ticker} berjaya dibekukan dalam RAM!",
        "time_myt": get_malaysia_time().strftime('%Y-%m-%d %H:%M:%S')
    }

@app.websocket("/ws/live-matrix")
async def websocket_endpoint(websocket: WebSocket):
    """Paip WebSockets yang menolak data matrik ke Streamlit setiap 1 saat tanpa henti"""
    await websocket.accept()
    
    # Ambil parameter ticker daripada URL (default: GLD)
    query_params = websocket.query_params
    ticker = query_params.get("ticker", "GLD").upper()
    
    # Jika RAM kosong (cth: server baru restart), paksa freeze sekali
    if ticker not in FROZEN_DATABASE:
        FROZEN_DATABASE[ticker] = process_and_calculate_greeks(ticker)
        
    current_sim_spot = FROZEN_DATABASE[ticker]["base_spot"]

    try:
        while True:
            # 1. Dapatkan harga spot terkini mengikut zon masa (Live vs Simulasi)
            current_sim_spot = get_live_market_spot(current_sim_spot, ticker_symbol=ticker)
            
            # 2. Ambil struktur data opsyen tegar yang dibekukan dalam RAM
            frozen_data = FROZEN_DATABASE[ticker]
            
            # 3. Satukan data opsyen beku bersama harga spot dinamik masa nyata
            payload = {
                "live_spot": current_sim_spot,
                "gamma_flip": frozen_data["gamma_flip"],
                "grid_strikes": frozen_data["grid_strikes"],
                "net_charm_m": frozen_data["net_charm_m"],
                "net_vanna_m": frozen_data["net_vanna_m"],
                "timestamp": datetime.now().isoformat()
            }
            
            # 4. Tembak data ke Streamlit frontend
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1)  # Hantar setiap 1 saat
            
    except WebSocketDisconnect:
        print(f"🔴 Talian sambungan Streamlit diputuskan bagi {ticker}.")
    except Exception as e:
        print(f"⚠️ Ralat dalam saluran WebSocket: {e}")