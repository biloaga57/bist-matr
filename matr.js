/* =========================================================
   BIST MaT-R
   MaT-R stratejisinin JavaScript karşılığı

   Temel mantık:
   - Trend: EMA34 > SMA34
   - MACD: EMA3 - EMA5
   - Sinyal: SMA2
   - AL: MACD'nin sinyali yukarı kesmesi + trend
   - ATR: 17
   - Zarar kes: giriş fiyatı - ATR17 × 2.2
   - TP1: +%12
   - TP2: +%20
   - EMA: 8 / 21 / 34 / 55 / 89 / 144 / 233 / 377
========================================================= */

"use strict";


/* =========================================================
   AYARLAR
========================================================= */

const MATR_CONFIG = {

    trendPeriod: 34,

    macdFast: 3,
    macdSlow: 5,
    macdSignal: 2,

    atrPeriod: 17,
    stopMultiplier: 2.2,

    takeProfit1: 0.12,
    takeProfit2: 0.20,

    emaPeriods: [
        8,
        21,
        34,
        55,
        89,
        144,
        233,
        377
    ]

};


/* =========================================================
   SAYI KONTROLÜ
========================================================= */

function safeNumber(value, fallback = 0) {

    const n = Number(value);

    if (!Number.isFinite(n)) {
        return fallback;
    }

    return n;

}


/* =========================================================
   EMA
========================================================= */

function ema(values, period) {

    if (!Array.isArray(values) || values.length === 0) {
        return [];
    }

    const result = new Array(values.length);

    const multiplier = 2 / (period + 1);

    result[0] = safeNumber(values[0]);

    for (let i = 1; i < values.length; i++) {

        const price = safeNumber(values[i]);

        result[i] =
            result[i - 1] +
            multiplier *
            (price - result[i - 1]);

    }

    return result;

}


/* =========================================================
   SMA
========================================================= */

function sma(values, period) {

    const result = new Array(values.length);

    let sum = 0;

    for (let i = 0; i < values.length; i++) {

        sum += safeNumber(values[i]);

        if (i >= period) {
            sum -= safeNumber(values[i - period]);
        }

        if (i >= period - 1) {
            result[i] = sum / period;
        } else {
            result[i] = null;
        }

    }

    return result;

}


/* =========================================================
   MACD
========================================================= */

function calculateMACD(close) {

    const fast =
        ema(
            close,
            MATR_CONFIG.macdFast
        );

    const slow =
        ema(
            close,
            MATR_CONFIG.macdSlow
        );

    const macd =
        close.map((_, i) => {

            if (
                fast[i] == null ||
                slow[i] == null
            ) {
                return null;
            }

            return fast[i] - slow[i];

        });


    /*
       MaT-R'daki:

       signal = SMA(macd, 2)

       mantığı.
    */

    const validMacd =
        macd.map(x =>
            x == null ? 0 : x
        );

    const signal =
        sma(
            validMacd,
            MATR_CONFIG.macdSignal
        );


    return {
        fast,
        slow,
        macd,
        signal
    };

}


/* =========================================================
   ATR
========================================================= */

function calculateATR(
    high,
    low,
    close,
    period = MATR_CONFIG.atrPeriod
) {

    const tr = new Array(close.length);

    for (let i = 0; i < close.length; i++) {

        if (i === 0) {

            tr[i] =
                safeNumber(high[i]) -
                safeNumber(low[i]);

            continue;
        }


        const h =
            safeNumber(high[i]);

        const l =
            safeNumber(low[i]);

        const previousClose =
            safeNumber(close[i - 1]);


        const range1 =
            h - l;

        const range2 =
            Math.abs(
                h - previousClose
            );

        const range3 =
            Math.abs(
                l - previousClose
            );


        tr[i] =
            Math.max(
                range1,
                range2,
                range3
            );

    }


    /*
       Pine kodundaki özel ATR:

       atr := nz(
           atr[1] +
           (Tr - atr[1]) / p,
           Tr
       )

       Bu klasik SMA ATR'den farklıdır.
       Wilder tarzı yumuşatılmış ATR'ye
       karşılık gelir.
    */

    const result =
        new Array(close.length);

    let previous = null;

    for (let i = 0; i < tr.length; i++) {

        if (previous === null) {

            previous =
                safeNumber(tr[i]);

        } else {

            previous =
                previous +
                (
                    safeNumber(tr[i]) -
                    previous
                ) / period;

        }

        result[i] = previous;

    }

    return result;

}


