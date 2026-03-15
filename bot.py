import os
import asyncio
import traceback
import pandas as pd
from datetime import datetime, timedelta

from ta.momentum import RSIIndicator
from ta.trend import MACD

from pyquotex import Quotex   # ← تأكد من الـ import الصحيح (pyquotex مش quotexpy)

# ──────────────── إصلاح مسارات المتصفح على Render ────────────────
os.environ["CHROME_EXECUTABLE_PATH"] = "/usr/bin/chromium-browser"
os.environ["CHROMEDRIVER_EXECUTABLE_PATH"] = "/usr/bin/chromedriver"

# =========================
# CONFIG
# =========================

EMAIL = os.environ.get("QUOTEX_EMAIL")
PASSWORD = os.environ.get("QUOTEX_PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("QUOTEX_EMAIL أو QUOTEX_PASSWORD غير موجودين في Environment Variables")

ACCOUNT_TYPE = "PRACTICE"

ASSETS = ["EURUSD", "GBPUSD", "GOLD"]

TIMEFRAME = 60
EXPIRY = 60
TRADE_AMOUNT = 500

COOLDOWN_SECONDS = 300
CANDLE_COUNT = 120

cooldowns = {}


# =========================
# LOGGER
# =========================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =========================
# INDICATORS
# =========================

def analyze_signal(df):
    if "close" not in df.columns:
        log("خطأ: لا يوجد عمود 'close' في البيانات")
        return None, None

    rsi = RSIIndicator(close=df["close"], window=14).rsi()
    macd_obj = MACD(close=df["close"])
    macd = macd_obj.macd()
    signal = macd_obj.macd_signal()

    df["rsi"] = rsi
    df["macd"] = macd
    df["signal"] = signal

    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_value = last.get("rsi")
    macd_cross_up = (prev.get("macd") < prev.get("signal")) and (last.get("macd") > last.get("signal"))
    macd_cross_down = (prev.get("macd") > prev.get("signal")) and (last.get("macd") < last.get("signal"))

    if rsi_value is not None:
        if rsi_value < 40 and macd_cross_up:
            return "call", rsi_value
        if rsi_value > 60 and macd_cross_down:
            return "put", rsi_value

    return None, rsi_value


# =========================
# COOLDOWN
# =========================

def can_trade(asset):
    if asset not in cooldowns:
        return True

    last_trade = cooldowns[asset]
    if datetime.now() - last_trade > timedelta(seconds=COOLDOWN_SECONDS):
        return True

    log(f"{asset} في cooldown حتى {(last_trade + timedelta(seconds=COOLDOWN_SECONDS)).strftime('%H:%M:%S')}")
    return False


# =========================
# GET CANDLES
# =========================

async def get_candles(client, asset):
    try:
        end = int(datetime.now().timestamp())
        log(f"جاري جلب {CANDLE_COUNT} كاندل لـ {asset} ...")

        # بعض الإصدارات من pyquotex مش async
        try:
            candles = await client.get_candles(asset, TIMEFRAME, CANDLE_COUNT, end)
        except TypeError:
            # لو مش async، نجرب بدون await
            candles = client.get_candles(asset, TIMEFRAME, CANDLE_COUNT, end)

        if not candles:
            log(f"لا كاندلز مرجعة لـ {asset}")
            return None

        df = pd.DataFrame(candles)

        log(f"أعمدة البيانات لـ {asset}: {list(df.columns)}")

        df.rename(columns={
            "open": "open",
            "close": "close",
            "max": "high",
            "min": "low"
        }, inplace=True)

        if len(df) < 20:
            log(f"عدد الكاندلز قليل جدًا ({len(df)}) لـ {asset}")
            return None

        return df

    except Exception as e:
        log(f"CANDLE ERROR {asset}: {str(e)}")
        traceback.print_exc()
        return None


# =========================
# OPEN TRADE
# =========================

async def open_trade(client, asset, direction):
    try:
        log(f"فتح صفقة {asset} {direction.upper()} بـ ${TRADE_AMOUNT}")

        # بعض الإصدارات مش async
        try:
            status, trade = await client.trade(direction, TRADE_AMOUNT, asset, EXPIRY)
        except TypeError:
            status, trade = client.trade(direction, TRADE_AMOUNT, asset, EXPIRY)

        if status:
            log(f"تم فتح الصفقة! ID = {trade}")
            cooldowns[asset] = datetime.now()
        else:
            log("فشل فتح الصفقة")

    except Exception as e:
        log(f"TRADE ERROR {asset}: {str(e)}")
        traceback.print_exc()


# =========================
# ANALYZE ASSET
# =========================

async def process_asset(client, asset):
    if not can_trade(asset):
        return

    df = await get_candles(client, asset)
    if df is None or len(df) < 50:
        return

    signal, rsi_value = analyze_signal(df)

    if rsi_value is not None:
        log(f"{asset} → RSI: {round(rsi_value, 2)} | SIGNAL: {signal}")
    else:
        log(f"{asset} → لا إشارة (مشكلة في الحسابات)")

    if signal:
        await open_trade(client, asset, signal)


# =========================
# MAIN LOOP
# =========================

async def main_loop(client):
    log("بدء الحلقة الرئيسية - فحص كل 10 ثوانٍ")
    while True:
        try:
            for asset in ASSETS:
                await process_asset(client, asset)
            await asyncio.sleep(10)
        except Exception as e:
            log(f"خطأ في الحلقة الرئيسية: {str(e)}")
            traceback.print_exc()
            await asyncio.sleep(5)


# =========================
# CONNECT WITH TIMEOUT
# =========================

async def connect():
    max_attempts = 10
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        try:
            log(f"محاولة اتصال رقم {attempt}/{max_attempts}")

            client = Quotex(email=EMAIL, password=PASSWORD)

            log("جاري الاتصال...")
            await client.connect()

            log("تم الاتصال بنجاح!")

            log("جاري تغيير نوع الحساب...")
            await client.change_account(ACCOUNT_TYPE)

            log(f"الحساب الآن: {ACCOUNT_TYPE}")
            return client

        except Exception as e:
            log(f"فشل الاتصال في المحاولة {attempt}: {str(e)}")
            traceback.print_exc()
            await asyncio.sleep(5)

    raise ConnectionError(f"فشل الاتصال بعد {max_attempts} محاولة")


# =========================
# ENTRY POINT
# =========================

async def main():
    log("تشغيل البوت...")
    try:
        client = await connect()
        await main_loop(client)
    except Exception as e:
        log(f"خطأ كبير في التشغيل: {str(e)}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
