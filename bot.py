# bot.py - بوت Quotex بسيط للديمو (جرب على PRACTICE أولاً)
import asyncio
import os
import time
from datetime import datetime
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import AverageTrueRange

# غير المكتبة حسب اللي هتثبتها، هنا نستخدم pyquotex كمثال
from pyquotex.stable_api import Quotex  # لو استخدمت pyquotex

EMAIL = os.environ.get("QUOTEX_EMAIL", "your@email.com")          # ← غيرها في Render
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "yourpassword")      # ← غيرها في Render

ASSETS = ["EURUSD", "GBPUSD", "GOLD"]  # أضف أصول OTC لو عايز 24/7
EXPIRY = 60                            # 60 ثانية
AMOUNT = 1                             # ابدأ بـ1 دولار في الديمو
COOLDOWN = 300                         # 5 دقايق بين صفقات نفس الأصل

client = Quotex(email=EMAIL, password=PASSWORD)

async def connect():
    check, msg = await client.connect()
    if check:
        print("تم الاتصال:", msg)
        await client.change_account("PRACTICE")  # PRACTICE = ديمو
    else:
        print("فشل الاتصال:", msg)
        exit(1)

def get_candles(asset, count=100):
    try:
        candles = client.get_candles(asset, 60, count, time.time())
        if not candles:
            return None
        df = pd.DataFrame(candles)
        df["close"] = df["close"].astype(float)
        df["RSI"] = RSIIndicator(df["close"], 14).rsi()
        macd = MACD(df["close"])
        df["macd"] = macd.macd()
        df["signal"] = macd.macd_signal()
        return df.dropna().tail(50)
    except:
        return None

async def check_signal(asset, df):
    if df is None or len(df) < 20:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    rsi = last["RSI"]
    macd_up = prev["macd"] < prev["signal"] and last["macd"] > last["signal"]
    macd_down = prev["macd"] > prev["signal"] and last["macd"] < last["signal"]
    
    if rsi < 40 and macd_up:
        return "call"
    if rsi > 60 and macd_down:
        return "put"
    return None

async def main_loop():
    await connect()
    print("البوت شغال... اضغط Ctrl+C للإيقاف")
    last_trade = {}
    while True:
        for asset in ASSETS:
            df = get_candles(asset)
            action = await check_signal(asset, df)
            if action:
                now = time.time()
                if asset in last_trade and now - last_trade[asset] < COOLDOWN:
                    continue
                print(f"إشارة: {action.upper()} على {asset}")
                check, order_id = client.buy(AMOUNT, asset, action, EXPIRY)
                if check:
                    last_trade[asset] = now
                    print(f"تم الدخول: {order_id}")
                else:
                    print("فشل الدخول")
        await asyncio.sleep(45)  # فحص كل ~45 ثانية

if __name__ == "__main__":
    asyncio.run(main_loop())
 
