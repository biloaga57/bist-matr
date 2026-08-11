import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# =========================================================
# BIST MaT-R RADAR
# TradingView MaT-R mantığının Python veri motoru
# =========================================================

SYMBOL_URL = (
    "https://raw.githubusercontent.com/ahmeterenodaci/"
    "Istanbul-Stock-Exchange--BIST--including-symbols-and-logos/"
    "main/bist.csv"
)

BATCH_SIZE = 25

OUTPUT_FILE = Path("data.json")


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


def clamp(value, low=0, high=100):
    return int(max(low, min(high, safe_float(value))))


# =========================================================
# HİSSE LİSTESİ
# =========================================================

def get_symbols():

    response = requests.get(
        SYMBOL_URL,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        io.StringIO(response.text)
    )

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
        df["symbol"].str.len().between(2, 6)
    ]

    df = df.drop_duplicates(
        "symbol"
    )

    return dict(
        zip(
            df["symbol"],
            df["name"]
        )
    )


# =========================================================
# MA-T-R EMA
# =========================================================

def ema(series, period):

    return series.ewm(
        span=period,
        adjust=False
    ).mean()


# =========================================================
# SMA
# =========================================================

def sma(series, period):

    return series.rolling(
        period
    ).mean()


# =========================================================
# ATR
# TradingView kodundaki özel ATR mantığına yakın
# =========================================================

def mat_r_atr(high, low, close, period=17):

    previous_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs()
        ],
        axis=1
    ).max(axis=1)

    atr_values = []

    previous_atr = np.nan

    for value in tr:

        value = safe_float(value)

        if np.isnan(previous_atr):

            current = value

        else:

            current = (
                previous_atr
                + (value - previous_atr) / period
            )

        atr_values.append(current)

        previous_atr = current

    return pd.Series(
        atr_values,
        index=close.index
    )


# =========================================================
# RSI
# =========================================================

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(
        lower=0
    )

    loss = -delta.clip(
        upper=0
    )

    avg_gain = gain.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    rs = (
        avg_gain /
        avg_loss.replace(0, np.nan)
    )

    result = (
        100 -
        100 / (1 + rs)
    )

    return result.fillna(50)


# =========================================================
# MA-T-R ANALİZİ
# =========================================================

