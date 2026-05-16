import numpy as np
import scipy.stats as si

def calculate_gamma(S, K, t, r, sigma):
    """
    Mengira nilai Gamma (Γ) untuk kontrak opsyen menggunakan model Black-Scholes.
    S: Harga Saham Semasa (Spot Price)
    K: Strike Price
    t: Tempoh Matang dalam Tahun (Days to Expiration / 365)
    r: Risk-free Interest Rate (Kadar Bebas Risiko)
    sigma: Implied Volatility (IV)
    """
    if t <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    gamma = si.norm.pdf(d1) / (S * sigma * np.sqrt(t))
    return gamma

def calculate_vanna(S, K, t, r, sigma, option_type="call"):
    """
    Mengira nilai Vanna (dGamma/dVol atau dDelta/dVol) menggunakan model Black-Scholes.
    Menunjukkan sensitiviti Delta opsyen terhadap perubahan Implied Volatility (IV).
    
    Pelarasan tanda (+/-) disesuaikan untuk simulasi posisi Short Gamma/Vanna 
    oleh Market Maker (Dealer Inventory):
    - Call Vanna: Secara teorinya bernilai positif (Long Call), dilaraskan untuk Dealer Net Hedging.
    - Put Vanna: Secara teorinya terbalik, dilaraskan mengikut kesan arah pendedahan pasaran.
    """
    if t <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0
        
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * t) / (sigma * np.sqrt(t))
    d2 = d1 - sigma * np.sqrt(t)
    
    # n'(d1) - Standard normal density function (PDF)
    nd1 = si.norm.pdf(d1)
    
    # Formula Matematik Vanna Asal (Black-Scholes Greek)
    vanna = -nd1 * d2 / sigma
    
    # Pelarasan Inventory untuk Dealer Hedging Matrix
    # Sesuai untuk dipetakan terus bersama Open Interest dalam matriks pendedahan
    if option_type == "put":
        return vanna * -1
    return vanna

def find_gamma_flip(df):
    """
    Mencari strike price di mana Net GEX berubah tanda daripada negatif ke positif 
    atau sebaliknya menggunakan interpolasi linear berdekatan paksi sifar (Zero GEX).
    """
    if df.empty or 'Strike' not in df.columns or 'Net_GEX' not in df.columns:
        return None
        
    df_sorted = df.sort_values('Strike').reset_index(drop=True)
    
    # Imbas keseluruhan baris data untuk mencari pertukaran tanda (+ ke - atau - ke +)
    for i in range(len(df_sorted) - 1):
        gex_current = df_sorted.loc[i, 'Net_GEX']
        gex_next = df_sorted.loc[i+1, 'Net_GEX']
        
        # Mengesan lintasan paksi sifar (Zero-Crossing)
        if (gex_current < 0 and gex_next > 0) or (gex_current > 0 and gex_next < 0):
            strike_current = df_sorted.loc[i, 'Strike']
            strike_next = df_sorted.loc[i+1, 'Strike']
            
            # Rumus Interpolasi Linear tepat: 
            # x = x1 - y1 * (x2 - x1) / (y2 - y1)
            if (gex_next - gex_current) == 0:
                continue
            flip_strike = strike_current - gex_current * (strike_next - strike_current) / (gex_next - gex_current)
            return flip_strike
            
    return None