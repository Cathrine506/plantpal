/**
 * PlantPal Weather Module (v3.0)
 * Fetches weather from /api/weather and updates the dashboard + chatbot context.
 */
(function () {
  "use strict";

  let _weather = null;

  function $id(id) { return document.getElementById(id); }

  function updateCard(id, value, suffix = "") {
    const el = $id(id);
    if (el) el.textContent = value !== null && value !== undefined ? `${value}${suffix}` : "--";
  }

  function riskClass(level) {
    return { critical: "risk-critical", high: "risk-high", moderate: "risk-moderate" }[level] || "risk-moderate";
  }

  function colorVitality(score) {
    if (score >= 80) return "#22c55e";
    if (score >= 60) return "#84cc16";
    if (score >= 40) return "#f59e0b";
    return "#ef4444";
  }

  function renderWeather(data) {
    _weather = data;
    updateCard("w-temp", data.temp, "°C");
    updateCard("w-hum", data.humidity, "%");
    updateCard("w-uv", data.uvIndex);
    const vitality = data.vitality_score ?? 65;
    updateCard("w-vitality", vitality + "/100");
    const bar = $id("vitality-bar");
    if (bar) { bar.style.width = vitality + "%"; bar.style.background = colorVitality(vitality); }

    const locLabel = $id("weather-location-label");
    if (locLabel) locLabel.textContent = `Conditions for ${data.city || "your area"} · ${data.description || ""}`;

    const risksEl = $id("weather-risks");
    if (risksEl && Array.isArray(data.risks) && data.risks.length) {
      risksEl.innerHTML = data.risks.map(r =>
        `<div class="risk-item ${riskClass(r.level)}"><span>⚠️</span><span>${r.message}</span></div>`
      ).join("");
    } else if (risksEl) {
      risksEl.innerHTML = `<div class="risk-item" style="background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0"><span>✅</span><span>Conditions look good for most plants!</span></div>`;
    }

    // Share with chatbot
    if (window.PlantPalChat) window.PlantPalChat.setWeather({
      temp: data.temp, humidity: data.humidity, uvIndex: data.uvIndex,
      cloudCover: data.cloudCover, city: data.city, feels_like: data.feels_like,
    });
  }

  function loadError(msg) {
    const locLabel = $id("weather-location-label");
    if (locLabel) locLabel.textContent = msg || "Weather unavailable";
  }

  async function fetchWeather(lat, lon) {
    try {
      const resp = await fetch(`/api/weather?lat=${lat}&lon=${lon}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      renderWeather(data);
    } catch (e) {
      console.warn("PlantPal: weather fetch failed", e);
      loadError("Weather data unavailable — check your internet connection.");
    }
  }

  function init() {
    if (!$id("w-temp") && !$id("weather-section")) return;  // not on a page with weather

    const locLabel = $id("weather-location-label");
    if (locLabel) locLabel.textContent = "Detecting your location…";

    if (!navigator.geolocation) {
      loadError("Geolocation not supported — weather unavailable.");
      return;
    }

    navigator.geolocation.getCurrentPosition(
      pos => fetchWeather(pos.coords.latitude, pos.coords.longitude),
      err => loadError("Location permission denied — weather unavailable."),
      { timeout: 8000, maximumAge: 600000 }
    );
  }

  document.addEventListener("DOMContentLoaded", init);
  window.PlantPalWeather = { get: () => _weather };
})();
