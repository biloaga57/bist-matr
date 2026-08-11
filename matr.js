// ============================================================
// BIST MaT-R
// matr.py tarafından oluşturulan data.json'u kullanır.
// ============================================================

const DATA_URL = "./data.json";

let stocks = [];
let filteredStocks = [];

const tbody = document.getElementById("stockTableBody");
const searchInput = document.getElementById("search");
const signalFilter = document.getElementById("signalFilter");
const sortSelect = document.getElementById("sortSelect");
const statusElement = document.getElementById("status");


// ============================================================
// GÜVENLİ SAYI
// ============================================================

function num(value, fallback = 0) {
    const n = Number(value);

    return Number.isFinite(n)
        ? n
        : fallback;
}


// ============================================================
// GÜVENLİ HTML
// ============================================================

function escapeHTML(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// ============================================================
// SAYI FORMAT
// ============================================================

function formatNumber(value, digits = 2) {

    const n = Number(value);

    if (!Number.isFinite(n)) {
        return "-";
    }

    return n.toFixed(digits);
}


// ============================================================
// YÜZDE
// ============================================================

function formatPercent(value) {

    const n = Number(value);

    if (!Number.isFinite(n)) {
        return "-";
    }

    
    return (
        n >= 0 ? "+" : ""
    ) + n.toFixed(2) + "%";
}


// ============================================================
// SİNYAL ADI
// ============================================================

function signalName(signal) {

    const names = {

        "AL": "AL",

        "KAR AL 1": "KAR AL 1",

        "KAR AL 2": "KAR AL 2",

        "STOP": "STOP",

        "POZİTİF": "POZİTİF",

        "İZLE": "İZLE",

        "BEKLE": "BEKLE"
    };

    return names[signal] || signal || "BEKLE";
}


// ============================================================
// SİNYAL CSS
// ============================================================

function signalClass(signal) {

    switch (signal) {

        case "AL":
            return "strong";

        case "KAR AL 1":
            return "positive";

        case "KAR AL 2":
            return "strong";

        case "STOP":
            return "sell";

        case "POZİTİF":
            return "positive";

        case "İZLE":
            return "neutral";

        case "BEKLE":
        default:
            return "weak";
    }
}


// ============================================================
// SKOR CSS
// ============================================================

function scoreClass(score) {

    if (score >= 80) {
        return "very-good";
    }

    if (score >= 65) {
        return "good";
    }

    if (score >= 50) {
        return "neutral";
    }

    return "danger";
}


// ============================================================
// DATA NORMALİZASYON
// ============================================================

function normalizeStock(stock) {

    return {

        ...stock,

        code:
            String(stock.code || "")
                .toUpperCase(),

        name:
            String(stock.name || ""),

        price:
            num(stock.price),

        matrScore:
            num(stock.matrScore),

        ema34:
            num(stock.ema34),

        sma34:
            num(stock.sma34),

        fastMA:
            num(stock.fastMA),

        slowMA:
            num(stock.slowMA),

        macd:
            num(stock.macd),

        macdSignal:
            num(stock.macdSignal),

        histogram:
            num(stock.histogram),

        atr:
            num(stock.atr),

        atrPercent:
            num(stock.atrPercent),

        rsi:
            num(stock.rsi),

        adx:
            num(stock.adx),

        volume:
            num(stock.volume),

        volumeRatio:
            num(stock.volumeRatio),

        ret21:
            num(stock.ret21),

        ret63:
            num(stock.ret63),

        ret126:
            num(stock.ret126),

        high52:
            num(stock.high52),

        low52:
            num(stock.low52),

        distance52High:
            num(stock.distance52High),

        distance52Low:
            num(stock.distance52Low),

        entryPrice:
            stock.entryPrice === null
                ? null
                : num(stock.entryPrice),

        entryATR:
            stock.entryATR === null
                ? null
                : num(stock.entryATR),

        tp1:
            stock.tp1 === null
                ? null
                : num(stock.tp1),

        tp2:
            stock.tp2 === null
                ? null
                : num(stock.tp2),

        stop:
            stock.stop === null
                ? null
                : num(stock.stop),

        barsSinceEntry:
            stock.barsSinceEntry === null
                ? null
                : num(stock.barsSinceEntry),

        signal:
            String(stock.signal || "BEKLE"),

        matrSignal:
            String(stock.matrSignal || "YOK"),

        positionStatus:
            String(stock.positionStatus || "BEKLE"),

        trend:
            String(stock.trend || "NÖTR"),

        macdState:
            String(stock.macdState || "NÖTR"),

        signals:
            Array.isArray(stock.signals)
                ? stock.signals
                : []
    };
}


// ============================================================
// VERİYİ YÜKLE
// ============================================================

async function loadData() {

    try {

        if (statusElement) {

            statusElement.textContent =
                "MaT-R verileri yükleniyor...";
        }


        const response = await fetch(
            DATA_URL + "?v=" + Date.now(),
            {
                cache: "no-store"
            }
        );


        if (!response.ok) {

            throw new Error(
                "data.json yüklenemedi. HTTP " +
                response.status
            );
        }


        const data =
            await response.json();


        if (!Array.isArray(data)) {

            throw new Error(
                "data.json liste formatında değil."
            );
        }


        stocks = data
            .filter(
                stock =>
                    stock &&
                    stock.code
            )
            .map(normalizeStock);


        filteredStocks =
            [...stocks];


        sortStocks();

        updateSummary();

        updateStatus();


    } catch (error) {

        console.error(
            "MaT-R veri hatası:",
            error
        );


        if (statusElement) {

            statusElement.innerHTML = `

                <div class="error">

                    <strong>
                        MaT-R verileri yüklenemedi.
                    </strong>

                    <br><br>

                    ${escapeHTML(error.message)}

                    <br><br>

                    data.json dosyasının
                    GitHub deposunda bulunduğundan
                    emin ol.

                </div>
            `;
        }


        if (tbody) {

            tbody.innerHTML = `

                <tr>

                    <td
                        colspan="11"
                        class="loading"
                    >

                        Veri yüklenemedi.

                    </td>

                </tr>
            `;
        }
    }
}


// ============================================================
// FİLTRE
// ============================================================

function applyFilters() {

    const search =
        searchInput
            ?.value
            ?.toLowerCase()
            .trim() || "";


    const selectedSignal =
        signalFilter
            ?.value || "";


    filteredStocks =
        stocks.filter(stock => {


            const matchesSearch =

                !search ||

                stock.code
                    .toLowerCase()
                    .includes(search) ||

                stock.name
                    .toLowerCase()
                    .includes(search);


            let matchesSignal = true;


            switch (selectedSignal) {

                case "buy":

                    matchesSignal =
                        stock.signal === "AL";

                    break;


                case "tp1":

                    matchesSignal =
                        stock.signal === "KAR AL 1";

                    break;


                case "tp2":

                    matchesSignal =
                        stock.signal === "KAR AL 2";

                    break;


                case "stop":

                    matchesSignal =
                        stock.signal === "STOP";

                    break;


                case "positive":

                    matchesSignal =
                        stock.signal === "POZİTİF";

                    break;


                case "watch":

                    matchesSignal =
                        stock.signal === "İZLE";

                    break;


                case "wait":

                    matchesSignal =
                        stock.signal === "BEKLE";

                    break;


                default:

                    matchesSignal = true;
            }


            return (
                matchesSearch &&
                matchesSignal
            );
        });


    sortStocks();
}


// ============================================================
// SIRALAMA
// ============================================================

function sortStocks() {

    const sort =
        sortSelect
            ?.value || "score";


    filteredStocks.sort(
        (a, b) => {

            switch (sort) {

                case "score":

                    return (
                        b.matrScore -
                        a.matrScore
                    );


                case "price":

                    return (
                        b.price -
                        a.price
                    );


                case "rsi":

                    return (
                        b.rsi -
                        a.rsi
                    );


                case "adx":

                    return (
                        b.adx -
                        a.adx
                    );


                case "volume":

                    return (
                        b.volumeRatio -
                        a.volumeRatio
                    );


                case "ret21":

                    return (
                        b.ret21 -
                        a.ret21
                    );


                case "ret63":

                    return (
                        b.ret63 -
                        a.ret63
                    );


                case "ret126":

                    return (
                        b.ret126 -
                        a.ret126
                    );


                case "atr":

                    return (
                        a.atrPercent -
                        b.atrPercent
                    );


                default:

                    return (
                        b.matrScore -
                        a.matrScore
                    );
            }
        }
    );


    render();
}


// ============================================================
// TABLO
// ============================================================

function render() {

    if (!tbody) {
        return;
    }


    if (!filteredStocks.length) {

        tbody.innerHTML = `

            <tr>

                <td
                    colspan="11"
                    class="loading"
                >

                    Hisse bulunamadı.

                </td>

            </tr>
        `;

        updateCount();

        return;
    }


    tbody.innerHTML =
        filteredStocks
            .map(
                (stock, index) => `

                    <tr
                        onclick="showStockDetails(${index})"
                    >

                        <td>
                            <strong>
                                ${index + 1}
                            </strong>
                        </td>


                        <td>

                            <span class="code">

                                ${escapeHTML(
                                    stock.code
                                )}

                            </span>

                            <br>

                            <span class="muted">

                                ${escapeHTML(
                                    stock.name
                                )}

                            </span>

                        </td>


                        <td>

                            ${formatNumber(
                                stock.price,
                                2
                            )}

                        </td>


                        <td>

                            <span
                                class="score ${scoreClass(
                                    stock.matrScore
                                )}"
                            >

                                ${stock.matrScore}

                            </span>

                        </td>


                        <td>

                            <span
                                class="signal ${signalClass(
                                    stock.signal
                                )}"
                            >

                                ${signalName(
                                    stock.signal
                                )}

                            </span>

                        </td>


                        <td>

                            ${escapeHTML(
                                stock.trend
                            )}

                        </td>


                        <td>

                            ${escapeHTML(
                                stock.macdState
                            )}

                        </td>


                        <td>

                            ${formatNumber(
                                stock.rsi,
                                1
                            )}

                        </td>


                        <td>

                            ${formatNumber(
                                stock.adx,
                                1
                            )}

                        </td>


                        <td>

                            ${formatNumber(
                                stock.atrPercent,
                                2
                            )}%

                        </td>


                        <td>

                            ${formatPercent(
                                stock.ret21
                            )}

                        </td>

                    </tr>
                `
            )
            .join("");


    updateCount();
}


// ============================================================
// ÖZET
// ============================================================

function updateSummary() {

    const total =
        document.getElementById(
            "totalStocks"
        );


    const buy =
        document.getElementById(
            "strongStocks"
        );


    const positive =
        document.getElementById(
            "positiveStocks"
        );


    const average =
        document.getElementById(
            "averageScore"
        );


    const buyCount =
        stocks.filter(
            x => x.signal === "AL"
        ).length;


    const positiveCount =
        stocks.filter(
            x =>
                x.signal === "POZİTİF" ||
                x.signal === "AL"
        ).length;


    const avg =
        stocks.length

            ? stocks.reduce(
                (sum, stock) =>
                    sum + stock.matrScore,
                0
            ) / stocks.length

            : 0;


    if (total) {

        total.textContent =
            stocks.length;
    }


    if (buy) {

        buy.textContent =
            buyCount;
    }


    if (positive) {

        positive.textContent =
            positiveCount;
    }


    if (average) {

        average.textContent =
            avg.toFixed(1);
    }
}


// ============================================================
// DURUM
// ============================================================

function updateStatus() {

    if (!statusElement) {
        return;
    }


    const buy =
        stocks.filter(
            x => x.signal === "AL"
        ).length;


    const tp1 =
        stocks.filter(
            x => x.signal === "KAR AL 1"
        ).length;


    const tp2 =
        stocks.filter(
            x => x.signal === "KAR AL 2"
        ).length;


    const stop =
        stocks.filter(
            x => x.signal === "STOP"
        ).length;


    const today =
        stocks.length
            ? stocks[0].date
            : "-";


    statusElement.textContent =

        `MaT-R aktif • ${stocks.length} hisse • ` +
        `${buy} AL • ` +
        `${tp1} TP1 • ` +
        `${tp2} TP2 • ` +
        `${stop} STOP • ` +
        `Veri: ${today}`;
}


// ============================================================
// HİSSE DETAY
// ============================================================

function showStockDetails(index) {

    const stock =
        filteredStocks[index];


    if (!stock) {
        return;
    }


    const modal =
        document.getElementById(
            "stockModal"
        );


    const title =
        document.getElementById(
            "modalTitle"
        );


    const content =
        document.getElementById(
            "modalContent"
        );


    if (!modal || !title || !content) {
        return;
    }


    title.textContent =
        `${stock.code} • ${stock.name}`;


    const entry =
        stock.entryPrice !== null
            ? formatNumber(
                stock.entryPrice,
                4
            )
            : "-";


    const tp1 =
        stock.tp1 !== null
            ? formatNumber(
                stock.tp1,
                4
            )
            : "-";


    const tp2 =
        stock.tp2 !== null
            ? formatNumber(
                stock.tp2,
                4
            )
            : "-";


    const stop =
        stock.stop !== null
            ? formatNumber(
                stock.stop,
                4
            )
            : "-";


    content.innerHTML = `

        <div>

            <span
                class="signal ${signalClass(
                    stock.signal
                )}"
            >

                ${signalName(
                    stock.signal
                )}

            </span>

        </div>


        <div class="detail-grid">

            ${detail(
                "MaT-R Skoru",
                stock.matrScore
            )}

            ${detail(
                "Fiyat",
                formatNumber(
                    stock.price,
                    4
                ) + " ₺"
            )}

            ${detail(
                "Durum",
                stock.positionStatus
            )}

            ${detail(
                "Trend",
                stock.trend
            )}

            ${detail(
                "MACD",
                stock.macdState
            )}

            ${detail(
                "EMA 34",
                formatNumber(
                    stock.ema34,
                    4
                )
            )}

            ${detail(
                "SMA 34",
                formatNumber(
                    stock.sma34,
                    4
                )
            )}

            ${detail(
                "MACD",
                formatNumber(
                    stock.macd,
                    6
                )
            )}

            ${detail(
                "MACD Sinyal",
                formatNumber(
                    stock.macdSignal,
                    6
                )
            )}

            ${detail(
                "Histogram",
                formatNumber(
                    stock.histogram,
                    6
                )
            )}

            ${detail(
                "ATR",
                formatNumber(
                    stock.atr,
                    4
                )
            )}

            ${detail(
                "ATR %",
                formatNumber(
                    stock.atrPercent,
                    2
                ) + "%"
            )}

            ${detail(
                "RSI",
                formatNumber(
                    stock.rsi,
                    2
                )
            )}

            ${detail(
                "ADX",
                formatNumber(
                    stock.adx,
                    2
                )
            )}

            ${detail(
                "Hacim Oranı",
                formatNumber(
                    stock.volumeRatio,
                    2
                ) + "x"
            )}

            ${detail(
                "21 Gün",
                formatPercent(
                    stock.ret21
                )
            )}

            ${detail(
                "3 Ay",
                formatPercent(
                    stock.ret63
                )
            )}

            ${detail(
                "6 Ay",
                formatPercent(
                    stock.ret126
                )
            )}

            ${detail(
                "52H Zirve",
                formatNumber(
                    stock.high52,
                    4
                )
            )}

            ${detail(
                "52H Dip",
                formatNumber(
                    stock.low52,
                    4
                )
            )}

            ${detail(
                "Giriş Fiyatı",
                entry
            )}

            ${detail(
                "Kâr Al 1",
                tp1
            )}

            ${detail(
                "Kâr Al 2",
                tp2
            )}

            ${detail(
                "Zarar Kes",
                stop
            )}

            ${detail(
                "Giriş ATR",
                stock.entryATR !== null
                    ? formatNumber(
                        stock.entryATR,
                        4
                    )
                    : "-"
            )}

            ${detail(
                "Sinyal Tarihi",
                stock.entryDate || "-"
            )}

        </div>


        ${
            stock.signals.length
                ? `
                    <div
                        style="
                            margin-top:15px;
                            color:#94a3b8;
                        "
                    >

                        ${stock.signals
                            .map(
                                x =>
                                    `<span
                                        class="signal positive"
                                        style="margin:3px"
                                    >
                                        ${escapeHTML(x)}
                                    </span>`
                            )
                            .join("")
                        }

                    </div>
                `
                : ""
        }

    `;


    modal.style.display =
        "block";
}


// ============================================================
// DETAY ELEMANI
// ============================================================

function detail(title, value) {

    return `

        <div class="detail">

            <small>
                ${escapeHTML(title)}
            </small>

            <strong>
                ${escapeHTML(value)}
            </strong>

        </div>
    `;
}


// ============================================================
// MODAL KAPAT
// ============================================================

function closeModal() {

    const modal =
        document.getElementById(
            "stockModal"
        );


    if (modal) {

        modal.style.display =
            "none";
    }
}


// ============================================================
// SAYI
// ============================================================

function updateCount() {

    const count =
        document.getElementById(
            "stockCount"
        );


    if (count) {

        count.textContent =
            `${filteredStocks.length} hisse`;
    }
}


// ============================================================
// EVENTLER
// ============================================================

if (searchInput) {

    searchInput.addEventListener(
        "input",
        applyFilters
    );
}


if (signalFilter) {

    signalFilter.addEventListener(
        "change",
        applyFilters
    );
}


if (sortSelect) {

    sortSelect.addEventListener(
        "change",
        sortStocks
    );
}


const modal =
    document.getElementById(
        "stockModal"
    );


if (modal) {

    modal.addEventListener(
        "click",
        event => {

            if (
                event.target === modal
            ) {

                closeModal();
            }
        }
    );
}


// ============================================================
// BAŞLAT
// ============================================================

loadData();