def analyze_stock(symbol, name, data):

    if data is None or data.empty:
        return None

    required = {
        "Open",
        "High",
        "Low",
        "Close",
        "Volume"
    }

    if not required.issubset(
        data.columns
    ):
        return None

    df = data.copy()

    for column in required:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "High",
            "Low",
            "Close"
        ]
    )

    if len(df) < 250:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"].fillna(0)

    # -----------------------------------------------------
    # MaT-R TRENDLER
    # -----------------------------------------------------

    period = 34

    trend_ema = ema(
        close,
        period
    )

    trend_sma = sma(
        close,
        period
    )

    # -----------------------------------------------------
    # MaT-R MACD
    #
    # Kısa = 3
    # Uzun = 5
    # Sinyal = 2
    # -----------------------------------------------------

    fast = ema(
        close,
        3
    )

    slow = ema(
        close,
        5
    )

    macd = fast - slow

    signal = ema(
        macd,
        2
    )

    histogram = macd - signal

    # -----------------------------------------------------
    # ATR
    # -----------------------------------------------------

    atr = mat_r_atr(
        high,
        low,
        close,
        17
    )

    # -----------------------------------------------------
    # RSI
    # -----------------------------------------------------

    rsi_series = rsi(
        close,
        14
    )

    # -----------------------------------------------------
    # SON DEĞERLER
    # -----------------------------------------------------

    price = safe_float(
        close.iloc[-1]
    )

    ema34 = safe_float(
        trend_ema.iloc[-1]
    )

    sma34 = safe_float(
        trend_sma.iloc[-1]
    )

    macd_now = safe_float(
        macd.iloc[-1]
    )

    signal_now = safe_float(
        signal.iloc[-1]
    )

    histogram_now = safe_float(
        histogram.iloc[-1]
    )

    atr_now = safe_float(
        atr.iloc[-1]
    )

    rsi_now = safe_float(
        rsi_series.iloc[-1]
    )

    # -----------------------------------------------------
    # MaT-R AL SİNYALİ
    #
    # TradingView:
    #
    # crossover(macd, signal)
    # AND
    # sma34 < ema34
    # -----------------------------------------------------

    macd_cross = False

    if len(macd) >= 2:

        macd_cross = (
            macd.iloc[-2]
            <= signal.iloc[-2]
            and
            macd.iloc[-1]
            >
            signal.iloc[-1]
        )

    trend_positive = (
        sma34 < ema34
    )

    entry_signal = (
        macd_cross
        and
        trend_positive
    )

    # -----------------------------------------------------
    # TREND DURUMU
    # -----------------------------------------------------

    if price > ema34 and ema34 > sma34:

        trend = "GÜÇLÜ YÜKSELİŞ"

    elif price > ema34:

        trend = "YÜKSELİŞ"

    elif price < ema34 and ema34 < sma34:

        trend = "GÜÇLÜ DÜŞÜŞ"

    else:

        trend = "NÖTR"

    # -----------------------------------------------------
    # KAR AL SEVİYELERİ
    #
    # MaT-R:
    # %12
    # %20
    # -----------------------------------------------------

    tp1 = price * 1.12
    tp2 = price * 1.20

    # -----------------------------------------------------
    # ZARAR KES
    #
    # ATR17 × 2.2
    # -----------------------------------------------------

    stop = price - (
        2.2 * atr_now
    )

    # -----------------------------------------------------
    # STOP MESAFESİ
    # -----------------------------------------------------

    stop_percent = 0

    if price > 0:

        stop_percent = (
            (stop / price) - 1
        ) * 100

    # -----------------------------------------------------
    # HACİM
    # -----------------------------------------------------

    volume_avg = (
        volume
        .rolling(20)
        .mean()
        .iloc[-1]
    )

    volume_ratio = 1

    if volume_avg > 0:

        volume_ratio = (
            volume.iloc[-1]
            / volume_avg
        )

    # -----------------------------------------------------
    # GETİRİLER
    # -----------------------------------------------------

    def return_percent(days):

        if len(close) <= days:
            return 0

        old = safe_float(
            close.iloc[-days - 1]
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
    # 52 HAFTA ZİRVESİ
    # -----------------------------------------------------

    high_52 = safe_float(
        close.tail(252).max(),
        price
    )

    distance_52 = 0

    if high_52 > 0:

        distance_52 = (
            price / high_52 - 1
        ) * 100

    # -----------------------------------------------------
    # VOLATİLİTE
    # -----------------------------------------------------

    returns = (
        close
        .pct_change()
        .dropna()
    )

    volatility = 0

    if len(returns) >= 20:

        volatility = safe_float(
            returns
            .rolling(20)
            .std()
            .iloc[-1]
            *
            np.sqrt(252)
            *
            100
        )

    # -----------------------------------------------------
    # MA-T-R SKORU
    #
    # Bu skor eski sistem değildir.
    #
    # MaT-R sinyal gücünü ölçmek için:
    #
    # Trend
    # MACD
    # RSI
    # Momentum
    # Hacim
    # Risk
    # -----------------------------------------------------

    score = 50

    # Trend
    if price > ema34:
        score += 12

    if ema34 > sma34:
        score += 10

    # MACD
    if macd_now > signal_now:
        score += 12

    if histogram_now > 0:
        score += 6

    # RSI
    if 50 <= rsi_now <= 70:
        score += 8

    elif 45 <= rsi_now < 50:
        score += 4

    elif rsi_now > 75:
        score -= 5

    elif rsi_now < 35:
        score -= 8

    # Momentum
    if ret21 > 5:
        score += 6

    elif ret21 > 0:
        score += 3

    elif ret21 < -5:
        score -= 6

    # Hacim
    if volume_ratio >= 2:
        score += 8

    elif volume_ratio >= 1.5:
        score += 5

    elif volume_ratio < 0.7:
        score -= 3

    # Risk
    if volatility > 60:
        score -= 10

    elif volatility > 40:
        score -= 5

    score = clamp(
        score,
        0,
        100
    )

    # -----------------------------------------------------
    # SİNYAL
    # -----------------------------------------------------

    if entry_signal:

        signal_name = "AL"

    elif (
        macd_now > signal_now
        and
        trend_positive
    ):

        signal_name = "İZLE"

    elif macd_now < signal_now:

        signal_name = "ZAYIF"

    else:

        signal_name = "NÖTR"

    # -----------------------------------------------------
    # MA-T-R DURUMU
    # -----------------------------------------------------

    if entry_signal:

        mat_r_status = (
            "MA-T-R AL SİNYALİ"
        )

    elif (
        macd_now > signal_now
        and trend_positive
    ):

        mat_r_status = (
            "POZİTİF TREND"
        )

    elif macd_now < signal_now:

        mat_r_status = (
            "MACD NEGATİF"
        )

    else:

        mat_r_status = (
            "BEKLE"
        )

    # -----------------------------------------------------
    # EK SİNYALLER
    # -----------------------------------------------------

    signals = []

    if entry_signal:
        signals.append("MA-T-R AL")

    if price > ema34:
        signals.append("EMA34 ÜSTÜ")

    if ema34 > sma34:
        signals.append("EMA34 > SMA34")

    if macd_now > signal_now:
        signals.append("MACD POZİTİF")

    if histogram_now > 0:
        signals.append("HISTOGRAM POZİTİF")

    if volume_ratio >= 1.5:
        signals.append("YÜKSEK HACİM")

    if ret21 > 5:
        signals.append("MOMENTUM")

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

        # Ana MaT-R skoru
        "score": int(score),

        "signal": signal_name,

        "matrStatus": mat_r_status,

        "entrySignal": bool(
            entry_signal
        ),

        # Trend
        "trend": trend,

        "ema34": round(
            ema34,
            2
        ),

        "sma34": round(
            sma34,
            2
        ),

        # MACD
        "macd": round(
            macd_now,
            6
        ),

        "macdSignal": round(
            signal_now,
            6
        ),

        "macdHistogram": round(
            histogram_now,
            6
        ),

        # ATR
        "atr17": round(
            atr_now,
            4
        ),

        # Zarar kes
        "stopLoss": round(
            stop,
            2
        ),

        "stopLossPercent": round(
            stop_percent,
            2
        ),

        # Kar al
        "takeProfit1": round(
            tp1,
            2
        ),

        "takeProfit2": round(
            tp2,
            2
        ),

        "takeProfit1Percent": 12,

        "takeProfit2Percent": 20,

        # RSI
        "rsi": round(
            rsi_now,
            2
        ),

        # Hacim
        "volumeRatio": round(
            volume_ratio,
            2
        ),

        # Getiriler
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

        # Risk
        "volatility": round(
            volatility,
            2
        ),

        "distance52High": round(
            distance_52,
            2
        ),

        "signals": signals
    }


