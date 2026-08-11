import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# =========================================================
# MATR BIST RADAR
# Pine Script MATR mantığının Python karşılığı
# =========================================================

SYMBOL_URL = (
    "https://raw.githubusercontent.com/ahmeterenodaci/"
    "Istanbul-Stock-Exchange--BIST--including-symbols-and-logos/"
    "main/bist.csv"
)

OUTPUT_FILE = "data.json"

BATCH_SIZE = 20

# MATR ayarları
TREND_PERIOD = 34

MACD_FAST = 3
MACD_SLOW = 5
MACD_SIGNAL = 2

ATR_PERIOD = 17
ATR_MULTIPLIER = 2.2

TP1_PERCENT = 12.0
TP2_PERCENT = 20.0

HISTORY_PERIOD = "2y"
INTERVAL = "1d"


# =========================================================
# YARDIMCI
# =========================================================

def safe_float(value, default=0.0):
    try:
        value = float(value)

        if np.isfinite(value):
            return value

    except Exception:
        pass

    return default


def finite_or_none(value):
    try:
        value = float(value)

        if np.isfinite(value):
            return value

    except Exception:
        pass

    return None


# =========================================================
# EMA
# =========================================================

def ema(series, period):
    """
    Pine'daki EMA davranışına yakın hesaplama.
    """

    return series.ewm(
        span=period,
        adjust=False,
        min_periods=1
    ).mean()


# =========================================================
# SMA
# =========================================================

def sma(series, period):

    return series.rolling(
        period,
        min_periods=period
    ).mean()


# =========================================================
# ATR
# =========================================================

def atr(high, low, close, period=17):
    """
    Pine kodundaki özel ATR hesabı:

    Tr =
        max(
            high-low,
            abs(high-close[1]),
            abs(low-close[1])
        )

    ATR =
        ATR[1] + (TR-ATR[1])/period
    """

    previous_close = close.shift(1)

    tr1 = high - low

    tr2 = (high - previous_close).abs()

    tr3 = (low - previous_close).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    result = np.zeros(len(tr))

    values = tr.to_numpy(dtype=float)

    if len(values) == 0:
        return pd.Series(
            dtype=float,
            index=tr.index
        )

    result[0] = values[0]

    for i in range(1, len(values)):

        current = values[i]

        previous = result[i - 1]

        result[i] = (
            previous
            + (current - previous) / period
        )

    return pd.Series(
        result,
        index=tr.index
    )


# =========================================================
# HİSSELERİ AL
# =========================================================

def get_symbols():

    print("BIST sembolleri indiriliyor...")

    response = requests.get(
        SYMBOL_URL,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        pd.io.common.StringIO(response.text)
    )

    columns = {
        str(c).lower(): c
        for c in df.columns
    }

    symbol_column = columns.get("symbol")

    if symbol_column is None:
        raise RuntimeError(
            "bist.csv içerisinde symbol sütunu bulunamadı."
        )

    name_column = (
        columns.get("name")
        or columns.get("company")
    )

    df["symbol"] = (
        df[symbol_column]
        .astype(str)
        .str.upper()
        .str.strip()
        .str.replace(
            r"[^A-Z0-9]",
            "",
            regex=True
        )
    )

    if name_column:
        df["company_name"] = (
            df[name_column]
            .astype(str)
            .str.strip()
        )
    else:
        df["company_name"] = ""

    df = df[
        df["symbol"].str.len().between(2, 6)
    ]

    df = df.drop_duplicates(
        subset="symbol"
    )

    symbols = dict(
        zip(
            df["symbol"],
            df["company_name"]
        )
    )

    print(
        f"BIST sembol sayısı: {len(symbols)}"
    )

    return symbols


# =========================================================
# YAHOO VERİSİNİ DÜZELT
# =========================================================

