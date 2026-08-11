# matr.py
# ============================================================
# BIST MaT-R
# TradingView MaT-R stratejisinin Python veri tarayıcısı
#
# Mantık:
#   Trend      : EMA34 / SMA34
#   MACD       : EMA/SMA 3 - EMA/SMA 5
#   Sinyal     : 2 periyot
#   AL         : MACD signal'i yukarı keser + SMA34 < EMA34
#   ATR        : 17
#   Stop       : Giriş - 2.2 * ATR
#   TP1        : +12%
#   TP2        : +20%
#
# Çıktı:
#   data.json
#
# Kurulum:
#   pip install -r requirements.txt
#
# Çalıştırma:
#   python matr.py
# ============================================================

import io
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# ============================================================
# AYARLAR
# ============================================================

SYMBOL_URL = (
    "https://raw.githubusercontent.com/"
    "ahmeterenodaci/"
    "Istanbul-Stock-Exchange--BIST--including-symbols-and-logos/"
    "main/bist.csv"
)

OUTPUT_FILE = Path("data.json")

BATCH_SIZE = 25

DOWNLOAD_PERIOD = "2y"
DOWNLOAD_INTERVAL = "1d"

# MaT-R
KUR_PER = 34

HIZLI_PER = 3
YAVAS_PER = 5
SINYAL_PER = 2

SMA_KAYNAK = False
SMA_SIGNAL = True

ATR_PERIOD = 17
STOP_MULTIPLIER = 2.2

TP1_PERCENT = 12.0
TP2_PERCENT = 20.0

MIN_HISTORY = 250


# ============================================================
# GENEL YARDIMCILAR
# ============================================================

def safe_float(value, default=0.0):
    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return default


def finite_or_none(value):
    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return None


def clean_series(series):
    return pd.to_numeric(
        series,
        errors="coerce"
    ).dropna()


# ============================================================
# HİSSELERİ AL
# ============================================================

def get_symbols():

    print("BIST sembolleri indiriliyor...")

    response = requests.get(
        SYMBOL_URL,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        io.StringIO(response.text)
    )

    if "symbol" not in df.columns:
        raise RuntimeError(
            "bist.csv içerisinde symbol sütunu bulunamadı."
        )

    if "name" not in df.columns:
        df["name"] = ""

    df["symbol"] = (
        df["symbol"]
        .astype(str)
        .str.upper()
        .str.strip()
        .str.replace(
            r"[^A-Z0-9]",
            "",
            regex=True
        )
    )

    df = df[
        df["symbol"]
        .str.len()
        .between(2, 6)
    ]

    df = df.drop_duplicates(
        subset="symbol"
    )

    symbols = dict(
        zip(
            df["symbol"],
            df["name"].fillna("")
        )
    )

    print(
        f"BIST sembol sayısı: {len(symbols)}"
    )

    return symbols


# ============================================================
# EMA
# ============================================================

def ema(series, period):

    return series.ewm(
        span=period,
        adjust=False,
        min_periods=1
    ).mean()


# ============================================================
# SMA
# ============================================================

def sma(series, period):

    return series.rolling(
        window=period,
        min_periods=period
    ).mean()


# ============================================================
# ATR
#
# Pine kodundaki özel Atr() fonksiyonunun mantığı:
#
# atr := nz(
#   atr[1] + (Tr - atr[1]) / p,
#   Tr
# )
#
# Bu Wilder tipi recursive ATR'dir.
# ============================================================

def atr_pine(high, low, close, period):

    previous_close = close.shift(1)

    tr1 = high - low

    tr2 = (
        high - previous_close
    ).abs()

    tr3 = (
        low - previous_close
    ).abs()

    true_range = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(axis=1)

    values = []

    previous_atr = None

    for tr in true_range:

        tr = safe_float(tr)

        if previous_atr is None:

            current_atr = tr

        else:

            current_atr = (
                previous_atr
                + (tr - previous_atr)
                / period
            )

        values.append(
            current_atr
        )

        previous_atr = current_atr

    return pd.Series(
        values,
        index=true_range.index,
        dtype=float
    )


