(function () {
  "use strict";

  const stage = document.querySelector(".stage");
  const gallery = document.querySelector(".states-gallery");
  if (gallery) gallery.remove();

  const title = stage.querySelector(".overlay-title");
  const subtitle = stage.querySelector(".overlay-subtitle");
  const clock = stage.querySelector(".overlay-clock");
  const fanart = stage.querySelector(".background-art");
  const posterSlot = stage.querySelector(".poster-slot");
  const poster = stage.querySelector(".poster-image");
  const statValues = stage.querySelectorAll(".stat-value");
  const groups = stage.querySelectorAll(".control-group");
  const volumeFill = stage.querySelector(".volume-fill");
  const volumeValue = stage.querySelector(".volume-value");
  const switches = stage.querySelectorAll(".switch");
  const fallbackPoster = "assets/fallbacks/poster-fallback.svg";
  const fallbackFanart = "assets/fallbacks/fanart-fallback.svg";

  const actionRows = [
    ["return", "exit"],
    ["volume"],
    ["mute"],
    ["wifi", "bluetooth"],
    ["sleep", "restart", "shutdown"]
  ];
  const elements = Object.create(null);

  const groupButtonSets = [
    groups[0] ? groups[0].querySelectorAll("button") : [],
    groups[1] ? groups[1].querySelectorAll("button") : [],
    groups[2] ? groups[2].querySelectorAll("button") : [],
    groups[3] ? groups[3].querySelectorAll("button") : []
  ];
  const orderedElements = [
    groupButtonSets[0][0], groupButtonSets[0][1],
    groupButtonSets[1][0], groupButtonSets[1][1],
    groupButtonSets[2][0], groupButtonSets[2][1],
    groupButtonSets[3][0], groupButtonSets[3][1], groupButtonSets[3][2]
  ];
  const orderedActions = [
    "return", "exit", "volume", "mute", "wifi", "bluetooth",
    "sleep", "restart", "shutdown"
  ];

  orderedElements.forEach(function (element, index) {
    if (!element) return;
    const action = orderedActions[index];
    element.dataset.overlayAction = action;
    element.id = "overlay-action-" + action;
    elements[action] = element;
    element.addEventListener("click", function () {
      if (element.classList.contains("is-disabled")) return;
      sendAction(action);
    });
  });

  actionRows.forEach(function (row, rowIndex) {
    row.forEach(function (action, columnIndex) {
      const element = elements[action];
      if (!element) return;
      element.dataset.navRow = String(rowIndex);
      element.dataset.navColumn = String(columnIndex);
    });
  });

  function sendAction(action) {
    const message = { type: "action", action: action };
    if (window.chrome && window.chrome.webview) {
      window.chrome.webview.postMessage(message);
    } else {
      console.info("Overlay action", message);
    }
  }

  function safeText(element, value) {
    if (element) element.textContent = value == null ? "" : String(value);
  }

  function safeArtwork(element, slot, value, fallback) {
    if (!element) return;
    const usable = typeof value === "string" && value.trim().length > 0;
    element.src = usable ? value : fallback;
    if (slot) slot.classList.toggle("is-empty", !usable);
    element.onerror = function () {
      element.onerror = null;
      element.src = fallback;
      if (slot) slot.classList.add("is-empty");
    };
  }

  function setSwitch(index, on) {
    if (switches[index]) switches[index].classList.toggle("is-on", !!on);
  }

  function setFocus(payload) {
    const action = payload && payload.action;
    Object.keys(elements).forEach(function (name) {
      const focused = name === action;
      elements[name].classList.toggle("is-focused", focused);
      if (focused) elements[name].setAttribute("aria-current", "true");
      else elements[name].removeAttribute("aria-current");
    });
  }

  let confirmation = null;
  let confirmationTitle = null;
  let confirmationNo = null;
  let confirmationYes = null;

  function ensureConfirmation() {
    if (confirmation) return;
    confirmation = document.createElement("div");
    confirmation.className = "confirm-backdrop runtime-confirm";
    confirmation.hidden = true;
    confirmation.setAttribute("role", "dialog");
    confirmation.setAttribute("aria-modal", "true");

    const panel = document.createElement("div");
    panel.className = "confirm-panel";
    confirmationTitle = document.createElement("p");
    confirmationTitle.className = "confirm-message";
    const actions = document.createElement("div");
    actions.className = "confirm-actions";
    confirmationNo = document.createElement("button");
    confirmationNo.type = "button";
    confirmationNo.className = "confirm-btn";
    confirmationNo.textContent = "No";
    confirmationYes = document.createElement("button");
    confirmationYes.type = "button";
    confirmationYes.className = "confirm-btn";
    confirmationYes.textContent = "Yes";
    confirmationNo.addEventListener("click", function () { sendAction("confirmNo"); });
    confirmationYes.addEventListener("click", function () { sendAction("confirmYes"); });
    actions.appendChild(confirmationNo);
    actions.appendChild(confirmationYes);
    panel.appendChild(confirmationTitle);
    panel.appendChild(actions);
    confirmation.appendChild(panel);
    stage.appendChild(confirmation);
  }

  let toast = null;
  function ensureToast() {
    if (toast) return;
    toast = document.createElement("div");
    toast.className = "toast runtime-toast";
    toast.hidden = true;
    toast.setAttribute("aria-live", "polite");
    stage.appendChild(toast);
  }

  window.overlayUI = {
    initialize: function (payload) {
      payload = payload || {};
      this.setMetadata(payload);
      this.setArtwork(payload);
      this.setClock(payload.clock);
      this.setSessionTime(payload.sessionTime);
      this.setTotalPlaytime(payload.totalPlaytime);
      this.setVolume({ value: payload.volume, muted: payload.muted });
      this.setConnectivity(payload);
      setFocus({ action: payload.focusedAction || "return" });
    },
    setMetadata: function (payload) {
      payload = payload || {};
      safeText(title, payload.title);
      safeText(subtitle, payload.subtitle);
    },
    setArtwork: function (payload) {
      payload = payload || {};
      safeArtwork(poster, posterSlot, payload.posterUrl, fallbackPoster);
      safeArtwork(fanart, null, payload.fanartUrl, fallbackFanart);
    },
    setClock: function (value) { safeText(clock, value); },
    setSessionTime: function (value) { safeText(statValues[0], value); },
    setTotalPlaytime: function (value) { safeText(statValues[1], value); },
    setVolume: function (payload) {
      payload = payload || {};
      const numeric = Number(payload.value);
      const value = Number.isFinite(numeric) ? Math.max(0, Math.min(100, numeric)) : 0;
      if (volumeFill) volumeFill.style.width = value + "%";
      safeText(volumeValue, value + "%");
      setSwitch(0, !!payload.muted);
    },
    setConnectivity: function (payload) {
      payload = payload || {};
      setSwitch(1, !!payload.wifiEnabled);
      setSwitch(2, !!payload.bluetoothEnabled);
    },
    setFocus: setFocus,
    setDisabled: function (payload) {
      const element = payload && elements[payload.action];
      if (!element) return;
      const disabled = !!payload.disabled;
      element.classList.toggle("is-disabled", disabled);
      element.setAttribute("aria-disabled", disabled ? "true" : "false");
    },
    showConfirmation: function (payload) {
      ensureConfirmation();
      safeText(confirmationTitle, payload && payload.title);
      confirmation.hidden = false;
      const yes = payload && payload.focusedAction === "confirmYes";
      confirmationYes.classList.toggle("is-focused", yes);
      confirmationNo.classList.toggle("is-focused", !yes);
    },
    hideConfirmation: function () {
      if (confirmation) confirmation.hidden = true;
    },
    showToast: function (payload) {
      ensureToast();
      safeText(toast, payload && payload.message);
      toast.hidden = false;
    },
    hideToast: function () {
      if (toast) toast.hidden = true;
    },
    reset: function () {
      this.hideConfirmation();
      this.hideToast();
      setFocus({ action: "return" });
    }
  };

  document.documentElement.classList.add("overlay-runtime");
  window.overlayUI.setFocus({ action: "return" });
  if (window.chrome && window.chrome.webview) {
    window.chrome.webview.postMessage({ type: "ready" });
  }
}());