/* =========================================================
   TREND
========================================================= */

function calculateTrend(close) {

    const ema34 =
        ema(
            close,
            MATR_CONFIG.trendPeriod
        );

    const sma34 =
        sma(
            close,
            MATR_CONFIG.trendPeriod
        );


    return {
        ema34,
        sma34
    };

}


/* =========================================================
   AL SİNYALİ
========================================================= */

function isCrossOver(
    previousMacd,
    currentMacd,
    previousSignal,
    currentSignal
) {

    if (
        previousMacd == null ||
        currentMacd == null ||
        previousSignal == null ||
        currentSignal == null
    ) {
        return false;
    }


    return (
        previousMacd <= previousSignal &&
        currentMacd > currentSignal
    );

}


/* =========================================================
   EMA'LAR
========================================================= */

function calculateEMAs(close) {

    const result = {};

    for (
        const period
        of MATR_CONFIG.emaPeriods
    ) {

        result[period] =
            ema(
                close,
                period
            );

    }

    return result;

}


/* =========================================================
   TEK HİSSE MATR ANALİZİ
========================================================= */

function calculateMATR(data) {

    if (
        !Array.isArray(data) ||
        data.length < 50
    ) {

        return {
            valid: false,
            reason: "Yetersiz veri"
        };

    }


    const close =
        data.map(x =>
            safeNumber(x.close)
        );

    const high =
        data.map(x =>
            safeNumber(x.high)
        );

    const low =
        data.map(x =>
            safeNumber(x.low)
        );


    /* -----------------------------------------------------
       TREND
    ----------------------------------------------------- */

    const trend =
        calculateTrend(close);


    /* -----------------------------------------------------
       MACD
    ----------------------------------------------------- */

    const macd =
        calculateMACD(close);


    /* -----------------------------------------------------
       ATR
    ----------------------------------------------------- */

    const atr =
        calculateATR(
            high,
            low,
            close,
            MATR_CONFIG.atrPeriod
        );


    /* -----------------------------------------------------
       EMA'LAR
    ----------------------------------------------------- */

    const emas =
        calculateEMAs(close);


    const last =
        close.length - 1;

    const previous =
        last - 1;


    const price =
        close[last];


    /* -----------------------------------------------------
       TREND KOŞULU

       Pine:

       oncu2 < oncu1

       SMA34 < EMA34
    ----------------------------------------------------- */

    const trendUp =
        trend.sma34[last] != null &&
        trend.ema34[last] != null &&
        trend.sma34[last] <
        trend.ema34[last];


    /* -----------------------------------------------------
       MACD CROSS
    ----------------------------------------------------- */

    const macdCross =
        isCrossOver(
            macd.macd[previous],
            macd.macd[last],
            macd.signal[previous],
            macd.signal[last]
        );


    /* -----------------------------------------------------
       AL

       Pine:

       entry_long =
       ta.crossover(macd, signal)
       and
       oncu2 < oncu1
    ----------------------------------------------------- */

    const buySignal =
        macdCross &&
        trendUp;


    /* -----------------------------------------------------
       ATR
    ----------------------------------------------------- */

    const currentATR =
        safeNumber(
            atr[last]
        );


    /* -----------------------------------------------------
       SON AL FİYATI

       data içinde daha önce hesaplanmış
       bir giriş varsa onu kullan.
    ----------------------------------------------------- */

    let entryPrice = null;

    if (buySignal) {

        entryPrice =
            price;

    }


    /* -----------------------------------------------------
       ZARAR KES

       entry_price - ATR × 2.2
    ----------------------------------------------------- */

    let stopLoss = null;

    if (entryPrice != null) {

        stopLoss =
            entryPrice -
            (
                MATR_CONFIG.stopMultiplier *
                currentATR
            );

    }


    /* -----------------------------------------------------
       KAR ALMA
    ----------------------------------------------------- */

    let takeProfit1 = null;
    let takeProfit2 = null;

    if (entryPrice != null) {

        takeProfit1 =
            entryPrice *
            (
                1 +
                MATR_CONFIG.takeProfit1
            );

        takeProfit2 =
            entryPrice *
            (
                1 +
                MATR_CONFIG.takeProfit2
            );

    }


    /* -----------------------------------------------------
       EMA DURUMLARI
    ----------------------------------------------------- */

    const emaState = {};

    for (
        const period
        of MATR_CONFIG.emaPeriods
    ) {

        const value =
            emas[period][last];

        emaState[period] = {

            value: safeNumber(value),

            above:
                price >
                safeNumber(value)

        };

    }


    /* -----------------------------------------------------
       MACD DURUMU
    ----------------------------------------------------- */

    const macdValue =
        safeNumber(
            macd.macd[last]
        );

    const signalValue =
        safeNumber(
            macd.signal[last]
        );

    const histogram =
        macdValue -
        signalValue;


    /* -----------------------------------------------------
       ÇIKIŞ

       Pine:

       exit_long =
       close < SL_floating_long

       Burada gerçek giriş fiyatı bilinmiyorsa
       sadece mevcut MaT-R AL sinyali hesaplanır.
    ----------------------------------------------------- */

    let stopSignal = false;

    if (
        entryPrice != null &&
        stopLoss != null
    ) {

        stopSignal =
            price < stopLoss;

    }


    /* -----------------------------------------------------
       KAR DURUMLARI
    ----------------------------------------------------- */

    let tp1Reached = false;
    let tp2Reached = false;

    if (entryPrice != null) {

        tp1Reached =
            price >= takeProfit1;

        tp2Reached =
            price >= takeProfit2;

    }


    /* -----------------------------------------------------
       SİNYAL
    ----------------------------------------------------- */

    let signal = "BEKLE";

    if (buySignal) {

        signal = "AL";

    } else if (stopSignal) {

        signal = "SAT";

    } else if (tp2Reached) {

        signal = "KAR AL 2";

    } else if (tp1Reached) {

        signal = "KAR AL 1";

    }


    /* -----------------------------------------------------
       SONUÇ
    ----------------------------------------------------- */

    return {

        valid: true,

        price,

        signal,

        buySignal,

        stopSignal,

        tp1Reached,

        tp2Reached,

        trendUp,

        macdCross,

        trend: {

            ema34:
                safeNumber(
                    trend.ema34[last]
                ),

            sma34:
                safeNumber(
                    trend.sma34[last]
                )

        },

        macd: {

            value: macdValue,

            signal: signalValue,

            histogram

        },

        atr: currentATR,

        entryPrice,

        stopLoss,

        takeProfit1,

        takeProfit2,

        ema: emaState

    };

}


