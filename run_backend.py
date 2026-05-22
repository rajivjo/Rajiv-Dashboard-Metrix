import uvicorn
from fastapi import FastAPI, WebSocket
import asyncio
import json
import pandas as pd
from utils.data_fetcher import get_options_data
from utils.math_engine import calculate_gamma, calculate_vanna, calculate_charm

app = FastAPI()

# Konfigurasi asas
RISK_FREE_RATE = 0.04  # Boleh diubah suai atau ditarik dari config

@app.websocket("/ws/live-matrix")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    ticker = "SPY"  # Default ticker
    
    while True:
        try:
            # 1. Ambil data mentah (menggunakan cache dari data_fetcher)
            data = get_options_data(ticker)
            spot = float(data.get('spot_price', 0.0))
            
            # Simulasi pengiraan untuk dihantar ke Frontend
            # Dalam versi backend penuh, anda boleh letak logic pengiraan di sini
            # atau biarkan Frontend yang buat pengiraan berat.
            
            payload = {
                "live_spot": spot,
                "gamma_flip": 0.0, # Akan dikira dalam math_engine nanti
                "timestamp": str(data.get('timestamp', ''))
            }
            
            # Hantar data kepada Frontend
            await websocket.send_text(json.dumps(payload))
            
        except Exception as e:
            print(f"Backend Error: {e}")
            # Hantar signal kosong jika error untuk elak frontend crash
            await websocket.send_text(json.dumps({"error": "Data fetch failed"}))
            
        # Delay 60 saat sebelum update seterusnya
        await asyncio.sleep(60)

if __name__ == "__main__":
    # Menjalankan server pada port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)