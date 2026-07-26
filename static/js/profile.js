/* Profile dashboard — vanilla JS. Renders category/monthly charts and a
   transaction list from data embedded by the server, with client-side
   filtering by time range and category. No external libraries. */
(function () {
    "use strict";

    const dataEl = document.getElementById("expense-data");
    if (!dataEl) return;

    let ALL = [];
    try {
        ALL = JSON.parse(dataEl.textContent) || [];
    } catch (e) {
        ALL = [];
    }

    const CATEGORIES = [
        "Food", "Transport", "Bills", "Health",
        "Entertainment", "Shopping", "Other",
    ];

    // Pull the category palette straight from the CSS variables so colours
    // live in one place (profile.css) rather than being hardcoded here.
    const rootStyle = getComputedStyle(document.documentElement);
    const COLORS = {};
    CATEGORIES.forEach(function (c) {
        const v = rootStyle.getPropertyValue("--cat-" + c.toLowerCase()).trim();
        COLORS[c] = v || "#888888";
    });

    // ---- State ----
    let rangeMonths = null;   // null = all time (used when no custom range)
    let activeCategory = null; // null = all categories
    let customFrom = null;    // Date (local midnight) or null
    let customTo = null;      // Date (local midnight) or null

    // ---- Helpers ----
    const SVG_NS = "http://www.w3.org/2000/svg";
    const MONTH_NAMES = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];

    function fmtCurrency(n) {
        return "₹" + Number(n).toLocaleString("en-IN", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
    }

    function fmtCompact(n) {
        return "₹" + Math.round(Number(n)).toLocaleString("en-IN");
    }

    // Re-trigger a CSS animation on a persistent element by removing the
    // class, forcing a reflow, then re-adding it.
    function pulse(el, cls) {
        if (!el) return;
        el.classList.remove(cls);
        void el.offsetWidth; // force reflow so the animation restarts
        el.classList.add(cls);
    }

    // Parse a "YYYY-MM-DD" string (date-input value or expense date) into a
    // local Date at midnight, so range comparisons are timezone-safe.
    function toDay(val) {
        if (!val) return null;
        const s = String(val).slice(0, 10).split("-");
        if (s.length !== 3) return null;
        return new Date(Number(s[0]), Number(s[1]) - 1, Number(s[2]));
    }

    function customRangeActive() {
        return customFrom !== null || customTo !== null;
    }

    // First-of-month for the earliest expense (fallback: current month).
    function earliestExpenseMonth() {
        const now = new Date();
        if (ALL.length === 0) return new Date(now.getFullYear(), now.getMonth(), 1);
        let earliest = now;
        ALL.forEach(function (e) {
            const d = toDay(e.date);
            if (d && d < earliest) earliest = d;
        });
        return new Date(earliest.getFullYear(), earliest.getMonth(), 1);
    }

    function rangeCutoff() {
        if (rangeMonths === null) return null;
        const d = new Date();
        d.setHours(0, 0, 0, 0);
        d.setMonth(d.getMonth() - rangeMonths);
        return d;
    }

    // Set filtered by time only (used by the donut so it always shows the
    // full category split for the period).
    function timeFilteredSet() {
        // An explicit from/to range overrides the month pills.
        if (customRangeActive()) {
            return ALL.filter(function (e) {
                const d = toDay(e.date);
                if (!d) return false;
                if (customFrom && d < customFrom) return false;
                if (customTo && d > customTo) return false;
                return true;
            });
        }
        const cutoff = rangeCutoff();
        if (!cutoff) return ALL.slice();
        return ALL.filter(function (e) {
            return new Date(e.date) >= cutoff;
        });
    }

    // Set filtered by time AND active category (stats, bars, table).
    function fullFilteredSet() {
        const base = timeFilteredSet();
        if (!activeCategory) return base;
        return base.filter(function (e) {
            return e.category === activeCategory;
        });
    }

    function sumBy(rows, keyFn) {
        const out = {};
        rows.forEach(function (r) {
            const k = keyFn(r);
            out[k] = (out[k] || 0) + Number(r.amount);
        });
        return out;
    }

    // ---- Renderers ----
    function renderStats(rows) {
        const total = rows.reduce(function (s, r) { return s + Number(r.amount); }, 0);
        const count = rows.length;
        const avg = count ? total / count : 0;

        const byCat = sumBy(rows, function (r) { return r.category; });
        let top = "—";
        let topVal = -1;
        Object.keys(byCat).forEach(function (c) {
            if (byCat[c] > topVal) { topVal = byCat[c]; top = c; }
        });

        document.getElementById("stat-total").textContent = fmtCurrency(total);
        document.getElementById("stat-count").textContent = String(count);
        document.getElementById("stat-avg").textContent = fmtCurrency(avg);
        document.getElementById("stat-top").textContent = count ? top : "—";

        document.querySelectorAll(".stat-value").forEach(function (el) {
            pulse(el, "pop");
        });
    }

    function renderDonut(rows) {
        const svg = document.getElementById("donut-chart");
        const legend = document.getElementById("donut-legend");
        const empty = document.getElementById("donut-empty");
        const totalEl = document.getElementById("donut-total");
        svg.innerHTML = "";
        legend.innerHTML = "";

        const byCat = sumBy(rows, function (r) { return r.category; });
        const total = Object.keys(byCat).reduce(function (s, c) { return s + byCat[c]; }, 0);
        totalEl.textContent = fmtCompact(total);

        if (total <= 0) {
            empty.hidden = false;
            svg.hidden = true;
            return;
        }
        empty.hidden = true;
        svg.hidden = false;

        const size = 220, stroke = 30;
        const r = (size - stroke) / 2;
        const cx = size / 2, cy = size / 2;
        const C = 2 * Math.PI * r;

        // Ordered by fixed category order for stable colours.
        const segments = CATEGORIES
            .filter(function (c) { return byCat[c] > 0; })
            .map(function (c) { return { cat: c, value: byCat[c] }; });

        let offset = 0;
        segments.forEach(function (seg) {
            const frac = seg.value / total;
            const len = frac * C;
            const circle = document.createElementNS(SVG_NS, "circle");
            circle.setAttribute("cx", cx);
            circle.setAttribute("cy", cy);
            circle.setAttribute("r", r);
            circle.setAttribute("fill", "none");
            circle.setAttribute("stroke", COLORS[seg.cat]);
            circle.setAttribute("stroke-width", stroke);
            circle.setAttribute("stroke-dasharray", len + " " + (C - len));
            circle.setAttribute("stroke-dashoffset", -offset);
            circle.setAttribute("transform", "rotate(-90 " + cx + " " + cy + ")");
            circle.setAttribute("data-cat", seg.cat);
            if (activeCategory && activeCategory !== seg.cat) {
                circle.classList.add("is-dim");
            }
            circle.addEventListener("click", function () {
                toggleCategory(seg.cat);
            });
            const title = document.createElementNS(SVG_NS, "title");
            title.textContent = seg.cat + " — " + fmtCurrency(seg.value)
                + " (" + (frac * 100).toFixed(1) + "%)";
            circle.appendChild(title);
            svg.appendChild(circle);
            offset += len;
        });

        // Spin + scale the whole donut in on every redraw.
        pulse(svg, "animate-in");

        // Legend
        segments.forEach(function (seg, i) {
            const frac = seg.value / total;
            const li = document.createElement("li");
            li.className = "legend-item"
                + (activeCategory === seg.cat ? " is-active" : "");
            li.style.animationDelay = (i * 0.04) + "s";
            li.addEventListener("click", function () { toggleCategory(seg.cat); });

            const sw = document.createElement("span");
            sw.className = "legend-swatch";
            sw.style.backgroundColor = COLORS[seg.cat];

            const name = document.createElement("span");
            name.className = "legend-name";
            name.textContent = seg.cat;

            const pct = document.createElement("span");
            pct.className = "legend-pct";
            pct.textContent = (frac * 100).toFixed(0) + "%";

            const amt = document.createElement("span");
            amt.className = "legend-amount";
            amt.textContent = fmtCurrency(seg.value);

            li.appendChild(sw);
            li.appendChild(name);
            li.appendChild(pct);
            li.appendChild(amt);
            legend.appendChild(li);
        });
    }

    function renderBars(rows) {
        const chart = document.getElementById("bar-chart");
        const empty = document.getElementById("bar-empty");
        chart.innerHTML = "";

        // Decide the [startMonth, endMonth] window to display.
        const now = new Date();
        now.setDate(1);
        now.setHours(0, 0, 0, 0);

        let startMonth, endMonth;
        if (customRangeActive()) {
            startMonth = customFrom
                ? new Date(customFrom.getFullYear(), customFrom.getMonth(), 1)
                : earliestExpenseMonth();
            endMonth = customTo
                ? new Date(customTo.getFullYear(), customTo.getMonth(), 1)
                : now;
        } else if (rangeMonths !== null) {
            endMonth = now;
            startMonth = new Date(now.getFullYear(), now.getMonth() - (rangeMonths - 1), 1);
        } else {
            // All-time: span from the earliest expense to now.
            endMonth = now;
            startMonth = rows.length ? earliestExpenseMonth() : now;
        }

        let monthsToShow = (endMonth.getFullYear() - startMonth.getFullYear()) * 12
            + (endMonth.getMonth() - startMonth.getMonth()) + 1;
        monthsToShow = Math.max(1, Math.min(monthsToShow, 24));

        // Build the ordered list of month buckets, ending at endMonth.
        const buckets = [];
        for (let i = monthsToShow - 1; i >= 0; i--) {
            const d = new Date(endMonth.getFullYear(), endMonth.getMonth() - i, 1);
            const key = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
            buckets.push({ key: key, label: MONTH_NAMES[d.getMonth()], total: 0 });
        }
        const idx = {};
        buckets.forEach(function (b, i) { idx[b.key] = i; });

        rows.forEach(function (e) {
            const key = String(e.date).slice(0, 7);
            if (key in idx) buckets[idx[key]].total += Number(e.amount);
        });

        const max = buckets.reduce(function (m, b) { return Math.max(m, b.total); }, 0);

        if (max <= 0) {
            empty.hidden = false;
            chart.hidden = true;
            return;
        }
        empty.hidden = true;
        chart.hidden = false;

        buckets.forEach(function (b, i) {
            const col = document.createElement("div");
            col.className = "bar-col";

            const track = document.createElement("div");
            track.className = "bar-track";

            const fill = document.createElement("div");
            fill.className = "bar-fill";
            // Start collapsed; the CSS height transition animates the rise.
            // Stagger via transition-delay (capped so long spans stay snappy).
            fill.style.height = "0%";
            fill.style.transitionDelay = (Math.min(i, 12) * 0.045) + "s";
            fill.dataset.targetHeight = (max ? (b.total / max) * 100 : 0);
            if (b.total > 0) fill.setAttribute("data-value", fmtCompact(b.total));

            const label = document.createElement("div");
            label.className = "bar-label";
            label.textContent = b.label;

            track.appendChild(fill);
            col.appendChild(track);
            col.appendChild(label);
            chart.appendChild(col);
        });

        // Next frame: flip each bar to its target height so the transition runs.
        requestAnimationFrame(function () {
            chart.querySelectorAll(".bar-fill").forEach(function (fill) {
                fill.style.height = fill.dataset.targetHeight + "%";
            });
        });
    }

    function renderTable(rows) {
        const body = document.getElementById("txn-body");
        const empty = document.getElementById("txn-empty");
        const countEl = document.getElementById("txn-count");
        // Server-injected URL templates, e.g. "/expenses/0/edit"; swap the id per row.
        const editUrlTemplate = body.dataset.editUrl;
        const deleteUrlTemplate = body.dataset.deleteUrl;
        body.innerHTML = "";

        countEl.textContent = rows.length ? "(" + rows.length + ")" : "";

        if (rows.length === 0) {
            empty.hidden = false;
            return;
        }
        empty.hidden = true;

        // rows already newest-first from the server.
        rows.forEach(function (e, i) {
            const tr = document.createElement("tr");
            // Stagger the fade-up, capped so long lists don't drag on.
            tr.style.animationDelay = (Math.min(i, 15) * 0.025) + "s";

            const dateTd = document.createElement("td");
            const d = new Date(e.date);
            dateTd.textContent = d.toLocaleDateString("en-IN", {
                day: "2-digit", month: "short", year: "numeric",
            });

            const catTd = document.createElement("td");
            const tag = document.createElement("span");
            tag.className = "cat-tag";
            const dot = document.createElement("span");
            dot.className = "cat-dot";
            dot.style.backgroundColor = COLORS[e.category] || "#888";
            tag.appendChild(dot);
            tag.appendChild(document.createTextNode(e.category));
            catTd.appendChild(tag);

            const descTd = document.createElement("td");
            descTd.textContent = e.description || "—";

            const amtTd = document.createElement("td");
            amtTd.className = "txn-amount";
            amtTd.textContent = fmtCurrency(e.amount);

            const actionTd = document.createElement("td");
            actionTd.className = "txn-actions";
            const editLink = document.createElement("a");
            editLink.className = "txn-edit-link";
            editLink.href = editUrlTemplate.replace("/0/", "/" + e.id + "/");
            editLink.textContent = "Edit";
            actionTd.appendChild(editLink);
            const deleteLink = document.createElement("a");
            deleteLink.className = "txn-delete-link";
            deleteLink.href = deleteUrlTemplate.replace("/0/", "/" + e.id + "/");
            deleteLink.textContent = "Delete";
            actionTd.appendChild(deleteLink);

            tr.appendChild(dateTd);
            tr.appendChild(catTd);
            tr.appendChild(descTd);
            tr.appendChild(amtTd);
            tr.appendChild(actionTd);
            body.appendChild(tr);
        });
    }

    function renderActiveFilter() {
        const wrap = document.getElementById("active-filter");
        const nameEl = document.getElementById("active-filter-name");
        if (activeCategory) {
            wrap.hidden = false;
            nameEl.textContent = activeCategory;
            const dot = COLORS[activeCategory];
            nameEl.style.color = dot;
            pulse(wrap.querySelector(".active-filter-chip"), "pop");
        } else {
            wrap.hidden = true;
            nameEl.textContent = "";
        }
    }

    function renderAll() {
        const donutSet = timeFilteredSet();
        const fullSet = fullFilteredSet();
        renderStats(fullSet);
        renderDonut(donutSet);
        renderBars(fullSet);
        renderTable(fullSet);
        renderActiveFilter();
    }

    // ---- Interactions ----
    function toggleCategory(cat) {
        activeCategory = (activeCategory === cat) ? null : cat;
        renderAll();
    }

    const dateFrom = document.getElementById("date-from");
    const dateTo = document.getElementById("date-to");
    const dateClear = document.getElementById("date-clear");

    function clearCustomRange() {
        customFrom = null;
        customTo = null;
        dateFrom.value = "";
        dateTo.value = "";
        dateClear.hidden = true;
    }

    function setRange(value) {
        clearCustomRange();
        rangeMonths = (value === "all") ? null : parseInt(value, 10);
        const pills = document.querySelectorAll("#range-pills .pill");
        pills.forEach(function (p) {
            p.classList.toggle("is-active", p.getAttribute("data-range") === value);
        });
        renderAll();
    }

    function applyDateRange() {
        customFrom = toDay(dateFrom.value);
        customTo = toDay(dateTo.value);

        // No dates left → fall back to the "All" pill.
        if (!customRangeActive()) {
            setRange("all");
            return;
        }

        // Keep from <= to so the range always makes sense.
        if (customFrom && customTo && customFrom > customTo) {
            const td = customFrom; customFrom = customTo; customTo = td;
            const tv = dateFrom.value; dateFrom.value = dateTo.value; dateTo.value = tv;
        }

        // An explicit range takes over from the month pills.
        rangeMonths = null;
        document.querySelectorAll("#range-pills .pill").forEach(function (p) {
            p.classList.remove("is-active");
        });
        dateClear.hidden = false;
        renderAll();
    }

    document.querySelectorAll("#range-pills .pill").forEach(function (pill) {
        pill.addEventListener("click", function () {
            setRange(pill.getAttribute("data-range"));
        });
    });

    dateFrom.addEventListener("change", applyDateRange);
    dateTo.addEventListener("change", applyDateRange);
    dateClear.addEventListener("click", function () {
        clearCustomRange();
        setRange("all");
    });

    document.getElementById("active-filter-clear").addEventListener("click", function () {
        activeCategory = null;
        renderAll();
    });

    // ---- Init ----
    renderAll();
})();