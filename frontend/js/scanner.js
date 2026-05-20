/**
 * PlantPal Leaf Scanner Module (v3.0)
 * Handles image upload, preview, scan API call, and result rendering.
 * All diagnosis logic lives in the backend — this file is purely UI + API glue.
 */
(function () {
  "use strict";

  const SESSION_KEY = "plantpal_session_id";
  const SCAN_HISTORY_KEY = "plantpal_scan_history";
  const MAX_HISTORY = 10;

  let _imageFile = null;
  let _imageBase64 = null;
  let _lastResult = null;

  function $id(id) { return document.getElementById(id); }

  function getSessionId() {
    return sessionStorage.getItem(SESSION_KEY) ||
      (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2));
  }

  // ── Image handling ──────────────────────────────────────────────────
  function setImage(file) {
    if (!file || !file.type.startsWith("image/")) {
      showError("Please upload a valid image file (JPG, PNG, or WebP).");
      return;
    }
    if (file.size > 16 * 1024 * 1024) {
      showError("Image is too large. Please use an image smaller than 16 MB.");
      return;
    }

    _imageFile = file;
    const reader = new FileReader();
    reader.onload = (e) => {
      _imageBase64 = e.target.result.split(",")[1];
      const preview = $id("preview-img");
      if (preview) preview.src = e.target.result;
      $id("drop-zone").style.display = "none";
      $id("preview-container").style.display = "block";
      const scanBtn = $id("scan-btn");
      if (scanBtn) scanBtn.disabled = false;
    };
    reader.readAsDataURL(file);
  }

  function removeImage() {
    _imageFile = null;
    _imageBase64 = null;
    $id("drop-zone").style.display = "";
    $id("preview-container").style.display = "none";
    const scanBtn = $id("scan-btn");
    if (scanBtn) scanBtn.disabled = true;
    const fileInput = $id("file-input");
    if (fileInput) fileInput.value = "";
    showPlaceholder();
  }

  // ── Result rendering ────────────────────────────────────────────────
  const LABEL_CONFIG = {
    "Healthy":  { cls: "badge-healthy",  barCls: "bar-healthy",  icon: "💚" },
    "Fungal":   { cls: "badge-fungal",   barCls: "bar-fungal",   icon: "🍄" },
    "Wilting":  { cls: "badge-wilting",  barCls: "bar-wilting",  icon: "🥺" },
    "Scorch":   { cls: "badge-scorch",   barCls: "bar-scorch",   icon: "🔥" },
  };

  function showPlaceholder() {
    $id("result-placeholder").style.display = "";
    $id("result-content").style.display = "none";
    $id("scan-loading").style.display = "none";
    $id("scan-error").style.display = "none";
  }

  function showLoading() {
    $id("result-placeholder").style.display = "none";
    $id("result-content").style.display = "none";
    $id("scan-loading").style.display = "";
    $id("scan-error").style.display = "none";
  }

  function showError(msg) {
    $id("result-placeholder").style.display = "none";
    $id("result-content").style.display = "none";
    $id("scan-loading").style.display = "none";
    $id("scan-error").style.display = "";
    const errText = $id("scan-error-text");
    if (errText) errText.textContent = msg || "Something went wrong. Please try again.";
  }

  function showResult(data) {
    _lastResult = data;
    $id("result-placeholder").style.display = "none";
    $id("scan-loading").style.display = "none";
    $id("scan-error").style.display = "none";
    $id("result-content").style.display = "";

    const label = data.label || "Unknown";
    const conf = data.confidence || 0;
    const cfg = LABEL_CONFIG[label] || { cls: "", barCls: "", icon: "🌿" };

    // Badge
    const badge = $id("result-badge");
    if (badge) {
      badge.className = `result-badge ${cfg.cls}`;
      badge.textContent = `${cfg.icon} ${label}`;
    }

    // Confidence
    const confEl = $id("result-conf");
    if (confEl) confEl.textContent = `${Math.round(conf * 100)}%`;

    // Confidence bar
    const bar = $id("confidence-bar");
    if (bar) {
      bar.className = `confidence-bar ${cfg.barCls}`;
      bar.style.width = "0%";
      setTimeout(() => { bar.style.width = `${Math.round(conf * 100)}%`; }, 50);
    }

    // Class breakdown
    const breakdown = $id("result-breakdown");
    if (breakdown && data.all_scores) {
      const sorted = Object.entries(data.all_scores).sort((a, b) => b[1] - a[1]);
      breakdown.innerHTML = sorted.map(([cls, score]) => {
        const pct = Math.round(score * 100);
        return `<div class="breakdown-row">
          <span style="min-width:80px;font-weight:${cls === label ? '700' : '400'}">${cls}</span>
          <div class="breakdown-bar-wrap">
            <div class="breakdown-bar-fill" style="width:${pct}%;background:${cls === label ? '#16a34a' : '#cbd5e1'}"></div>
          </div>
          <span style="min-width:42px;text-align:right;font-weight:${cls === label ? '700' : '400'}">${pct}%</span>
        </div>`;
      }).join("");
    }

    // Plant species (Plant.id)
    const plantEl = $id("result-plant");
    if (plantEl) {
      if (data.plant_name) {
        const pct = Math.round((data.plant_confidence || 0) * 100);
        plantEl.textContent = `Species: ${data.plant_name} (${pct}% match)`;
        plantEl.style.display = "";
      } else {
        plantEl.style.display = "none";
      }
    }

    // Diagnosis
    const diagBox = $id("result-diagnosis");
    if (diagBox && data.diagnosis) diagBox.textContent = data.diagnosis;

    // Multi-modal note
    const mmBox = $id("multi-modal-box");
    const mmText = $id("multi-modal-text");
    if (mmBox && mmText && data.multi_modal) {
      mmText.textContent = data.multi_modal;
      mmBox.style.display = "";
    } else if (mmBox) {
      mmBox.style.display = "none";
    }

    // Weather risks
    const risksEl = $id("result-risks");
    if (risksEl && Array.isArray(data.weather_risks) && data.weather_risks.length) {
      const riskCls = { critical: "risk-critical", high: "risk-high", moderate: "risk-moderate" };
      risksEl.innerHTML = data.weather_risks
        .filter(r => r.level !== "low")
        .map(r => `<div class="risk-item ${riskCls[r.level] || 'risk-moderate'}"><span>⚠️</span><span>${r.message}</span></div>`)
        .join("");
    } else if (risksEl) {
      risksEl.innerHTML = "";
    }

    // Simulated badge
    if (data.fallback) {
      const notice = document.createElement("div");
      notice.style.cssText = "font-size:.8rem;color:#94a3b8;margin-top:8px;font-style:italic;";
      notice.textContent = "Plant.id fallback (local model was not used for this scan).";
      $id("result-content").appendChild(notice);
    }

    // Share with chatbot context
    if (window.PlantPalChat) {
      window.PlantPalChat.setScan({ label: data.label, confidence: data.confidence });
    }

    // Save to history
    saveToHistory({ label, confidence: conf, time: new Date().toLocaleTimeString() });
    renderHistory();
  }

  // ── Scan history ────────────────────────────────────────────────────
  function saveToHistory(entry) {
    try {
      const history = JSON.parse(sessionStorage.getItem(SCAN_HISTORY_KEY) || "[]");
      history.unshift(entry);
      sessionStorage.setItem(SCAN_HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
    } catch {}
  }

  function renderHistory() {
    const histEl = $id("scan-history");
    if (!histEl) return;
    const history = JSON.parse(sessionStorage.getItem(SCAN_HISTORY_KEY) || "[]");
    if (!history.length) { histEl.innerHTML = ""; return; }
    const cfg = LABEL_CONFIG;
    histEl.innerHTML = `<div class="history-title">Recent Scans</div>` +
      history.map(h => {
        const c = cfg[h.label] || { icon: "🌿" };
        return `<div class="history-card">
          <span class="history-label">${c.icon} ${h.label}</span>
          <span class="history-time">${Math.round(h.confidence * 100)}% · ${h.time}</span>
        </div>`;
      }).join("");
  }

  // ── API call ────────────────────────────────────────────────────────
  async function runScan() {
    if (!_imageBase64) { showError("No image selected."); return; }

    const scanBtn = $id("scan-btn");
    if (scanBtn) scanBtn.disabled = true;
    showLoading();

    const weather = window.PlantPalWeather ? window.PlantPalWeather.get() : null;
    const plantSelect = $id("scan-plant-select");
    const plantName = plantSelect ? plantSelect.value : "";

    const payload = {
      image_base64: _imageBase64,
      session_id: getSessionId(),
      plant_name: plantName,
      weather: weather,
    };

    try {
      const resp = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(20000),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || `Server error (${resp.status})`);
      }

      const data = await resp.json();
      showResult(data);

    } catch (err) {
      showError(`Scan failed: ${err.message}. Ensure the backend is running.`);
      console.error("PlantPal scan error:", err);
    } finally {
      if (scanBtn) scanBtn.disabled = !_imageBase64;
    }
  }

  // ── Ask AI button ───────────────────────────────────────────────────
  function setupAskAiButton() {
    const btn = $id("ask-ai-btn");
    if (!btn) return;
    btn.addEventListener("click", () => {
      if (!_lastResult) return;
      const label = _lastResult.label;
      const conf = Math.round((_lastResult.confidence || 0) * 100);
      const msg = `My scan shows ${label} at ${conf}% confidence. What should I do?`;
      if (window.PlantPalChat) {
        window.PlantPalChat.open();
        setTimeout(() => window.PlantPalChat.send(msg), 400);
      }
    });
  }

  // ── Init ────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    const dropZone  = $id("drop-zone");
    const fileInput = $id("file-input");
    const dropLink  = $id("drop-link");
    const removeBtn = $id("remove-img");
    const scanBtn   = $id("scan-btn");
    const retryBtn  = $id("retry-btn");

    if (!dropZone) return;  // Not on scanner page

    dropLink && dropLink.addEventListener("click", () => fileInput && fileInput.click());
    dropZone.addEventListener("click", () => fileInput && fileInput.click());
    fileInput && fileInput.addEventListener("change", (e) => {
      if (e.target.files[0]) setImage(e.target.files[0]);
    });

    // Drag & drop
    ["dragover", "dragenter"].forEach(evt => {
      dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
    });
    ["dragleave", "drop"].forEach(evt => {
      dropZone.addEventListener(evt, (e) => { e.preventDefault(); dropZone.classList.remove("drag-over"); });
    });
    dropZone.addEventListener("drop", (e) => {
      const file = e.dataTransfer.files[0];
      if (file) setImage(file);
    });

    removeBtn && removeBtn.addEventListener("click", removeImage);
    scanBtn && scanBtn.addEventListener("click", runScan);
    retryBtn && retryBtn.addEventListener("click", () => { showPlaceholder(); });

    setupAskAiButton();
    renderHistory();
  });
})();