# ============================================================
# MACD
# ============================================================

def calculate_macd(close):

    if SMA_KAYNAK:

        fast_ma = sma(
            close,
            HIZLI_PER
        )

        slow_ma = sma(
            close,
            YAVAS_PER
        )

    else:

        fast_ma = ema(
            close,
            HIZLI_PER
        )

        slow_ma = ema(
            close,
            YAVAS_PER
        )

    macd = (
        fast_ma
        - slow_ma
    )

    if SMA_SIGNAL:

        signal = sma(
            macd,
            SINYAL_PER
        )

    else:

        signal = ema(
            macd,
            SINYAL_PER
        )

    histogram = (
        macd
        - signal
    )

    return (
        fast_ma,
        slow_ma,
        macd,
        signal,
        histogram
    )


# ============================================================
# CROSSOVER
#
# Pine:
# ta.crossover(macd, signal)
#
# Şart:
# önce MACD <= signal
# şimdi MACD > signal
# ============================================================

def crossover(series_a, series_b):

    previous_a = series_a.shift(1)
    previous_b = series_b.shift(1)

    return (
        (previous_a <= previous_b)
        &
        (series_a > series_b)
    )


# ============================================================
# MA-TREND
# ============================================================

def calculate_trend(close):

    ema34 = ema(
        close,
        KUR_PER
    )

    sma34 = sma(
        close,
        KUR_PER
    )

    trend_condition = (
        sma34 < ema34
    )

    return (
        ema34,
        sma34,
        trend_condition
    )


# ============================================================
# MA-T-R ANA SİNYAL
# ============================================================

