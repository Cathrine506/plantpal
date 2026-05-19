/**
 * PlantPal AI Chatbot — Frontend Module (v3.0)
 *
 * Responsibilities:
 *  - All UI rendering (messages, typing, suggestions, open/close)
 *  - NO chatbot logic — all AI reasoning lives in the backend
 *  - Sends full context (plant, weather, scan, history) to POST /api/chat
 *  - Maintains conversational history in sessionStorage
 */

(function () {
  "use strict";

  const API_BASE = "";  // Same-origin — Flask serves frontend
  const SESSION_KEY = "plantpal_session_id";
  const HISTORY_KEY = "plantpal_chat_history";
  const MAX_HISTORY = 20;
  const MAX_RETRIES = 1;

  // ── State ──────────────────────────────────────────────────────────
  let _isOpen = false;
  let _isTyping = false;
  let _retries = 0;
  let _currentWeather = null;
  let _currentScan = null;

  function getSessionId() {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
      sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
  }

  function getHistory() {
    try { return JSON.parse(sessionStorage.getItem(HISTORY_KEY) || "[]"); }
    catch { return []; }
  }

  function saveHistory(history) {
    const trimmed = history.slice(-MAX_HISTORY);
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed));
  }

  function pushHistory(role, content) {
    const h = getHistory();
    h.push({ role, content });
    saveHistory(h);
  }

  // ── DOM refs (resolved lazily so this script works on all pages) ───
  function $id(id) { return document.getElementById(id); }

  // ── Open / Close ───────────────────────────────────────────────────
  function openChat() {
    const panel = $id("chatbot-panel");
    const overlay = $id("chatbot-overlay");
    if (!panel) return;
    _isOpen = true;
    panel.classList.add("open");
    if (overlay) overlay.classList.add("open");
    const input = $id("chatbot-input");
    if (input) setTimeout(() => input.focus(), 300);
    hideFabBadge();
  }

  function closeChat() {
    _isOpen = false;
    const panel = $id("chatbot-panel");
    const overlay = $id("chatbot-overlay");
    if (panel) panel.classList.remove("open");
    if (overlay) overlay.classList.remove("open");
  }

  function showFabBadge() {
    const badge = $id("fab-badge");
    if (badge && !_isOpen) badge.classList.add("visible");
  }
  function hideFabBadge() {
    const badge = $id("fab-badge");
    if (badge) badge.classList.remove("visible");
  }

  // ── Markdown renderer (lightweight) ───────────────────────────────
  function renderMarkdown(text) {
    return text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>")
      .replace(/^### (.+)$/gm, "<h4>$1</h4>")
      .replace(/^## (.+)$/gm, "<h4>$1</h4>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/(<li>[\s\S]*?<\/li>)/g, "<ul>$1</ul>")
      .replace(/^(\d+)\. (.+)$/gm, "<li>$2</li>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>")
      .replace(/^(.+)$/, "<p>$1</p>");
  }

  // ── Message rendering ──────────────────────────────────────────────
  function appendMessage(role, content, opts = {}) {
    const container = $id("chatbot-messages");
    if (!container) return;

    const msgEl = document.createElement("div");
    msgEl.className = `chat-msg ${role}`;

    const bubble = document.createElement("span");
    bubble.className = "chat-bubble";
    if (opts.error) bubble.classList.add("error-bubble");

    if (role === "assistant") {
      bubble.innerHTML = renderMarkdown(content);
      if (opts.severity && opts.severity !== "low") {
        const badge = document.createElement("div");
        badge.className = `severity-badge severity-${opts.severity}`;
        const icons = { critical: "🚨", high: "⚠️", moderate: "💛", low: "✅" };
        badge.textContent = `${icons[opts.severity] || ""} ${opts.severity.charAt(0).toUpperCase() + opts.severity.slice(1)} severity`;
        bubble.appendChild(badge);
      }
    } else {
      bubble.textContent = content;
    }

    msgEl.appendChild(bubble);
    container.appendChild(msgEl);
    scrollBottom(container);
    return msgEl;
  }

  function showTyping() {
    const container = $id("chatbot-messages");
    if (!container || _isTyping) return;
    _isTyping = true;
    const msgEl = document.createElement("div");
    msgEl.className = "chat-msg assistant";
    msgEl.id = "typing-indicator-msg";
    const bubble = document.createElement("span");
    bubble.className = "chat-bubble";
    bubble.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
    msgEl.appendChild(bubble);
    container.appendChild(msgEl);
    scrollBottom(container);
  }

  function hideTyping() {
    _isTyping = false;
    const el = $id("typing-indicator-msg");
    if (el) el.remove();
  }

  function scrollBottom(container) {
    requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
  }

  // ── Suggestion chips ───────────────────────────────────────────────
  function updateSuggestions(suggestions) {
    const box = $id("chatbot-suggestions");
    if (!box || !Array.isArray(suggestions) || suggestions.length === 0) return;
    box.innerHTML = suggestions.map(s =>
      `<button class="suggestion-chip" data-msg="${s.replace(/"/g, "&quot;")}">${s}</button>`
    ).join("");
    bindSuggestionClicks();
  }

  function bindSuggestionClicks() {
    document.querySelectorAll(".suggestion-chip").forEach(btn => {
      btn.addEventListener("click", () => sendMessage(btn.dataset.msg));
    });
  }

  // ── Status bar ─────────────────────────────────────────────────────
  function setStatus(text, active = true) {
    const el = $id("chatbot-status");
    if (!el) return;
    el.textContent = text;
    el.style.opacity = active ? "1" : "0.6";
  }

  // ── Core: send message ─────────────────────────────────────────────
  async function sendMessage(messageText) {
    const input = $id("chatbot-input");
    const sendBtn = $id("chatbot-send");
    const text = (messageText || (input && input.value) || "").trim();
    if (!text || _isTyping) return;

    if (input) input.value = "";
    if (sendBtn) sendBtn.disabled = true;

    appendMessage("user", text);
    pushHistory("user", text);
    showTyping();
    setStatus("Thinking…", false);

    const plantSelect = $id("plant-select");
    const plantName = (plantSelect && plantSelect.value) ? plantSelect.value : "";

    const payload = {
      message: text,
      session_id: getSessionId(),
      plant_name: plantName,
      conversation_history: getHistory().slice(-MAX_HISTORY),
      weather: _currentWeather || null,
      scan_result: _currentScan || null,
    };

    try {
      const resp = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(30000),
      });

      hideTyping();

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.error || `Server error (${resp.status})`);
      }

      const data = await resp.json();
      const reply = data.response || "I didn't get a proper response. Please try again.";

      appendMessage("assistant", reply, { severity: data.severity });
      pushHistory("assistant", reply);
      if (data.suggestions && data.suggestions.length) updateSuggestions(data.suggestions);
      _retries = 0;

    } catch (err) {
      hideTyping();
      if (_retries < MAX_RETRIES) {
        _retries++;
        appendMessage("assistant", "Connection hiccup — retrying…", { error: true });
        setTimeout(() => sendMessage(text), 1500);
      } else {
        _retries = 0;
        appendMessage("assistant",
          "I'm having trouble connecting right now. Make sure the PlantPal backend is running (`python backend/app.py`).",
          { error: true }
        );
      }
    } finally {
      if (sendBtn) sendBtn.disabled = false;
      setStatus("Online");
      const inp = $id("chatbot-input");
      if (inp) inp.focus();
    }
  }

  // ── Public API ─────────────────────────────────────────────────────
  window.PlantPalChat = {
    open: openChat,
    close: closeChat,
    send: sendMessage,

    setWeather(weather) { _currentWeather = weather; },
    setScan(scan) {
      _currentScan = scan;
      if (scan && scan.label) {
        showFabBadge();
        if (_isOpen) {
          setTimeout(() => appendMessage("assistant",
            `I've received your scan result: **${scan.label}** (${Math.round((scan.confidence || 0) * 100)}% confidence). What would you like to know about it?`
          ), 400);
        }
      }
    },

    clearHistory() {
      sessionStorage.removeItem(HISTORY_KEY);
      const container = $id("chatbot-messages");
      if (container) {
        container.innerHTML = `
          <div class="chat-msg assistant">
            <span class="chat-bubble">Conversation cleared. How can I help with your plant today? 🌿</span>
          </div>`;
      }
    },
  };

  // ── Init ───────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", () => {
    const fab      = $id("chat-fab");
    const overlay  = $id("chatbot-overlay");
    const closeBtn = $id("chatbot-close");
    const clearBtn = $id("clear-chat");
    const sendBtn  = $id("chatbot-send");
    const input    = $id("chatbot-input");

    if (fab) fab.addEventListener("click", openChat);
    if (overlay) overlay.addEventListener("click", closeChat);
    if (closeBtn) closeBtn.addEventListener("click", closeChat);
    if (clearBtn) clearBtn.addEventListener("click", () => window.PlantPalChat.clearHistory());

    if (sendBtn) sendBtn.addEventListener("click", () => sendMessage());
    if (input) {
      input.addEventListener("keydown", e => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
      });
    }

    bindSuggestionClicks();

    // Keyboard shortcut: Ctrl/Cmd + K
    document.addEventListener("keydown", e => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") { e.preventDefault(); _isOpen ? closeChat() : openChat(); }
      if (e.key === "Escape" && _isOpen) closeChat();
    });
  });
})();
