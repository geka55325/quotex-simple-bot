# bot.py - بوت Quotex بسيط للديمو (جرب على PRACTICE أولاً)
import asyncio
import os
import time
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD

# استخدام quotexpy (اللي مثبتة في requirements.txt)
from quotexpy import Quotex

# متغيرات البيئة من Render
EMAIL = os.environ.get("QUOTEX_EMAIL", "your@email.com")
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "yourpassword")

ASSETS = ["EURUSD", "GBPUSD", "GOLD"]  # أضف "_otc" لو عايز تداول في الويك إند، مثلاً "EURUSD_otc"
EXPIRY = 60                            # ثواني (مدة الصفقة)
AMOUNT = 1                             # مبلغ الصفقة (صغير في الديمو)
COOLDOWN = 300                         # 5 دقايق بين صفقات نفس الأصل

client = Quotex(email=EMAIL, password=PASSWORD)

async def connect():
    try:
        connected = await client.connect()
        if connected:
            print("تم الاتصال بنجاح!")
            change_ok = await client.change_account("PRACTICE")  # PRACTICE = ديمو
            if change_ok:
                print("تم تغيير الحساب إلى ديمو (PRACTICE)")
            else:
                print("فشل تغيير الحساب إلى PRACTICE")
                return False
            return True
        else:
            print("فشل الاتصال بالمنصة")
            return False
    except Exception as e:
        print(f"خطأ أثناء الاتصال: {e}")
        return False

def get_candles(asset, count=100):
    try:
        # quotexpy غالباً بتستخدم get_candles بدون async في بعض الإصدارات، جرب كده
        candles = client.get_candles(asset, 60, count, time.time())  # 60 = timeframe 1 دقيقة
        if not candles or not isinstance(candles, list):
            print(f"لا توجد كاندلز لـ {asset}")
            return None
        
        df = pd.DataFrame(candles)
        if 'close' not in df.columns:
            print("مشكلة في هيكل الكاندلز - لا يوجد عمود close")
            return None
        
        df["close"] = df["close"].astype(float)
        df["RSI"] = RSIIndicator(df["close"], 14).rsi()
        macd = MACD(df["close"])
        df["macd"] = macd.macd()
        df["signal"] = macd.macd_signal()
        
        df_clean = df.dropna().tail(50)
        if len(df_clean) < 20:
            print(f"بيانات غير كافية بعد التنظيف لـ {asset}")
            return None
        return df_clean
    except Exception as e:
        print(f"خطأ في جلب الكاندلز لـ {asset}: {e}")
        return None

async def check_signal(asset, df):
    if df is None or len(df) < 20:
        return None
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    rsi = last["RSI"]
    
    macd_up = (prev["macd"] < prev["signal"]) and (last["macd"] > last["signal"])
    macd_down = (prev["macd"] > prev["signal"]) and (last["macd"] < last["signal"])
    
    if rsi < 40 and macd_up:
        return "call"
    if rsi > 60 and macd_down:
        return "put"
    return None

async def main_loop():
    if not await connect():
        print("لا يمكن المتابعة بدون اتصال ناجح. إعادة المحاولة بعد 60 ثانية...")
        await asyncio.sleep(60)
        await main_loop()  # إعادة محاولة
        return
    
    print("البوت شغال الآن... مراقبة كل 45 ثانية")
    last_trade = {}
    
    while True:
        try:
            for asset in ASSETS:
                df = get_candles(asset)
                if df is None:
                    continue
                
                action = await check_signal(asset, df)
                if action:
                    now = time.time()
                    if asset in last_trade and now - last_trade[asset] < COOLDOWN:
                        print(f"Cooldown نشط لـ {asset}، تخطي")
                        continue
                    
                    print(f"إشارة جديدة: {action.upper()} على {asset} | RSI: {df.iloc[-1]['RSI']:.1f}")
                    
                    # الشراء في quotexpy
                    success, order_id = await client.buy_simple(AMOUNT, asset, action, EXPIRY)
                    # أو جرب: success, order_id = client.buy(AMOUNT, asset, action, EXPIRY) حسب الإصدار
                    
                    if success:
                        last_trade[asset] = now
                        print(f"تم فتح الصفقة بنجاح! Order ID: {order_id}")
                    else:
                        print("فشل فتح الصفقة")
            
            await asyncio.sleep(45)
        except Exception as e:
            print(f"خطأ في الحلقة الرئيسية: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(main_loop())
