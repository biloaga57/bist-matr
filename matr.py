import io
import json
import time
import math
import requests
import numpy as np
import pandas as pd
import yfinance as yf


# =========================================================
# AYARLAR
# =========================================================

SYMBOL_URL = (
    "https://raw.githubusercontent.com/ahmeterenodaci/"
    "Istanbul-Stock-Exchange--BIST--including-symbols-and-logos/"
    "main/bist.csv"
)

BATCH_SIZE = 25
PERIOD = "2y"

OUTPUT_FILE = "data.json"


# =========================================================
# GÜVENLİ SAYI
# =========================================================

def safe_float(value, default=0.0):

    try:

        value = float(value)

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return default


# =========================================================
# HİSSE LİSTESİ
# =========================================================

def get_symbols():

    print("BIST hisse listesi indiriliyor...")

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
            "bist.csv içinde symbol sütunu bulunamadı."
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
        "symbol"
    )

    result = dict(
        zip(
            df["symbol"],
            df["name"]
        )
    )

    print(
        "Toplam sembol:",
        len(result)
    )

    return result


# =========================================================
# EMA
# =========================================================

def ema(series, period):

    return (
        series
        .ewm(
            span=period,
            adjust=False
        )
        .mean()
    )


# =========================================================
# SMA
# =========================================================

def sma(series, period):

    return (
        series
        .rolling(
            period
        )
        .mean()
    )


# =========================================================
# ATR
#
# Pine MaT-R kodundaki ATR:
#
# atr := nz(
#     atr[1] + (Tr - atr[1]) / p,
#     Tr
# )
#
# =========================================================

def matr_atr(
    high,
    low,
    close,
    period=17
):

    previous_close =
        close.shift(1)

    tr1 = (
        high -
        low
    )

    tr2 = (
        high -
        previous_close
    ).abs()

    tr3 = (
        low -
        previous_close
    ).abs()

    tr = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(
        axis=1
    )

    result = []

    previous_atr = None

    for value in tr:

        value = safe_float(
            value
        )

        if previous_atr is None:

            previous_atr = value

        else:

            previous_atr = (
                previous_atr +
                (
                    value -
                    previous_atr
                ) / period
            )

        result.append(
            previous_atr
        )

    return pd.Series(
        result,
        index=close.index
    )


# =========================================================
# MATR HESABI
# =========================================================

