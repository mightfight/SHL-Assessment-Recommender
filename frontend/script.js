/* ─── SHL Assessment Recommender — Frontend Logic ─────────────── */

const API_BASE = window.location.origin; // Same origin as backend

// ─── DOM Refs ─────────────────────────────────────────────────────
const recommendBtn = document.getElementById("recommend-btn");
const btnText = document.querySelector(".btn-text");
const btnSpinner = document.getElementById("btn-spinner");
const btnArrow = document.querySelector(".btn-arrow");
const queryInput = document.getElementById("query-input");
const urlInput = document.getElementById("url-input");
const errorBanner = document.getElementById("error-banner");
const errorText = document.getElementById("error-text");
const resultsSection = document.getElementById("results-section");
const resultsTbody = document.getElementById("results-tbody");
const resultsCount = document.getElementById("results-count");
const resultsMeta = document.getElementById("results-meta");
const typeSummary = document.getElementById("type-summary");

let activeTab = "text"; // "text" or "url"

// ─── Test type metadata ───────────────────────────────────────────
const TYPE_META = {
    "Ability & Aptitude": { code: "A", cls: "chip-A" },
    "Biodata & Situational Judgement": { code: "B", cls: "chip-B" },
    "Competencies": { code: "C", cls: "chip-C" },
    "Development & 360": { code: "D", cls: "chip-D" },
    "Assessment Exercises": { code: "E", cls: "chip-E" },
    "Knowledge & Skills": { code: "K", cls: "chip-K" },
    "Personality & Behavior": { code: "P", cls: "chip-P" },
    "Personality & Behaviour": { code: "P", cls: "chip-P" },
    "Simulations": { code: "S", cls: "chip-S" },
};

function getTypeMeta(typeName) {
    return TYPE_META[typeName] || { code: typeName?.[0] || "?", cls: "chip-K" };
}

// ─── Tabs ─────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(tab => {
    tab.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        activeTab = tab.dataset.tab;
        document.getElementById("input-text-panel").classList.toggle("active", activeTab === "text");
        document.getElementById("input-url-panel").classList.toggle("active", activeTab === "url");
    });
});

// ─── Sample query chips ───────────────────────────────────────────
document.querySelectorAll(".sample-chip").forEach(chip => {
    chip.addEventListener("click", () => {
        // Switch to text tab
        document.getElementById("tab-text").click();
        queryInput.value = chip.dataset.q;
        queryInput.focus();
    });
});

// ─── Recommend button ─────────────────────────────────────────────
recommendBtn.addEventListener("click", fetchRecommendations);

// Allow Enter in URL input to trigger
urlInput.addEventListener("keydown", e => { if (e.key === "Enter") fetchRecommendations(); });

// Ctrl+Enter in textarea
queryInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) fetchRecommendations();
});

// ─── Main fetch logic ─────────────────────────────────────────────
async function fetchRecommendations() {
    const query = activeTab === "text"
        ? queryInput.value.trim()
        : urlInput.value.trim();

    if (!query) {
        showError("Please enter a job description, query, or URL.");
        return;
    }

    setLoading(true);
    hideError();
    hideResults();

    try {
        const startTime = Date.now();
        const resp = await fetch(`${API_BASE}/recommend`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query }),
        });

        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.detail || `Server error (${resp.status})`);
        }

        const data = await resp.json();
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        renderResults(data.recommended_assessments, elapsed);

    } catch (err) {
        showError(err.message || "Failed to reach the recommendation API. Is the server running?");
    } finally {
        setLoading(false);
    }
}

// ─── Render results ───────────────────────────────────────────────
function renderResults(assessments, elapsed) {
    if (!assessments || assessments.length === 0) {
        showError("No assessments found for this query. Try rephrasing your input.");
        return;
    }

    // Header
    resultsCount.textContent = `${assessments.length} assessment${assessments.length !== 1 ? "s" : ""} recommended`;
    resultsMeta.textContent = `⚡ ${elapsed}s`;

    // Test-type summary chips
    const typeGroups = {};
    assessments.forEach(a => {
        (a.test_type || []).forEach(t => {
            typeGroups[t] = (typeGroups[t] || 0) + 1;
        });
    });

    typeSummary.innerHTML = Object.entries(typeGroups)
        .sort((a, b) => b[1] - a[1])
        .map(([type, count]) => {
            const meta = getTypeMeta(type);
            return `<span class="type-chip ${meta.cls}">${meta.code}: ${type} (${count})</span>`;
        }).join("");

    // Table rows
    resultsTbody.innerHTML = "";
    assessments.forEach((a, i) => {
        const tr = document.createElement("tr");
        tr.style.animationDelay = `${i * 50}ms`;

        // Test type badges
        const badges = (a.test_type || []).map(t => {
            const meta = getTypeMeta(t);
            return `<span class="type-badge ${meta.cls}">${meta.code}: ${t}</span>`;
        }).join("");

        // Support indicators
        const remoteHtml = a.remote_support === "Yes"
            ? `<span class="support-yes">✓ Yes</span>`
            : `<span class="support-no">— No</span>`;
        const adaptiveHtml = a.adaptive_support === "Yes"
            ? `<span class="support-yes">✓ Yes</span>`
            : `<span class="support-no">— No</span>`;

        // Duration
        const dur = a.duration
            ? `<span class="duration-cell">${a.duration}<span> min</span></span>`
            : `<span class="support-no">—</span>`;

        // Description (truncate)
        const desc = (a.description || "").slice(0, 160) + (a.description?.length > 160 ? "…" : "");

        tr.innerHTML = `
      <td><div class="rank-num">${i + 1}</div></td>
      <td>
        <a class="assessment-link" href="${escHtml(a.url)}" target="_blank" rel="noopener">
          ${escHtml(a.name)}
          <svg style="display:inline;margin-left:5px;vertical-align:middle;opacity:0.5" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
      </td>
      <td><div class="type-badges">${badges || "—"}</div></td>
      <td>${dur}</td>
      <td>${remoteHtml}</td>
      <td>${adaptiveHtml}</td>
      <td><p class="desc-short">${escHtml(desc)}</p></td>
    `;
        resultsTbody.appendChild(tr);
    });

    resultsSection.style.display = "block";
    resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ─── UI helpers ───────────────────────────────────────────────────
function setLoading(loading) {
    recommendBtn.disabled = loading;
    btnText.textContent = loading ? "Analyzing…" : "Get Recommendations";
    btnSpinner.style.display = loading ? "inline-flex" : "none";
    btnArrow.style.display = loading ? "none" : "inline";
}

function showError(msg) {
    errorText.textContent = msg;
    errorBanner.style.display = "flex";
}

function hideError() {
    errorBanner.style.display = "none";
}

function hideResults() {
    resultsSection.style.display = "none";
}

function escHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