/* =========================================================
   GEÇMİŞ SİNYALLERİ TARA
========================================================= */

function scanMATR(data) {

    if (
        !Array.isArray(data) ||
        data.length < 50
    ) {

        return [];

    }


    const close =
        data.map(x =>
            safeNumber(x.close)
        );

    const high =
        data.map(x =>
            safeNumber(x.high)
        );

    const low =
        data.map(x =>
            safeNumber(x.low)
        );


    const trend =
        calculateTrend(close);

    const macd =
        calculateMACD(close);

    const atr =
        calculateATR(
            high,
            low,
            close,
            MATR_CONFIG.atrPeriod
        );


    const signals = [];


    for (
        let i = 1;
        i < close.length;
        i++
    ) {

        const trendUp =
            trend.sma34[i] != null &&
            trend.ema34[i] != null &&
            trend.sma34[i] <
            trend.ema34[i];


        const cross =
            isCrossOver(
                macd.macd[i - 1],
                macd.macd[i],
                macd.signal[i - 1],
                macd.signal[i]
            );


        if (
            cross &&
            trendUp
        ) {

            const entry =
                close[i];

            const currentATR =
                safeNumber(
                    atr[i]
                );


            const stop =
                entry -
                (
                    currentATR *
                    MATR_CONFIG.stopMultiplier
                );


            const tp1 =
                entry *
                (
                    1 +
                    MATR_CONFIG.takeProfit1
                );


            const tp2 =
                entry *
                (
                    1 +
                    MATR_CONFIG.takeProfit2
                );


            signals.push({

                index: i,

                date:
                    data[i].date ||
                    null,

                price:
                    entry,

                stopLoss:
                    stop,

                takeProfit1:
                    tp1,

                takeProfit2:
                    tp2

            });

        }

    }


    return signals;

}


/* =========================================================
   DIŞA AKTAR
========================================================= */

window.MATR = {

    config:
        MATR_CONFIG,

    ema,

    sma,

    calculateMACD,

    calculateATR,

    calculateTrend,

    calculateEMAs,

    calculateMATR,

    scanMATR

};