def calculate_matr(df):

    if df is None:
        return None

    if df.empty:
        return None

    required = [
        "Close",
        "High",
        "Low",
        "Volume"
    ]

    for column in required:

        if column not in df.columns:
            return None

    df = df.copy()

    for column in required:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    df = df.dropna(
        subset=[
            "Close",
            "High",
            "Low"
        ]
    )

    if len(df) < 100:

        return None


    close = df["Close"]
    high = df["High"]
    low = df["Low"]


    # -----------------------------------------------------
    # EMA34 / SMA34
    # -----------------------------------------------------

    ema34 = ema(
        close,
        34
    )

    sma34 = sma(
        close,
        34
    )


    # -----------------------------------------------------
    # MACD
    #
    # EMA 3 - EMA 5
    # -----------------------------------------------------

    fast = ema(
        close,
        3
    )

    slow = ema(
        close,
        5
    )

    macd = (
        fast -
        slow
    )


    # MaT-R kodunda:
    #
    # signal = SMA(macd, 2)
    #

    signal_line = sma(
        macd,
        2
    )


    # -----------------------------------------------------
    # ATR 17
    # -----------------------------------------------------

    atr = matr_atr(
        high,
        low,
        close,
        17
    )


    # -----------------------------------------------------
    # SON BAR
    # -----------------------------------------------------

    last = len(df) - 1
    previous = last - 1

    price = safe_float(
        close.iloc[last]
    )


    # -----------------------------------------------------
    # TREND
    #
    # oncu2 < oncu1
    #
    # SMA34 < EMA34
    # -----------------------------------------------------

    trend_up = (

        pd.notna(
            sma34.iloc[last]
        )

        and

        pd.notna(
            ema34.iloc[last]
        )

        and

        sma34.iloc[last]
        <
        ema34.iloc[last]

    )


    # -----------------------------------------------------
    # MACD CROSSOVER
    #
    # ta.crossover(macd, signal)
    #
    # Önce MACD <= sinyal
    # Şimdi MACD > sinyal
    # -----------------------------------------------------

    macd_cross = (

        pd.notna(
            macd.iloc[previous]
        )

        and

        pd.notna(
            signal_line.iloc[previous]
        )

        and

        pd.notna(
            macd.iloc[last]
        )

        and

        pd.notna(
            signal_line.iloc[last]
        )

        and

        macd.iloc[previous]
        <=
        signal_line.iloc[previous]

        and

        macd.iloc[last]
        >
        signal_line.iloc[last]

    )


    # -----------------------------------------------------
    # AL
    # -----------------------------------------------------

    buy_signal = (

        macd_cross
        and
        trend_up

    )


    # -----------------------------------------------------
    # ATR
    # -----------------------------------------------------

    current_atr = safe_float(
        atr.iloc[last]
    )


    # -----------------------------------------------------
    # GİRİŞ
    #
    # Yeni AL sinyalinde:
    # giriş = mevcut kapanış
    #
    # -----------------------------------------------------

    entry_price = None

    if buy_signal:

        entry_price = price


    # -----------------------------------------------------
    # ZARAR KES
    #
    # entry - ATR × 2.2
    # -----------------------------------------------------

    stop_loss = None

    if entry_price is not None:

        stop_loss = (
            entry_price -
            (
                current_atr *
                2.2
            )
        )


    # -----------------------------------------------------
    # KAR AL 1
    # -----------------------------------------------------

    take_profit_1 = None

    if entry_price is not None:

        take_profit_1 = (
            entry_price *
            1.12
        )


    # -----------------------------------------------------
    # KAR AL 2
    # -----------------------------------------------------

    take_profit_2 = None

    if entry_price is not None:

        take_profit_2 = (
            entry_price *
            1.20
        )


    # -----------------------------------------------------
    # SİNYAL
    # -----------------------------------------------------

    if buy_signal:

        final_signal = "AL"

    else:

        final_signal = "BEKLE"


    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    return {

        "price": round(
            price,
            4
        ),

        "signal":
            final_signal,

        "buySignal":
            bool(buy_signal),

        "trendUp":
            bool(trend_up),

        "macdCross":
            bool(macd_cross),

        "macd":
            round(
                safe_float(
                    macd.iloc[last]
                ),
                6
            ),

        "macdSignal":
            round(
                safe_float(
                    signal_line.iloc[last]
                ),
                6
            ),

        "macdHistogram":
            round(
                safe_float(
                    macd.iloc[last] -
                    signal_line.iloc[last]
                ),
                6
            ),

        "atr":
            round(
                current_atr,
                4
            ),

        "stopLoss":
            (
                round(
                    stop_loss,
                    4
                )
                if stop_loss is not None
                else None
            ),

        "takeProfit1":
            (
                round(
                    take_profit_1,
                    4
                )
                if take_profit_1 is not None
                else None
            ),

        "takeProfit2":
            (
                round(
                    take_profit_2,
                    4
                )
                if take_profit_2 is not None
                else None
            ),

        "ema34":
            round(
                safe_float(
                    ema34.iloc[last]
                ),
                4
            ),

        "sma34":
            round(
                safe_float(
                    sma34.iloc[last]
                ),
                4
            )

    }


# =========================================================
# HİSSE GEÇMİŞİ
# =========================================================

def build_history(df):

    history = []

    if df is None or df.empty:
        return history

    for index, row in df.iterrows():

        close = safe_float(
            row["Close"],
            None
        )

        high = safe_float(
            row["High"],
            None
        )

        low = safe_float(
            row["Low"],
            None
        )

        if (
            close is None or
            high is None or
            low is None
        ):
            continue

        if hasattr(index, "strftime"):

            date = index.strftime(
                "%Y-%m-%d"
            )

        else:

            date = str(index)


        history.append({

            "date": date,

            "close": round(
                close,
                4
            ),

            "high": round(
                high,
                4
            ),

            "low": round(
                low,
                4
            )

        })

    return history


# =========================================================
# YAHOO VERİSİNİ ÇÖZ
# =========================================================