def calculate_strategy(data):

    close = pd.to_numeric(
        data["Close"],
        errors="coerce"
    )

    high = pd.to_numeric(
        data["High"],
        errors="coerce"
    )

    low = pd.to_numeric(
        data["Low"],
        errors="coerce"
    )

    volume = pd.to_numeric(
        data["Volume"],
        errors="coerce"
    ).fillna(0)

    frame = pd.concat(
        [
            close.rename("Close"),
            high.rename("High"),
            low.rename("Low"),
            volume.rename("Volume")
        ],
        axis=1
    )

    frame = frame.dropna(
        subset=[
            "Close",
            "High",
            "Low"
        ]
    )

    if len(frame) < MIN_HISTORY:
        return None

    close = frame["Close"]
    high = frame["High"]
    low = frame["Low"]
    volume = frame["Volume"]

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    ema34, sma34, trend_condition = (
        calculate_trend(close)
    )

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    (
        fast_ma,
        slow_ma,
        macd,
        signal,
        histogram
    ) = calculate_macd(close)

    # --------------------------------------------------------
    # CROSSOVER
    # --------------------------------------------------------

    entry_signal = (
        crossover(
            macd,
            signal
        )
        &
        trend_condition
    )

    # --------------------------------------------------------
    # ATR
    # --------------------------------------------------------

    atr_series = atr_pine(
        high,
        low,
        close,
        ATR_PERIOD
    )

    # --------------------------------------------------------
    # SON BAR
    # --------------------------------------------------------

    last = frame.index[-1]

    price = safe_float(
        close.iloc[-1]
    )

    current_ema34 = safe_float(
        ema34.iloc[-1]
    )

    current_sma34 = safe_float(
        sma34.iloc[-1]
    )

    current_fast = safe_float(
        fast_ma.iloc[-1]
    )

    current_slow = safe_float(
        slow_ma.iloc[-1]
    )

    current_macd = safe_float(
        macd.iloc[-1]
    )

    current_signal = safe_float(
        signal.iloc[-1]
    )

    current_hist = safe_float(
        histogram.iloc[-1]
    )

    current_atr = safe_float(
        atr_series.iloc[-1]
    )

    current_volume = safe_float(
        volume.iloc[-1]
    )

    # --------------------------------------------------------
    # SON AL SİNYALİ
    # --------------------------------------------------------

    buy_now = bool(
        entry_signal.iloc[-1]
    )

    # Son AL sinyalinin bulunduğu bar
    signal_positions = np.where(
        entry_signal.fillna(False).values
    )[0]

    last_entry_index = None

    if len(signal_positions):

        last_entry_index = (
            signal_positions[-1]
        )

    # --------------------------------------------------------
    # SON AL SİNYALİNE GÖRE GİRİŞ FİYATI
    # --------------------------------------------------------

    entry_price = None
    entry_date = None
    entry_atr = None
    bars_since_entry = None

    if last_entry_index is not None:

        entry_price = safe_float(
            close.iloc[last_entry_index]
        )

        entry_date = str(
            close.index[last_entry_index]
        )[:10]

        entry_atr = safe_float(
            atr_series.iloc[last_entry_index]
        )

        bars_since_entry = (
            len(close)
            - 1
            - last_entry_index
        )

    # --------------------------------------------------------
    # TP / SL
    # --------------------------------------------------------

    tp1 = None
    tp2 = None
    stop = None

    if entry_price is not None:

        tp1 = (
            entry_price
            * (1 + TP1_PERCENT / 100)
        )

        tp2 = (
            entry_price
            * (1 + TP2_PERCENT / 100)
        )

        stop = (
            entry_price
            - STOP_MULTIPLIER
            * entry_atr
        )

    # --------------------------------------------------------
    # POZİSYON DURUMU
    # --------------------------------------------------------

    position_status = "BEKLE"

    if buy_now:

        position_status = "AL"

    elif entry_price is not None:

        if price >= tp2:

            position_status = "TP2"

        elif price >= tp1:

            position_status = "TP1"

        elif (
            stop is not None
            and price <= stop
        ):

            position_status = "STOP"

        elif bars_since_entry is not None:

            position_status = "POZİSYON"

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if current_sma34 < current_ema34:

        trend = "YUKARI"

    elif current_sma34 > current_ema34:

        trend = "AŞAĞI"

    else:

        trend = "NÖTR"

    # --------------------------------------------------------
    # MACD
    # --------------------------------------------------------

    if current_macd > current_signal:

        macd_state = "POZİTİF"

    elif current_macd < current_signal:

        macd_state = "NEGATİF"

    else:

        macd_state = "NÖTR"

    # --------------------------------------------------------
    # ATR YÜZDESİ
    # --------------------------------------------------------

    atr_percent = (
        current_atr / price * 100
        if price
        else 0
    )

    # --------------------------------------------------------
    # SON 52 HAFTA
    # --------------------------------------------------------

    high_52 = safe_float(
        close.tail(252).max(),
        price
    )

    low_52 = safe_float(
        close.tail(252).min(),
        price
    )

    distance_high = (
        (price / high_52 - 1)
        * 100
        if high_52
        else 0
    )

    distance_low = (
        (price / low_52 - 1)
        * 100
        if low_52
        else 0
    )

    # --------------------------------------------------------
    # GETİRİLER
    # --------------------------------------------------------

    def return_pct(period):

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

    ret21 = return_pct(21)
    ret63 = return_pct(63)
    ret126 = return_pct(126)

    # --------------------------------------------------------
    # HACİM
    # --------------------------------------------------------

    avg_volume20 = (
        volume
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    volume_ratio = (
        current_volume
        / safe_float(
            avg_volume20,
            1
        )
    )

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    delta = close.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    rs = (
        avg_gain
        /
        avg_loss.replace(
            0,
            np.nan
        )
    )

    rsi = (
        100
        - 100 / (1 + rs)
    )

    rsi_value = safe_float(
        rsi.iloc[-1],
        50
    )

    # --------------------------------------------------------
    # ADX
    # --------------------------------------------------------

    up_move = high.diff()

    down_move = -low.diff()

    plus_dm = np.where(
        (
            (up_move > down_move)
            &
            (up_move > 0)
        ),
        up_move,
        0
    )

    minus_dm = np.where(
        (
            (down_move > up_move)
            &
            (down_move > 0)
        ),
        down_move,
        0
    )

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr14 = tr.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    plus_di = (
        100
        *
        pd.Series(
            plus_dm,
            index=close.index
        ).ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
        /
        atr14.replace(
            0,
            np.nan
        )
    )

    minus_di = (
        100
        *
        pd.Series(
            minus_dm,
            index=close.index
        ).ewm(
            alpha=1 / 14,
            adjust=False
        ).mean()
        /
        atr14.replace(
            0,
            np.nan
        )
    )

    dx = (
        100
        *
        (plus_di - minus_di).abs()
        /
        (
            plus_di + minus_di
        ).replace(
            0,
            np.nan
        )
    )

    adx_series = dx.ewm(
        alpha=1 / 14,
        adjust=False
    ).mean()

    adx_value = safe_float(
        adx_series.iloc[-1],
        20
    )

    # --------------------------------------------------------
    # MA T-R PUANI
    #
    # Bu puan sadece MaT-R sinyalinin
    # durumunu kullanıcıya kolay göstermek için.
    # Ana AL/SAT mantığını değiştirmez.
    # --------------------------------------------------------

    matr_score = 50

    if trend == "YUKARI":
        matr_score += 20
    else:
        matr_score -= 20

    if macd_state == "POZİTİF":
        matr_score += 20
    else:
        matr_score -= 20

    if current_hist > 0:
        matr_score += 10
    else:
        matr_score -= 10

    if adx_value >= 25:
        matr_score += 10

    if rsi_value >= 50:
        matr_score += 5

    if rsi_value > 75:
        matr_score -= 5

    matr_score = int(
        max(
            0,
            min(
                100,
                matr_score
            )
        )
    )

    # --------------------------------------------------------
    # GÖSTERİM SİNYALİ
    # --------------------------------------------------------

    if buy_now:

        signal_name = "AL"

    elif position_status == "STOP":

        signal_name = "STOP"

    elif position_status == "TP2":

        signal_name = "KAR AL 2"

    elif position_status == "TP1":

        signal_name = "KAR AL 1"

    elif trend == "YUKARI" and macd_state == "POZİTİF":

        signal_name = "POZİTİF"

    elif trend == "YUKARI":

        signal_name = "İZLE"

    else:

        signal_name = "BEKLE"

    # --------------------------------------------------------
    # SİNYALLER
    # --------------------------------------------------------

    signals = []

    if buy_now:
        signals.append("MA T-R AL")

    if trend == "YUKARI":
        signals.append("EMA34>SMA34")

    if macd_state == "POZİTİF":
        signals.append("MACD")

    if adx_value >= 25:
        signals.append("ADX")

    if volume_ratio >= 1.5:
        signals.append("HACİM")

    if rsi_value >= 50:
        signals.append("RSI")

    # --------------------------------------------------------
    # JSON SONUCU
    # --------------------------------------------------------

    result = {

        "code": None,
        "name": None,

        "date": str(last)[:10],

        "price": round(
            price,
            4
        ),

        "signal": signal_name,

        "matrSignal": "AL" if buy_now else "YOK",

        "matrScore": matr_score,

        "positionStatus": position_status,

        "trend": trend,

        "macdState": macd_state,

        "ema34": round(
            current_ema34,
            4
        ),

        "sma34": round(
            current_sma34,
            4
        ),

        "fastMA": round(
            current_fast,
            4
        ),

        "slowMA": round(
            current_slow,
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
            current_hist,
            6
        ),

        "atr": round(
            current_atr,
            4
        ),

        "atrPercent": round(
            atr_percent,
            2
        ),

        "rsi": round(
            rsi_value,
            2
        ),

        "adx": round(
            adx_value,
            2
        ),

        "volume": round(
            current_volume,
            0
        ),

        "volumeRatio": round(
            volume_ratio,
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

        "high52": round(
            high_52,
            4
        ),

        "low52": round(
            low_52,
            4
        ),

        "distance52High": round(
            distance_high,
            2
        ),

        "distance52Low": round(
            distance_low,
            2
        ),

        "entryPrice": (
            round(
                entry_price,
                4
            )
            if entry_price is not None
            else None
        ),

        "entryDate": entry_date,

        "entryATR": (
            round(
                entry_atr,
                4
            )
            if entry_atr is not None
            else None
        ),

        "barsSinceEntry": bars_since_entry,

        "tp1": (
            round(
                tp1,
                4
            )
            if tp1 is not None
            else None
        ),

        "tp2": (
            round(
                tp2,
                4
            )
            if tp2 is not None
            else None
        ),

        "stop": (
            round(
                stop,
                4
            )
            if stop is not None
            else None
        ),

        "tp1Percent": TP1_PERCENT,

        "tp2Percent": TP2_PERCENT,

        "stopMultiplier": STOP_MULTIPLIER,

        "atrPeriod": ATR_PERIOD,

        "signals": signals
    }

    return result


# ============================================================
# DATAFRAME DÜZELT
# ============================================================

def extract_ticker_data(raw, symbol):

    if raw is None or raw.empty:
        return None

    ticker = symbol + ".IS"

    try:

        if isinstance(
            raw.columns,
            pd.MultiIndex
        ):

            level0 = (
                raw.columns
                .get_level_values(0)
            )

            level1 = (
                raw.columns
                .get_level_values(1)
            )

            if ticker in level0:

                return raw[
                    ticker
                ].copy()

            if ticker in level1:

                return raw.xs(
                    ticker,
                    axis=1,
                    level=1
                ).copy()

        else:

            return raw.copy()

    except Exception as exc:

        print(
            f"{symbol} veri ayıklama hatası:",
            exc
        )

    return None


# ============================================================
# TEK HİSSE
# ============================================================

def process_stock(symbol, name, data):

    try:

        result = calculate_strategy(
            data
        )

        if result is None:
            return None

        result["code"] = symbol
        result["name"] = (
            str(name)
            if name is not None
            else ""
        )

        return result

    except Exception as exc:

        print(
            f"SKIP {symbol}: {exc}"
        )

        return None


# ============================================================
# JSON TEMİZLE
# ============================================================

def clean_json_value(value):

    if isinstance(
        value,
        dict
    ):

        return {
            key: clean_json_value(val)
            for key, val in value.items()
        }

    if isinstance(
        value,
        list
    ):

        return [
            clean_json_value(x)
            for x in value
        ]

    if isinstance(
        value,
        float
    ):

        if math.isfinite(value):
            return value

        return None

    if isinstance(
        value,
        np.floating
    ):

        value = float(value)

        if math.isfinite(value):
            return value

        return None

    if isinstance(
        value,
        np.integer
    ):

        return int(value)

    return value


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    print()
    print("=" * 60)
    print("BIST MaT-R TARAYICI")
    print("=" * 60)
    print()

    symbols = get_symbols()

    symbol_list = list(
        symbols.keys()
    )

    results = []

    failed = []

    total = len(
        symbol_list
    )

    # --------------------------------------------------------
    # BATCH
    # --------------------------------------------------------

    for start in range(
        0,
        total,
        BATCH_SIZE
    ):

        batch = symbol_list[
            start:
            start + BATCH_SIZE
        ]

        end = min(
            start + BATCH_SIZE,
            total
        )

        print()
        print(
            f"[{start + 1}-{end}/{total}] "
            f"veri indiriliyor..."
        )

        tickers = [
            symbol + ".IS"
            for symbol in batch
        ]

        try:

            raw = yf.download(
                tickers,
                period=DOWNLOAD_PERIOD,
                interval=DOWNLOAD_INTERVAL,
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=60
            )

        except Exception as exc:

            print(
                "BATCH ERROR:",
                exc
            )

            for symbol in batch:
                failed.append(symbol)

            continue

        # ----------------------------------------------------
        # HİSSELER
        # ----------------------------------------------------

        for symbol in batch:

            try:

                data = extract_ticker_data(
                    raw,
                    symbol
                )

                if data is None:

                    failed.append(
                        symbol
                    )

                    continue

                result = process_stock(
                    symbol,
                    symbols[symbol],
                    data
                )

                if result is None:

                    failed.append(
                        symbol
                    )

                else:

                    results.append(
                        result
                    )

            except Exception as exc:

                print(
                    "HATA",
                    symbol,
                    exc
                )

                failed.append(
                    symbol
                )

        time.sleep(1)

    # --------------------------------------------------------
    # SIRALAMA
    #
    # Önce gerçek AL sinyalleri,
    # sonra MaT-R puanı.
    # --------------------------------------------------------

    results.sort(
        key=lambda x: (
            x["matrSignal"] == "AL",
            x["matrScore"]
        ),
        reverse=True
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    cleaned = clean_json_value(
        results
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            cleaned,
            file,
            ensure_ascii=False,
            allow_nan=False,
            separators=(
                ",",
                ":"
            )
        )

    # --------------------------------------------------------
    # ÖZET
    # --------------------------------------------------------

    buy_list = [
        x
        for x in results
        if x["matrSignal"] == "AL"
    ]

    tp1_list = [
        x
        for x in results
        if x["positionStatus"] == "TP1"
    ]

    tp2_list = [
        x
        for x in results
        if x["positionStatus"] == "TP2"
    ]

    stop_list = [
        x
        for x in results
        if x["positionStatus"] == "STOP"
    ]

    print()
    print("=" * 60)
    print("TARAMA TAMAMLANDI")
    print("=" * 60)

    print(
        "Başarılı hisse:",
        len(results)
    )

    print(
        "Veri alınamayan:",
        len(failed)
    )

    print(
        "MaT-R AL:",
        len(buy_list)
    )

    print(
        "TP1:",
        len(tp1_list)
    )

    print(
        "TP2:",
        len(tp2_list)
    )

    print(
        "STOP:",
        len(stop_list)
    )

    print(
        "JSON:",
        OUTPUT_FILE
    )

    # --------------------------------------------------------
    # AL SİNYALLERİ
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("MaT-R AL SİNYALLERİ")
    print("=" * 60)

    if not buy_list:

        print(
            "Bugün yeni MaT-R AL sinyali yok."
        )

    else:

        for i, stock in enumerate(
            buy_list,
            1
        ):

            print(
                f"{i:>3}. "
                f"{stock['code']:<8} "
                f"Fiyat={stock['price']:<10} "
                f"Skor={stock['matrScore']:<3} "
                f"ATR={stock['atr']}"
            )

    # --------------------------------------------------------
    # EN GÜÇLÜ 20
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("EN GÜÇLÜ 20 MaT-R")
    print("=" * 60)

    top20 = sorted(
        results,
        key=lambda x: x["matrScore"],
        reverse=True
    )[:20]

    for i, stock in enumerate(
        top20,
        1
    ):

        print(
            f"{i:>3}. "
            f"{stock['code']:<8} "
            f"{stock['matrScore']:>3} "
            f"{stock['signal']}"
        )

    # --------------------------------------------------------
    # 400 HİSSE KONTROLÜ
    # --------------------------------------------------------

    if len(results) < 400:

        raise RuntimeError(
            "Çok az hisse üretildi: "
            f"{len(results)}. "
            "Yahoo Finance veri kaynağını veya "
            "sembol listesini kontrol et."
        )


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":
    main()
