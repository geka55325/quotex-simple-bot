import os
import asyncio
import traceback
import pandas as pd
from datetime import datetime, timedelta

from ta.momentum import RSIIndicator
from ta.trend import MACD

from quotexpy import Quotex

# =========================
# CONFIG
# =========================

EMAIL = os.environ.get("QUOTEX_EMAIL")
PASSWORD = os.environ.get("QUOTEX_PASSWORD")

ACCOUNT_TYPE = "PRACTICE"

ASSETS = [
    "EURUSD",
    "GBPUSD",
    "GOLD"
]

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

    rsi = RSIIndicator(close=df["close"], window=14).rsi()

    macd_obj = MACD(close=df["close"])

    macd = macd_obj.macd()
    signal = macd_obj.macd_signal()

    df["rsi"] = rsi
    df["macd"] = macd
    df["signal"] = signal

    last = df.iloc[-1]
    prev = df.iloc[-2]

    rsi_value = last["rsi"]

    macd_cross_up = prev["macd"] < prev["signal"] and last["macd"] > last["signal"]
    macd_cross_down = prev["macd"] > prev["signal"] and last["macd"] < last["signal"]

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

    return False


# =========================
# GET CANDLES
# =========================

async def get_candles(client, asset):

    try:

        end = int(datetime.now().timestamp())

        candles = await client.get_candles(
            asset,
            TIMEFRAME,
            CANDLE_COUNT,
            end
        )

        df = pd.DataFrame(candles)

        df.rename(columns={
            "open": "open",
            "close": "close",
            "max": "high",
            "min": "low"
        }, inplace=True)

        return df

    except Exception as e:

        log(f"CANDLE ERROR {asset}: {e}")

        return None


# =========================
# OPEN TRADE
# =========================

async def open_trade(client, asset, direction):

    try:

        log(f"OPEN TRADE {asset} {direction} amount={TRADE_AMOUNT}")

        status, trade = await client.trade(
            direction,
            TRADE_AMOUNT,
            asset,
            EXPIRY
        )

        if status:
            log(f"TRADE OPENED ID={trade}")
            cooldowns[asset] = datetime.now()
        else:
            log("TRADE FAILED")

    except Exception as e:

        log(f"TRADE ERROR {e}")


# =========================
# ANALYZE ASSET
# =========================

async def process_asset(client, asset):

    if not can_trade(asset):

        log(f"{asset} cooldown active")

        return

    df = await get_candles(client, asset)

    if df is None or len(df) < 50:
        return

    signal, rsi_value = analyze_signal(df)

    log(f"{asset} RSI={round(rsi_value,2)} SIGNAL={signal}")

    if signal:

        await open_trade(client, asset, signal)


# =========================
# MAIN LOOP
# =========================

async def main_loop(client):

    while True:

        try:

            for asset in ASSETS:

                await process_asset(client, asset)

            await asyncio.sleep(10)

        except Exception:

            traceback.print_exc()

            await asyncio.sleep(5)


# =========================
# CONNECT
# =========================

async def connect():

    while True:

        try:

            log("CONNECTING TO QUOTEX...")

            client = Quotex(
                email=EMAIL,
                password=PASSWORD
            )

            await client.connect()

            log("CONNECTED")

            await client.change_account(ACCOUNT_TYPE)

            log("ACCOUNT MODE: PRACTICE")

            return client

        except Exception:

            traceback.print_exc()

            log("RETRY CONNECT IN 5s")

            await asyncio.sleep(5)


# =========================
# ENTRY
# =========================

async def main():

    client = await connect()

    await main_loop(client)


if __name__ == "__main__":

    asyncio.run(main())