def extract_ticker_data(
    raw,
    ticker
):

    if raw is None:
        return None

    if raw.empty:
        return None


    # MultiIndex
    if isinstance(
        raw.columns,
        pd.MultiIndex
    ):

        levels0 = (
            raw.columns
            .get_level_values(0)
        )

        levels1 = (
            raw.columns
            .get_level_values(1)
        )


        if ticker in levels0:

            return raw[
                ticker
            ].copy()


        if ticker in levels1:

            return raw.xs(
                ticker,
                axis=1,
                level=1
            ).copy()


    # Tek ticker
    else:

        return raw.copy()


    return None


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    names = get_symbols()

    symbols = list(
        names.keys()
    )


    results = []

    failed = []


    total = len(symbols)


    print()
    print(
        "========================================"
    )
    print(
        "BIST MaT-R MOTORU"
    )
    print(
        "========================================"
    )
    print(
        "Hisse:",
        total
    )
    print(
        "Periyot:",
        PERIOD
    )
    print(
        "MACD: EMA3 - EMA5"
    )
    print(
        "Sinyal: SMA2"
    )
    print(
        "Trend: EMA34 > SMA34"
    )
    print(
        "ATR: 17"
    )
    print(
        "Stop: ATR x 2.2"
    )
    print(
        "TP1: %12"
    )
    print(
        "TP2: %20"
    )
    print(
        "========================================"
    )
    print()


    # -----------------------------------------------------
    # BATCH
    # -----------------------------------------------------

    for start in range(
        0,
        total,
        BATCH_SIZE
    ):

        batch = symbols[
            start:
            start + BATCH_SIZE
        ]


        print(
            f"[{start + 1}-"
            f"{start + len(batch)} / "
            f"{total}]"
        )


        tickers = [
            symbol + ".IS"
            for symbol in batch
        ]


        try:

            raw = yf.download(

                tickers,

                period=PERIOD,

                interval="1d",

                auto_adjust=True,

                group_by="ticker",

                threads=True,

                progress=False,

                timeout=60

            )

        except Exception as error:

            print(
                "BATCH ERROR:",
                error
            )

            failed.extend(
                batch
            )

            time.sleep(2)

            continue


        # -------------------------------------------------
        # HER HİSSE
        # -------------------------------------------------

        for symbol in batch:

            ticker =
                symbol + ".IS"


            try:

                df =
                    extract_ticker_data(
                        raw,
                        ticker
                    )


                if (
                    df is None or
                    df.empty
                ):

                    failed.append(
                        symbol
                    )

                    continue


                matr =
                    calculate_matr(
                        df
                    )


                if matr is None:

                    failed.append(
                        symbol
                    )

                    continue


                history =
                    build_history(
                        df
                    )


                if len(history) < 50:

                    failed.append(
                        symbol
                    )

                    continue


                result = {

                    "code":
                        symbol,

                    "name":
                        str(
                            names.get(
                                symbol,
                                ""
                            )
                        ),

                    "price":
                        matr["price"],

                    "signal":
                        matr["signal"],

                    "buySignal":
                        matr["buySignal"],

                    "trendUp":
                        matr["trendUp"],

                    "macdCross":
                        matr["macdCross"],

                    "macd":
                        matr["macd"],

                    "macdSignal":
                        matr["macdSignal"],

                    "macdHistogram":
                        matr[
                            "macdHistogram"
                        ],

                    "atr":
                        matr["atr"],

                    "stopLoss":
                        matr["stopLoss"],

                    "takeProfit1":
                        matr[
                            "takeProfit1"
                        ],

                    "takeProfit2":
                        matr[
                            "takeProfit2"
                        ],

                    "ema34":
                        matr["ema34"],

                    "sma34":
                        matr["sma34"],

                    "history":
                        history

                }


                results.append(
                    result
                )


            except Exception as error:

                print(
                    "SKIP",
                    symbol,
                    error
                )

                failed.append(
                    symbol
                )


        time.sleep(1)


    # =====================================================
    # AL SİNYALLERİ ÖNE AL
    # =====================================================

    def signal_rank(item):

        signal =
            item.get(
                "signal",
                "BEKLE"
            )

        if signal == "AL":
            return 0

        return 1


    results.sort(
        key=signal_rank
    )


    # =====================================================
    # JSON
    # =====================================================

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            ensure_ascii=False,
            allow_nan=False,
            separators=(
                ",",
                ":"
            )
        )


    # =====================================================
    # RAPOR
    # =====================================================

    buy_count =
        sum(
            1
            for x in results
            if x["signal"] == "AL"
        )


    print()
    print(
        "========================================"
    )

    print(
        "MaT-R TAMAMLANDI"
    )

    print(
        "Başarılı:",
        len(results)
    )

    print(
        "Veri yok:",
        len(failed)
    )

    print(
        "AL Sinyali:",
        buy_count
    )

    print(
        "data.json:",
        OUTPUT_FILE
    )

    print(
        "========================================"
    )


    print()
    print(
        "İLK AL SİNYALLERİ:"
    )


    buy_results = [
        x
        for x in results
        if x["signal"] == "AL"
    ]


    for i, item in enumerate(
        buy_results[:20],
        1
    ):

        print(
            i,
            item["code"],
            "Fiyat:",
            item["price"],
            "ATR:",
            item["atr"],
            "Stop:",
            item["stopLoss"],
            "TP1:",
            item["takeProfit1"],
            "TP2:",
            item["takeProfit2"]
        )


    # -----------------------------------------------------
    # Minimum veri kontrolü
    # -----------------------------------------------------

    if len(results) < 400:

        raise RuntimeError(

            "Çok az hisse verisi oluştu: "
            + str(len(results))

        )


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":

    main()
