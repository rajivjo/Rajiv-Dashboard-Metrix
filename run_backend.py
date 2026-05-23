from fastapi import FastAPI
import yfinance as yf
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Benarkan semua akses dari Streamlit Cloud
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/get_data/{ticker}")
async def get_data(ticker: str):
    try:
        t = yf.Ticker(ticker)
        spot_price = t.history(period="1d")['Close'].iloc[-1]
        expirations = t.options
        
        return {
            "spot_price": float(spot_price),
            "expirations": expirations
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