# =========================================================
# YAHOO DATAFRAME AYIKLAMA
# =========================================================

def get_ticker_data(raw, ticker):

    if raw is None or raw.empty:
        return None

    if not isinstance(
        raw.columns,
        pd.MultiIndex
    ):

        return raw.copy()

    level0 = raw.columns.get_level_values(0)
    level1 = raw.columns.get_level_values(1)

    if ticker in level0:

        return raw[ticker].copy()

    if ticker in level1:

        return raw.xs(
            ticker,
            axis=1,
            level=1
        ).copy()

    return None


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    print(
        "======================================"
    )

    print(
        "BIST MA-T-R RADAR BAŞLIYOR"
    )

    print(
        "======================================"
    )

    names = get_symbols()

    symbols = list(names.keys())

    print(
        "BIST sembol sayısı:",
        len(symbols)
    )

    output = []

    failed = []

    # -----------------------------------------------------
    # BATCH
    # -----------------------------------------------------

    for start in range(
        0,
        len(symbols),
        BATCH_SIZE
    ):

        batch = symbols[
            start:start + BATCH_SIZE
        ]

        print(
            f"[{start + 1}-"
            f"{start + len(batch)} / "
            f"{len(symbols)}]"
        )

        tickers = [
            symbol + ".IS"
            for symbol in batch
        ]

        try:

            raw = yf.download(
                tickers,
                period="2y",
                interval="1d",
                auto_adjust=True,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=30
            )

        except Exception as error:

            print(
                "BATCH ERROR:",
                error
            )

            raw = None

        for symbol in batch:

            ticker = (
                symbol + ".IS"
            )

            try:

                data = get_ticker_data(
                    raw,
                    ticker
                )

                result = analyze_stock(
                    symbol,
                    names[symbol],
                    data
                )

                if result is not None:

                    output.append(
                        result
                    )

                else:

                    failed.append(
                        symbol
                    )

            except Exception as error:

                print(
                    "SKIP:",
                    symbol,
                    error
                )

                failed.append(
                    symbol
                )

        time.sleep(1)

    # -----------------------------------------------------
    # SIRALA
    # -----------------------------------------------------

    output.sort(
        key=lambda x: (
            x["entrySignal"],
            x["score"]
        ),
        reverse=True
    )

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            allow_nan=False,
            separators=(
                ",",
                ":"
            )
        )

    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    print()
    print(
        "======================================"
    )

    print(
        "BAŞARILI:",
        len(output)
    )

    print(
        "VERİ YOK:",
        len(failed)
    )

    print(
        "======================================"
    )

    print(
        "İLK 20 MA-T-R:"
    )

    for index, stock in enumerate(
        output[:20],
        1
    ):

        print(
            index,
            stock["code"],
            "SKOR:",
            stock["score"],
            "SİNYAL:",
            stock["signal"],
            "DURUM:",
            stock["matrStatus"]
        )

    # -----------------------------------------------------
    # GÜVENLİK
    # -----------------------------------------------------

    if len(output) < 400:

        raise RuntimeError(
            "Çok az hisse üretildi: "
            + str(len(output))
        )

    print()
    print(
        "data.json başarıyla oluşturuldu."
    )


if __name__ == "__main__":

    main()
