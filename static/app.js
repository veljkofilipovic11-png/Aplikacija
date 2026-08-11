const API = "/api";
let token = localStorage.getItem("furnicom_token");
let statusPollTimer = null;

function authHeaders() {
  return { Authorization: `Bearer ${token}` };
}

async function apiFetch(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401) {
    logout();
    throw new Error("Sesija istekla, prijavi se ponovo.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Greska ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-screen").classList.remove("hidden");
  loadTenders();
  loadStatus();
  loadSettings();
}

function showLogin() {
  document.getElementById("app-screen").classList.add("hidden");
  document.getElementById("login-screen").classList.remove("hidden");
}

function logout() {
  token = null;
  localStorage.removeItem("furnicom_token");
  if (statusPollTimer) clearInterval(statusPollTimer);
  showLogin();
}

// --- Login ---
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.classList.add("hidden");
  try {
    const response = await fetch(API + "/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) throw new Error("Pogresna lozinka");
    const data = await response.json();
    token = data.token;
    localStorage.setItem("furnicom_token", token);
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
});

document.getElementById("logout-btn").addEventListener("click", logout);

// --- Tabs ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// --- Tenderi ---
function scoreBadgeClass(score) {
  if (score === null || score === undefined) return "";
  if (score >= 7) return "high";
  if (score >= 4) return "mid";
  return "";
}

async function loadTenders() {
  const listEl = document.getElementById("tenders-list");
  listEl.innerHTML = `<p class="empty-state">Ucitavanje...</p>`;
  try {
    const onlyRelevant = document.getElementById("filter-relevant").checked;
    const query = onlyRelevant ? "?min_score=7" : "";
    const tenders = await apiFetch(`/tenders${query}`);
    if (!tenders.length) {
      listEl.innerHTML = `<p class="empty-state">Nema tendera. Pokreni pretragu iz taba "Pretraga".</p>`;
      return;
    }
    listEl.innerHTML = tenders.map(renderTenderCard).join("");
  } catch (err) {
    listEl.innerHTML = `<p class="empty-state">Greska: ${err.message}</p>`;
  }
}

function renderTenderCard(t) {
  const scoreHtml =
    t.relevance_score !== null && t.relevance_score !== undefined
      ? `<span class="score-badge ${scoreBadgeClass(t.relevance_score)}">Ocena ${t.relevance_score}/10</span>`
      : `<span class="score-badge">Nije analizirano</span>`;
  return `
    <div class="tender-card">
      <p class="title">${escapeHtml(t.title || t.tender_id)}</p>
      <p class="meta">${escapeHtml(t.buyer || "")}</p>
      <p class="meta">Rok: ${escapeHtml(t.deadline || "nepoznat")} · CPV ${escapeHtml(t.cpv_code || "")}</p>
      <p class="meta">${scoreHtml}</p>
      ${t.detail_url ? `<a class="link" href="${t.detail_url}" target="_blank" rel="noopener">Otvori tender na portalu &rarr;</a>` : ""}
    </div>
  `;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

document.getElementById("refresh-tenders").addEventListener("click", loadTenders);
document.getElementById("filter-relevant").addEventListener("change", loadTenders);

// --- Pretraga / status ---
async function loadStatus() {
  try {
    const data = await apiFetch("/status");
    document.getElementById("run-status").textContent = data.is_running ? "U toku..." : "Neaktivno";
    document.getElementById("tender-count").textContent = data.tender_count;
    if (data.last_run) {
      document.getElementById("last-run-time").textContent = new Date(data.last_run.started_at).toLocaleString("sr-RS");
      document.getElementById("last-run-counts").textContent =
        `${data.last_run.tenders_found ?? 0} / ${data.last_run.new_tenders ?? 0}`;
    }
    const runBtn = document.getElementById("run-btn");
    runBtn.disabled = data.is_running;
    if (data.is_running && !statusPollTimer) {
      statusPollTimer = setInterval(async () => {
        const s = await apiFetch("/status");
        if (!s.is_running) {
          clearInterval(statusPollTimer);
          statusPollTimer = null;
          loadStatus();
          loadTenders();
        }
      }, 4000);
    }
  } catch (err) {
    document.getElementById("run-message").textContent = err.message;
  }
}

document.getElementById("run-btn").addEventListener("click", async () => {
  const msgEl = document.getElementById("run-message");
  msgEl.textContent = "";
  try {
    await apiFetch("/run", { method: "POST" });
    msgEl.textContent = "Pretraga pokrenuta u pozadini...";
    loadStatus();
  } catch (err) {
    msgEl.textContent = err.message;
  }
});

// --- Podesavanja ---
async function loadSettings() {
  try {
    const settings = await apiFetch("/settings");
    const lines = Object.entries(settings.cpv_codes || {}).map(([code, name]) => `${code} - ${name}`);
    document.getElementById("cpv-codes").value = lines.join("\n");
    document.getElementById("relevance-threshold").value = settings.relevance_threshold ?? 7;
    document.getElementById("paused-toggle").checked = !!settings.paused;
  } catch (err) {
    document.getElementById("settings-message").textContent = err.message;
  }
}

function parseCpvTextarea(text) {
  const result = {};
  text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      const [code, ...rest] = line.split("-");
      if (code && code.trim()) {
        result[code.trim()] = rest.join("-").trim();
      }
    });
  return result;
}

document.getElementById("save-settings-btn").addEventListener("click", async () => {
  const msgEl = document.getElementById("settings-message");
  msgEl.textContent = "";
  try {
    const cpv_codes = parseCpvTextarea(document.getElementById("cpv-codes").value);
    const relevance_threshold = parseInt(document.getElementById("relevance-threshold").value, 10);
    const paused = document.getElementById("paused-toggle").checked;
    await apiFetch("/settings", {
      method: "PUT",
      body: JSON.stringify({ cpv_codes, relevance_threshold, paused }),
    });
    msgEl.textContent = "Sacuvano.";
  } catch (err) {
    msgEl.textContent = err.message;
  }
});

// --- Init ---
if (token) {
  showApp();
} else {
  showLogin();
}