def normalize_dataframe(df):

    if df is None or df.empty:
        return None

    result = df.copy()

    # MultiIndex varsa düzelt
    if isinstance(
        result.columns,
        pd.MultiIndex
    ):

        result.columns = [
            str(x[0])
            for x in result.columns
        ]

    required = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    ]

    for column in required:

        if column not in result.columns:
            return None

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce"
        )

    result = result.dropna(
        subset=[
            "High",
            "Low",
            "Close"
        ]
    )

    return result


# =========================================================
# TEK HİSSE VERİSİ
# =========================================================

def get_stock_data(symbol):

    ticker = symbol + ".IS"

    try:

        data = yf.download(
            ticker,
            period=HISTORY_PERIOD,
            interval=INTERVAL,
            auto_adjust=True,
            progress=False,
            threads=False
        )

        data = normalize_dataframe(data)

        if data is None:
            return None

        if len(data) < 250:
            return None

        return data

    except Exception as error:

        print(
            f"{symbol}: veri alınamadı -> {error}"
        )

        return None


# =========================================================
# MATR HESAPLA
# =========================================================

def calculate_matr(symbol, name, data):

    if data is None or len(data) < 250:
        return None

    close = data["Close"]
    high = data["High"]
    low = data["Low"]

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    trend_ema = ema(
        close,
        TREND_PERIOD
    )

    trend_sma = sma(
        close,
        TREND_PERIOD
    )

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    fast_ma = ema(
        close,
        MACD_FAST
    )

    slow_ma = ema(
        close,
        MACD_SLOW
    )

    macd = fast_ma - slow_ma

    signal = sma(
        macd,
        MACD_SIGNAL
    )

    histogram = macd - signal

    # -----------------------------------------------------
    # ATR
    # -----------------------------------------------------

    atr_series = atr(
        high,
        low,
        close,
        ATR_PERIOD
    )

    # -----------------------------------------------------
    # AL SİNYALİ
    #
    # Pine:
    #
    # entry_long =
    # crossover(macd, signal)
    # and oncu2 < oncu1
    # -----------------------------------------------------

    macd_previous = macd.shift(1)

    signal_previous = signal.shift(1)

    crossover = (
        (macd_previous <= signal_previous)
        &
        (macd > signal)
    )

    trend_condition = (
        trend_sma < trend_ema
    )

    entry_signal = (
        crossover
        &
        trend_condition
    )

    # -----------------------------------------------------
    # SON DEĞERLER
    # -----------------------------------------------------

    last = data.iloc[-1]

    price = safe_float(
        close.iloc[-1]
    )

    current_ema34 = safe_float(
        trend_ema.iloc[-1]
    )

    current_sma34 = safe_float(
        trend_sma.iloc[-1]
    )

    current_macd = safe_float(
        macd.iloc[-1]
    )

    current_signal = safe_float(
        signal.iloc[-1]
    )

    current_histogram = safe_float(
        histogram.iloc[-1]
    )

    current_atr = safe_float(
        atr_series.iloc[-1]
    )

    buy_signal = bool(
        entry_signal.iloc[-1]
    )

    # -----------------------------------------------------
    # SON AL SİNYALİNİ BUL
    # -----------------------------------------------------

    signal_positions = np.where(
        entry_signal.fillna(False).to_numpy()
    )[0]

    last_entry_index = None

    if len(signal_positions):

        last_entry_index = int(
            signal_positions[-1]
        )

    # -----------------------------------------------------
    # POZİSYON BİLGİSİ
    # -----------------------------------------------------

    entry_price = None

    stop_price = None

    tp1_price = None

    tp2_price = None

    position_active = False

    entry_date = None

    # -----------------------------------------------------
    # SON AL SİNYALİNDEN SONRA
    # ZARAR KES / KAR AL
    # -----------------------------------------------------

    if last_entry_index is not None:

        entry_price = safe_float(
            close.iloc[last_entry_index]
        )

        entry_atr = safe_float(
            atr_series.iloc[last_entry_index]
        )

        stop_price = (
            entry_price
            - ATR_MULTIPLIER * entry_atr
        )

        tp1_price = (
            entry_price
            * (1 + TP1_PERCENT / 100)
        )

        tp2_price = (
            entry_price
            * (1 + TP2_PERCENT / 100)
        )

        entry_date = str(
            data.index[last_entry_index].date()
        )

        # Sonraki günlerde çıkış olmuş mu?
        position_active = True

        for i in range(
            last_entry_index + 1,
            len(data)
        ):

            day_low = safe_float(
                low.iloc[i]
            )

            day_high = safe_float(
                high.iloc[i]
            )

            day_close = safe_float(
                close.iloc[i]
            )

            # Önce stop kontrolü
            if day_close < (
                entry_price
                - ATR_MULTIPLIER
                * safe_float(atr_series.iloc[i])
            ):

                position_active = False
                break

            # TP2'ye ulaşmışsa strateji hâlâ
            # pozisyonun kalan kısmını taşıyabilir.
            #
            # Burada yalnızca aktiflik takibi yapıyoruz.
            if day_high >= tp2_price:

                # Pozisyonun %15'i TP2
                # seviyesinde satılır.
                #
                # Kalan pozisyon devam eder.
                pass

            if day_high >= tp1_price:

                # Pozisyonun %10'u TP1
                # seviyesinde satılır.
                pass

    # -----------------------------------------------------
    # SİNYAL DURUMU
    # -----------------------------------------------------

    if buy_signal:

        status = "AL"

    elif position_active:

        status = "POZİSYON"

    else:

        status = "BEKLE"

    # -----------------------------------------------------
    # TREND
    # -----------------------------------------------------

    if current_sma34 < current_ema34:

        trend = "YUKARI"

    else:

        trend = "ZAYIF"

    # -----------------------------------------------------
    # MACD
    # -----------------------------------------------------

    if current_macd > current_signal:

        macd_status = "POZİTİF"

    else:

        macd_status = "NEGATİF"

    # -----------------------------------------------------
    # ATR STOP MESAFESİ
    # -----------------------------------------------------

    stop_distance_percent = 0

    if price > 0:

        stop_distance_percent = (
            (price - (
                price
                - ATR_MULTIPLIER
                * current_atr
            ))
            / price
        ) * 100

    # -----------------------------------------------------
    # 21 / 63 / 126 GÜNLÜK GETİRİ
    # -----------------------------------------------------

    def return_percent(period):

        if len(close) <= period:
            return 0

        old = safe_float(
            close.iloc[-period - 1]
        )

        if old == 0:
            return 0

        return (
            price / old - 1
        ) * 100

    ret21 = return_percent(21)

    ret63 = return_percent(63)

    ret126 = return_percent(126)

    # -----------------------------------------------------
    # BASİT MATR PUANI
    #
    # Bu puan eski sistemin puanı değildir.
    # Sadece MATR koşullarının durumunu özetler.
    # -----------------------------------------------------

    matr_score = 0

    if trend_condition.iloc[-1]:
        matr_score += 40

    if current_macd > current_signal:
        matr_score += 30

    if current_histogram > 0:
        matr_score += 15

    if buy_signal:
        matr_score += 15

    matr_score = min(
        100,
        max(
            0,
            matr_score
        )
    )

    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    return {

        "code": symbol,

        "name": name,

        "price": round(
            price,
            2
        ),

        "status": status,

        "signal": (
            "AL"
            if buy_signal
            else "BEKLE"
        ),

        "trend": trend,

        "macdStatus": macd_status,

        "matrScore": int(
            matr_score
        ),

        "ema34": round(
            current_ema34,
            4
        ),

        "sma34": round(
            current_sma34,
            4
        ),

        "macd": round(
            current_macd,
            6
        ),

        "macdSignal": round(
            current_signal,
            6
        ),

        "histogram": round(
            current_histogram,
            6
        ),

        "atr": round(
            current_atr,
            4
        ),

        "entryPrice": (
            round(entry_price, 2)
            if entry_price is not None
            else None
        ),

        "stopPrice": (
            round(stop_price, 2)
            if stop_price is not None
            else None
        ),

        "tp1Price": (
            round(tp1_price, 2)
            if tp1_price is not None
            else None
        ),

        "tp2Price": (
            round(tp2_price, 2)
            if tp2_price is not None
            else None
        ),

        "entryDate": entry_date,

        "positionActive": bool(
            position_active
        ),

        "stopDistancePercent": round(
            stop_distance_percent,
            2
        ),

        "ret21": round(
            ret21,
            2
        ),

        "ret63": round(
            ret63,
            2
        ),

        "ret126": round(
            ret126,
            2
        ),

        "parameters": {

            "trendPeriod": TREND_PERIOD,

            "macdFast": MACD_FAST,

            "macdSlow": MACD_SLOW,

            "macdSignal": MACD_SIGNAL,

            "atrPeriod": ATR_PERIOD,

            "atrMultiplier": ATR_MULTIPLIER,

            "tp1Percent": TP1_PERCENT,

            "tp2Percent": TP2_PERCENT

        }

    }


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    start_time = time.time()

    print()
    print("=" * 60)
    print("MATR BIST RADAR")
    print("=" * 60)
    print()

    symbols = get_symbols()

    symbol_list = list(symbols.keys())

    results = []

    failed = []

    total = len(symbol_list)

    for index, symbol in enumerate(
        symbol_list,
        start=1
    ):

        print(
            f"[{index}/{total}] {symbol}",
            end=" "
        )

        try:

            data = get_stock_data(
                symbol
            )

            if data is None:

                print("VERİ YOK")

                failed.append(symbol)

                continue

            result = calculate_matr(
                symbol,
                symbols[symbol],
                data
            )

            if result is None:

                print("HESAPLANAMADI")

                failed.append(symbol)

                continue

            results.append(result)

            print(
                f"{result['status']} "
                f"Skor:{result['matrScore']}"
            )

        except Exception as error:

            print(
                f"HATA: {error}"
            )

            failed.append(symbol)

    # -----------------------------------------------------
    # SIRALAMA
    # -----------------------------------------------------

    results.sort(
        key=lambda x: (
            x["signal"] == "AL",
            x["matrScore"]
        ),
        reverse=True
    )

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    output = Path(
        OUTPUT_FILE
    )

    with output.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            ensure_ascii=False,
            allow_nan=False,
            indent=2
        )

    # -----------------------------------------------------
    # ÖZET
    # -----------------------------------------------------

    buy_count = sum(
        x["signal"] == "AL"
        for x in results
    )

    active_count = sum(
        x["positionActive"]
        for x in results
    )

    print()
    print("=" * 60)
    print("MATR TAMAMLANDI")
    print("=" * 60)

    print(
        f"Toplam sembol : {total}"
    )

    print(
        f"Başarılı      : {len(results)}"
    )

    print(
        f"Veri/Hata     : {len(failed)}"
    )

    print(
        f"AL sinyali    : {buy_count}"
    )

    print(
        f"Aktif pozisyon: {active_count}"
    )

    print(
        f"Dosya         : {OUTPUT_FILE}"
    )

    print(
        f"Süre          : "
        f"{time.time() - start_time:.1f} sn"
    )

    print("=" * 60)

    print()
    print("MATR AL SİNYALLERİ")
    print("-" * 60)

    for item in results:

        if item["signal"] == "AL":

            print(
                item["code"],
                "|",
                item["price"],
                "|",
                "Giriş:",
                item["entryPrice"],
                "|",
                "SL:",
                item["stopPrice"],
                "|",
                "TP1:",
                item["tp1Price"],
                "|",
                "TP2:",
                item["tp2Price"]
            )


if __name__ == "__main__":
    main()
