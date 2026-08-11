const DATA_URL = "./data.json";

let stocks = [];
let filteredStocks = [];

const tbody = document.getElementById("stockTableBody");
const searchInput = document.getElementById("search");
const signalFilter = document.getElementById("signalFilter");
const sortSelect = document.getElementById("sortSelect");
const status = document.getElementById("status");


// ======================================================
// GÜVENLİ SAYI
// ======================================================

function num(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
}


// ======================================================
// YÜZDE
// ======================================================

function percent(value) {
    const n = num(value);

    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}


// ======================================================
// FİYAT
// ======================================================

function price(value) {
    return num(value).toFixed(2);
}


// ======================================================
// HTML GÜVENLİĞİ
// ======================================================

function escapeHTML(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// ======================================================
// SİNYAL SINIFI
// ======================================================

function signalClass(signal) {

    switch (signal) {

        case "AL":
            return "buy";

        case "POZİSYONDA":
            return "position";

        case "İZLE":
            return "watch";

        case "BEKLE":
            return "wait";

        default:
            return "wait";
    }
}


// ======================================================
// SİNYAL AÇIKLAMASI
// ======================================================

function signalDescription(stock) {

    if (stock.entry) {
        return "Yeni MaT-R AL sinyali";
    }

    if (stock.position) {
        return "MaT-R pozisyonu aktif";
    }

    if (
        stock.trendPositive &&
        stock.macd > stock.macdSignal
    ) {
        return "Trend ve MACD pozitif";
    }

    if (stock.macd > stock.macdSignal) {
        return "MACD pozitif";
    }

    if (stock.trendPositive) {
        return "Trend pozitif";
    }

    return "Yeni sinyal bekleniyor";
}


// ======================================================
// SKOR RENGİ
// ======================================================

function scoreClass(score) {

    if (score >= 85)
        return "score-excellent";

    if (score >= 70)
        return "score-good";

    if (score >= 50)
        return "score-neutral";

    return "score-low";
}


// ======================================================
// MAtr VERİLERİNİ NORMALİZE ET
// ======================================================

function normalizeStock(stock) {

    return {

        ...stock,

        score: num(stock.score),

        price: num(stock.price),

        macd: num(stock.macd),

        macdSignal: num(stock.macdSignal),

        macdHistogram: num(
            stock.macdHistogram
        ),

        atr: num(stock.atr),

        rsi: num(stock.rsi),

        volumeRatio: num(
            stock.volumeRatio
        ),

        ret21: num(stock.ret21),

        volatility: num(
            stock.volatility
        ),

        distance52High: num(
            stock.distance52High
        ),

        ema8: num(stock.ema8),
        ema21: num(stock.ema21),
        ema34: num(stock.ema34),
        ema55: num(stock.ema55),
        ema89: num(stock.ema89),
        ema144: num(stock.ema144),
        ema233: num(stock.ema233),
        ema377: num(stock.ema377),

        oncu1: num(stock.oncu1),
        oncu2: num(stock.oncu2),

        tp1Price:
            stock.tp1Price === null
                ? null
                : num(stock.tp1Price),

        tp2Price:
            stock.tp2Price === null
                ? null
                : num(stock.tp2Price),

        stopPrice:
            stock.stopPrice === null
                ? null
                : num(stock.stopPrice),

        lastEntryPrice:
            stock.lastEntryPrice === null
                ? null
                : num(stock.lastEntryPrice),

        entry: Boolean(stock.entry),

        position: Boolean(stock.position),

        trendPositive:
            Boolean(stock.trendPositive),

        tp1Hit:
            Boolean(stock.tp1Hit),

        tp2Hit:
            Boolean(stock.tp2Hit)
    };
}


// ======================================================
// TABLOYU ÇİZ
// ======================================================

function render() {

    if (!tbody)
        return;

    const search =
        searchInput?.value
            ?.toLowerCase()
            .trim() || "";

    const signal =
        signalFilter?.value || "";

    const sort =
        sortSelect?.value || "score";


    // --------------------------------------------------
    // FİLTRE
    // --------------------------------------------------

    filteredStocks = stocks.filter(stock => {

        const code =
            String(stock.code || "")
                .toLowerCase();

        const name =
            String(stock.name || "")
                .toLowerCase();

        const matchesSearch =
            !search ||
            code.includes(search) ||
            name.includes(search);


        let matchesSignal = true;


        if (signal === "buy") {

            matchesSignal =
                stock.signal === "AL";

        }

        else if (signal === "position") {

            matchesSignal =
                stock.signal === "POZİSYONDA";

        }

        else if (signal === "watch") {

            matchesSignal =
                stock.signal === "İZLE";

        }

        else if (signal === "wait") {

            matchesSignal =
                stock.signal === "BEKLE";

        }


        return (
            matchesSearch &&
            matchesSignal
        );
    });


    // --------------------------------------------------
    // SIRALAMA
    // --------------------------------------------------

    filteredStocks.sort((a, b) => {

        switch (sort) {

            case "score":
                return b.score - a.score;

            case "price":
                return b.price - a.price;

            case "macd":
                return b.macdHistogram -
                       a.macdHistogram;

            case "rsi":
                return b.rsi - a.rsi;

            case "volume":
                return b.volumeRatio -
                       a.volumeRatio;

            case "ret21":
                return b.ret21 - a.ret21;

            case "atr":
                return b.atr - a.atr;

            default:
                return b.score - a.score;
        }
    });


    // --------------------------------------------------
    // BOŞ SONUÇ
    // --------------------------------------------------

    if (!filteredStocks.length) {

        tbody.innerHTML = `
            <tr>
                <td colspan="11"
                    class="loading">
                    Hisse bulunamadı.
                </td>
            </tr>
        `;

        updateCount();

        return;
    }


    // --------------------------------------------------
    // TABLO
    // --------------------------------------------------

    tbody.innerHTML = filteredStocks
        .map((stock, index) => {

            return `
                <tr
                    class="stock-row"
                    onclick="showStockDetails(${index})"
                >

                    <td>
                        <strong>
                            ${index + 1}
                        </strong>
                    </td>


                    <td>

                        <div class="stock-code">
                            ${escapeHTML(stock.code)}
                        </div>

                        <div class="stock-name">
                            ${escapeHTML(
                                stock.name || ""
                            )}
                        </div>

                    </td>


                    <td>
                        <strong>
                            ${price(stock.price)}
                        </strong>
                    </td>


                    <td>

                        <span
                            class="score ${scoreClass(
                                stock.score
                            )}"
                        >
                            ${stock.score}
                        </span>

                    </td>


                    <td>

                        <span
                            class="signal ${signalClass(
                                stock.signal
                            )}"
                        >
                            ${escapeHTML(
                                stock.signal || "BEKLE"
                            )}
                        </span>

                    </td>


                    <td>
                        ${price(stock.macd)}
                    </td>


                    <td>
                        ${price(stock.macdSignal)}
                    </td>


                    <td>
                        ${price(
                            stock.macdHistogram
                        )}
                    </td>


                    <td>
                        ${price(stock.atr)}
                    </td>


                    <td>
                        ${stock.rsi.toFixed(1)}
                    </td>


                    <td>
                        ${percent(stock.ret21)}
                    </td>

                </tr>
            `;
        })
        .join("");


    updateCount();
}


// ======================================================
// ÖZET
// ======================================================

function updateSummary() {

    const total =
        document.getElementById(
            "totalStocks"
        );

    const buy =
        document.getElementById(
            "buyStocks"
        );

    const position =
        document.getElementById(
            "positionStocks"
        );

    const average =
        document.getElementById(
            "averageScore"
        );


    if (total) {

        total.textContent =
            stocks.length;
    }


    if (buy) {

        buy.textContent =
            stocks.filter(
                x => x.signal === "AL"
            ).length;
    }


    if (position) {

        position.textContent =
            stocks.filter(
                x => x.signal === "POZİSYONDA"
            ).length;
    }


    if (average) {

        const avg =
            stocks.length
                ? stocks.reduce(
                    (sum, stock) =>
                        sum + stock.score,
                    0
                ) / stocks.length
                : 0;

        average.textContent =
            avg.toFixed(1);
    }


    if (status) {

        const buyCount =
            stocks.filter(
                x => x.signal === "AL"
            ).length;

        const positionCount =
            stocks.filter(
                x => x.signal === "POZİSYONDA"
            ).length;


        status.textContent =
            `MaT-R aktif • ` +
            `${stocks.length} hisse tarandı • ` +
            `${buyCount} AL • ` +
            `${positionCount} aktif pozisyon`;
    }
}


// ======================================================
// DETAY PANELİ
// ======================================================

function showStockDetails(index) {

    const stock =
        filteredStocks[index];

    if (!stock)
        return;


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


    if (!modal || !title || !content)
        return;


    title.textContent =
        `${stock.code} • ${
            stock.name || ""
        }`;


    const stopHtml =
        stock.stopPrice !== null
            ? `${price(stock.stopPrice)} ₺`
            : "-";


    const tp1Html =
        stock.tp1Price !== null
            ? `${price(stock.tp1Price)} ₺`
            : "-";


    const tp2Html =
        stock.tp2Price !== null
            ? `${price(stock.tp2Price)} ₺`
            : "-";


    content.innerHTML = `

        <div class="detail-signal">

            <span
                class="signal ${signalClass(
                    stock.signal
                )}"
            >
                ${escapeHTML(
                    stock.signal || "BEKLE"
                )}
            </span>

            <p>
                ${escapeHTML(
                    signalDescription(stock)
                )}
            </p>

        </div>


        <div class="detail-score">

            <div>
                MaT-R SKORU
            </div>

            <strong
                class="${scoreClass(
                    stock.score
                )}"
            >
                ${stock.score}
            </strong>

        </div>


        <div class="detail-grid">


            ${detail(
                "Fiyat",
                `${price(stock.price)} ₺`
            )}


            ${detail(
                "Son AL Fiyatı",
                stock.lastEntryPrice !== null
                    ? `${price(
                        stock.lastEntryPrice
                    )} ₺`
                    : "-"
            )}


            ${detail(
                "AL Sinyal Tarihi",
                stock.lastSignalDate || "-"
            )}


            ${detail(
                "MACD",
                price(stock.macd)
            )}


            ${detail(
                "MACD Sinyal",
                price(stock.macdSignal)
            )}


            ${detail(
                "MACD Histogram",
                price(stock.macdHistogram)
            )}


            ${detail(
                "ATR",
                price(stock.atr)
            )}


            ${detail(
                "RSI",
                stock.rsi.toFixed(2)
            )}


            ${detail(
                "Hacim / 20 Gün",
                `${stock.volumeRatio.toFixed(2)}x`
            )}


            ${detail(
                "21 Gün Getiri",
                percent(stock.ret21)
            )}


            ${detail(
                "Volatilite",
                `${stock.volatility.toFixed(2)}%`
            )}


            ${detail(
                "52H Zirvesine Uzaklık",
                percent(stock.distance52High)
            )}

        </div>


        <h3>
            MaT-R İşlem Seviyeleri
        </h3>


        <div class="detail-grid">


            ${detail(
                "Kâr Alma 1",
                tp1Html
            )}


            ${detail(
                "Kâr Alma 1 %",
                `%${stock.tp1Percent || 12}`
            )}


            ${detail(
                "Kâr Alma 2",
                tp2Html
            )}


            ${detail(
                "Kâr Alma 2 %",
                `%${stock.tp2Percent || 20}`
            )}


            ${detail(
                "Zarar Kes",
                stopHtml
            )}


            ${detail(
                "ATR Çarpanı",
                `${stock.atrMultiplier || 2.2}x`
            )}

        </div>


        <h3>
            EMA Durumu
        </h3>


        <div class="detail-grid">


            ${detail(
                "EMA 8",
                price(stock.ema8)
            )}


            ${detail(
                "EMA 21",
                price(stock.ema21)
            )}


            ${detail(
                "EMA 34",
                price(stock.ema34)
            )}


            ${detail(
                "EMA 55",
                price(stock.ema55)
            )}


            ${detail(
                "EMA 89",
                price(stock.ema89)
            )}


            ${detail(
                "EMA 144",
                price(stock.ema144)
            )}


            ${detail(
                "EMA 233",
                price(stock.ema233)
            )}


            ${detail(
                "EMA 377",
                price(stock.ema377)
            )}

        </div>


        <h3>
            MaT-R Trend
        </h3>


        <div class="detail-grid">


            ${detail(
                "Trend",
                stock.trendPositive
                    ? "POZİTİF"
                    : "NEGATİF"
            )}


            ${detail(
                "Öncü EMA 34",
                price(stock.oncu1)
            )}


            ${detail(
                "Öncü SMA 34",
                price(stock.oncu2)
            )}


            ${detail(
                "MACD Durumu",
                stock.macd > stock.macdSignal
                    ? "POZİTİF"
                    : "NEGATİF"
            )}

        </div>

    `;


    modal.style.display = "block";
}


// ======================================================
// DETAY KARTI
// ======================================================

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


// ======================================================
// MODAL KAPAT
// ======================================================

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


// ======================================================
// SAYI
// ======================================================

function updateCount() {

    const element =
        document.getElementById(
            "stockCount"
        );

    if (element) {

        element.textContent =
            `${filteredStocks.length} hisse`;
    }
}


// ======================================================
// VERİYİ YÜKLE
// ======================================================

async function loadData() {

    try {

        if (status) {

            status.textContent =
                "MaT-R verileri yükleniyor...";
        }


        const response =
            await fetch(
                DATA_URL +
                "?v=" +
                Date.now()
            );


        if (!response.ok) {

            throw new Error(
                `data.json yüklenemedi. HTTP ${
                    response.status
                }`
            );
        }


        const data =
            await response.json();


        if (!Array.isArray(data)) {

            throw new Error(
                "data.json liste formatında değil."
            );
        }


        stocks =
            data
                .filter(
                    stock =>
                        stock &&
                        stock.code
                )
                .map(
                    normalizeStock
                );


        stocks.sort(
            (a, b) =>
                b.score - a.score
        );


        updateSummary();

        render();


    } catch (error) {

        console.error(
            "MaT-R veri hatası:",
            error
        );


        if (status) {

            status.innerHTML = `
                <div class="error">
                    <strong>
                        MaT-R verileri yüklenemedi.
                    </strong>

                    <br><br>

                    ${escapeHTML(
                        error.message
                    )}

                    <br><br>

                    data.json dosyasının
                    GitHub Pages üzerinde
                    bulunduğunu kontrol et.
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
                        MaT-R verileri
                        yüklenemedi.
                    </td>
                </tr>
            `;
        }
    }
}


// ======================================================
// EVENTLER
// ======================================================

if (searchInput) {

    searchInput.addEventListener(
        "input",
        render
    );
}


if (signalFilter) {

    signalFilter.addEventListener(
        "change",
        render
    );
}


if (sortSelect) {

    sortSelect.addEventListener(
        "change",
        render
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


// ESC ile kapat

document.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Escape"
        ) {

            closeModal();
        }
    }
);


// ======================================================
// BAŞLAT
// ======================================================

loadData();
