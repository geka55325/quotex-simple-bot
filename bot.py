# bot.py - نسخة معدلة لتتبع الأخطاء على Render
import asyncio
import os
import time
import traceback  # لطباعة الأخطاء الكاملة
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD

from quotexpy import Quotex

EMAIL = os.environ.get("QUOTEX_EMAIL", "your@email.com")
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "yourpassword")

ASSETS = ["EURUSD", "GBPUSD", "GOLD"]
EXPIRY = 60
AMOUNT = 1
COOLDOWN = 300

client = Quotex(email=EMAIL, password=PASSWORD)
client.debug_ws_enable = True  # شغل debug للـ websocket عشان نشوف التفاصيل

async def connect():
    try:
        print("جاري محاولة الاتصال...")
        connected = await client.connect()
        if connected:
            print("تم الاتصال بنجاح!")
            change_ok = await client.change_account("PRACTICE")
            if change_ok:
                print("تم تغيير الحساب إلى PRACTICE (ديمو)")
            else:
                print("فشل تغيير الحساب")
            return True
        else:
            print("فشل الاتصال - connected = False")
            return False
    except Exception as e:
        print(f"خطأ أثناء الاتصال: {str(e)}")
        traceback.print_exc()  # طباعة stack trace كامل
        return False

# باقي الدوال زي ما هي (get_candles, check_signal, main_loop) بدون تغيير كبير
# لكن في main_loop أضف print أكتر

async def main_loop():
    connected = await connect()
    if not connected:
        print("الاتصال فشل، هنجرب تاني بعد 60 ثانية...")
        await asyncio.sleep(60)
        await main_loop()  # retry
        return

    print("البوت شغال ومتصل! مراقبة الأصول...")
    last_trade = {}

    while True:
        try:
            for asset in ASSETS:
                print(f"جاري فحص {asset}...")
                df = get_candles(asset)
                if df is None:
                    print(f"لا بيانات لـ {asset}")
                    continue

                action = await check_signal(asset, df)
                if action:
                    print(f"إشارة: {action.upper()} على {asset}")
                    # ... باقي كود الشراء ...
            await asyncio.sleep(45)
        except Exception as e:
            print(f"خطأ في اللوب: {str(e)}")
            traceback.print_exc()
            await asyncio.sleep(30)

if __name__ == "__main__":
    print("بدء تشغيل البوت...")
    asyncio.run(main_loop())
