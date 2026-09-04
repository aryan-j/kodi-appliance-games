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
  const connectionStates = stage.querySelectorAll("[data-connection-status]");
  const volumeState = stage.querySelector(".volume-state");
  const connectivityPanel = stage.querySelector(".connectivity-panel");
  const connectivityTitle = stage.querySelector(".connectivity-title");
  const connectivitySubtitle = stage.querySelector(".connectivity-subtitle");
  const connectivityStatus = stage.querySelector(".connectivity-status");
  const connectivityContent = stage.querySelector(".connectivity-content");
  const connectivityActions = stage.querySelector(".connectivity-actions");
  const connectivityBack = stage.querySelector(".connectivity-back");
  const fallbackPoster = "assets/fallbacks/poster-fallback.svg";
  const fallbackFanart = "assets/fallbacks/fanart-fallback.svg";

  const actionRows = [
    ["return", "exit"],
    ["volume"],
    ["wifi", "wifiDetails"],
    ["bluetooth", "bluetoothDetails"],
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
    groupButtonSets[1][0],
    groupButtonSets[2][0], groupButtonSets[2][1],
    groupButtonSets[3][0], groupButtonSets[3][1], groupButtonSets[3][2]
  ];
  const orderedActions = [
    "return", "exit", "volume", "wifi", "bluetooth",
    "sleep", "restart", "shutdown"
  ];
  const detailElements = stage.querySelectorAll("[data-connectivity-details]");

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

  detailElements.forEach(function (element) {
    const kind = element.getAttribute("data-connectivity-details");
    const action = kind + "Details";
    element.dataset.overlayAction = action;
    element.id = "overlay-action-" + action;
    elements[action] = element;
    element.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      sendAction(action);
    });
    element.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        event.stopPropagation();
        sendAction(action);
      }
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

  function sendAction(action, data) {
    const message = { type: "action", action: action };
    if (data && typeof data.ssid === "string") message.ssid = data.ssid;
    const hostBridgeAvailable = window.chrome && window.chrome.webview && window.location.hostname === "overlay.local";
    if (hostBridgeAvailable) {
      window.chrome.webview.postMessage(message);
    } else {
      console.info("Overlay action", message);
      runBrowserDemoAction(action, data);
    }
  }

  // Keep the design package explorable when opened in a normal browser. Kodi's
  // WebView2 host takes the real path above, so these demo-only states never
  // replace system actions in the live overlay.
  function runBrowserDemoAction(action, data) {
    if (action === "volume") {
      const muted = !elements.volume.classList.contains("is-muted");
      window.overlayUI.setVolume({ value: 66, muted: muted });
      return;
    }
    if (action === "wifi") {
      window.overlayUI.setConnectivity({ wifiEnabled: !connectionStates[0].classList.contains("is-on"), bluetoothEnabled: connectionStates[1].classList.contains("is-on") });
      return;
    }
    if (action === "bluetooth") {
      window.overlayUI.setConnectivity({ wifiEnabled: connectionStates[0].classList.contains("is-on"), bluetoothEnabled: !connectionStates[1].classList.contains("is-on") });
      return;
    }
    if (action === "wifiDetails" || action === "bluetoothDetails") {
      const kind = action === "bluetoothDetails" ? "bluetooth" : "wifi";
      window.overlayUI.showConnectivity({ kind: kind, snapshot: {
        wifi: {
          state: "Connected",
          ssid: "Arcade Wi-Fi",
          signal: 86,
          linkSpeed: "866 Mbps",
          adapter: "Wireless adapter",
          networks: [
            { ssid: "Arcade Wi-Fi", signal: 86, authentication: "WPA2-Personal" },
            { ssid: "Guest network", signal: 54, authentication: "WPA2-Personal" },
            { ssid: "5G backup", signal: 32, authentication: "Open" }
          ]
        },
        bluetooth: {
          state: "On",
          devices: [
            { name: "DualSense Wireless Controller", status: "Connected", battery: 82 },
            { name: "Living room headset", status: "Paired", battery: 48 }
          ]
        }
      } });
      return;
    }
    if (action === "connectivityClose") {
      window.overlayUI.hideConnectivity();
      return;
    }
    if (action === "exit") {
      window.overlayUI.showConfirmation({ title: "Exit Galacticare?", focusedAction: "confirmNo" });
      return;
    }
    if (action === "sleep" || action === "restart" || action === "shutdown") {
      const labels = { sleep: "Put this PC to sleep?", restart: "Restart this PC?", shutdown: "Shut down this PC?" };
      window.overlayUI.showConfirmation({ title: labels[action], focusedAction: "confirmNo" });
      return;
    }
    if (action === "confirmNo" || action === "confirmYes") {
      window.overlayUI.hideConfirmation();
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

  function setConnectionState(index, on) {
    if (!connectionStates[index]) return;
    connectionStates[index].classList.toggle("is-on", !!on);
    safeText(connectionStates[index], on ? "On" : "Off");
  }

  let connectivityKind = "wifi";
  let connectivityFocusIndex = 0;
  let connectivityFocusButtons = [];
  let connectivityHideTimer = null;

  function showConnectivityPanelVisual() {
    if (!connectivityPanel) return;
    if (connectivityHideTimer) {
      window.clearTimeout(connectivityHideTimer);
      connectivityHideTimer = null;
    }
    connectivityPanel.hidden = false;
    connectivityPanel.classList.remove("is-leaving");
    connectivityPanel.classList.remove("is-visible");
    window.requestAnimationFrame(function () {
      if (connectivityPanel) connectivityPanel.classList.add("is-visible");
    });
  }

  function hideConnectivityPanelVisual() {
    if (!connectivityPanel) return;
    connectivityPanel.classList.remove("is-visible");
    connectivityPanel.classList.add("is-leaving");
    if (connectivityHideTimer) window.clearTimeout(connectivityHideTimer);
    connectivityHideTimer = window.setTimeout(function () {
      if (!connectivityPanel || connectivityPanel.classList.contains("is-visible")) return;
      connectivityPanel.hidden = true;
      connectivityPanel.classList.remove("is-leaving");
      connectivityHideTimer = null;
    }, 220);
  }

  function displayValue(value, fallback) {
    if (value == null || String(value).trim() === "") return fallback;
    return String(value);
  }

  function appendFact(parent, label, value) {
    const fact = document.createElement("div");
    fact.className = "connectivity-fact";
    const factLabel = document.createElement("span");
    factLabel.className = "connectivity-fact-label";
    safeText(factLabel, label);
    const factValue = document.createElement("strong");
    factValue.className = "connectivity-fact-value";
    safeText(factValue, value);
    fact.appendChild(factLabel);
    fact.appendChild(factValue);
    parent.appendChild(fact);
  }

  function appendConnectivityAction(label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "connectivity-action";
    button.dataset.connectivityAction = action;
    safeText(button, label);
    button.addEventListener("click", function () { sendAction(action); });
    connectivityActions.appendChild(button);
    connectivityFocusButtons.push(button);
  }

  function appendWifiNetwork(parent, network, currentSsid) {
    if (!network || typeof network.ssid !== "string" || !network.ssid) return;
    const ssid = network.ssid;
    if (ssid.length > 64 || /[\x00-\x1F\x7F"'\r\n]/.test(ssid)) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "connectivity-network-row";
    button.dataset.connectivityAction = "wifiConnect";
    const text = document.createElement("span");
    text.className = "connectivity-network-text";
    const name = document.createElement("strong");
    safeText(name, ssid);
    const security = document.createElement("span");
    const authentication = displayValue(network.authentication, "Security unknown");
    const signal = Number(network.signal);
    const signalText = Number.isFinite(signal) && signal >= 0 && signal <= 100
      ? "Signal " + Math.round(signal) + "%" : "Signal —";
    safeText(security, signalText + "  ·  " + authentication);
    text.appendChild(name);
    text.appendChild(security);
    const state = document.createElement("span");
    state.className = "connectivity-network-state";
    safeText(state, currentSsid && currentSsid === ssid ? "Connected" : "Connect");
    button.appendChild(text);
    button.appendChild(state);
    button.addEventListener("click", function () {
      sendAction("wifiConnect", { ssid: ssid });
    });
    parent.appendChild(button);
    connectivityFocusButtons.push(button);
  }

  function renderConnectivity(kind, snapshot) {
    if (!connectivityContent || !connectivityActions) return;
    connectivityKind = kind === "bluetooth" ? "bluetooth" : "wifi";
    while (connectivityContent.firstChild) connectivityContent.removeChild(connectivityContent.firstChild);
    while (connectivityActions.firstChild) connectivityActions.removeChild(connectivityActions.firstChild);
    connectivityFocusButtons = [];
    if (connectivityBack) connectivityFocusButtons.push(connectivityBack);

    const source = snapshot || {};
    const data = source[connectivityKind] || {};
    const facts = document.createElement("div");
    facts.className = "connectivity-facts";
    if (connectivityKind === "wifi") {
      appendFact(facts, "Connection", displayValue(data.state, "Unknown"));
      appendFact(facts, "Network", displayValue(data.ssid, "Not connected"));
      appendFact(facts, "Signal", Number.isFinite(Number(data.signal)) ? Number(data.signal) + "%" : "—");
      appendFact(facts, "Link speed", displayValue(data.linkSpeed, "—"));
      appendFact(facts, "Adapter", displayValue(data.adapter, "—"));
      connectivityContent.appendChild(facts);

      const networkList = document.createElement("div");
      networkList.className = "connectivity-network-list";
      const networks = Array.isArray(data.networks) ? data.networks : [];
      if (networks.length === 0) {
        const empty = document.createElement("p");
        empty.className = "connectivity-empty";
        safeText(empty, "No Wi-Fi networks found");
        networkList.appendChild(empty);
      } else {
        networks.forEach(function (network) {
          appendWifiNetwork(networkList, network, data.ssid);
        });
      }
      connectivityContent.appendChild(networkList);
    } else {
      const devices = Array.isArray(data.devices) ? data.devices : [];
      appendFact(facts, "Bluetooth", displayValue(data.state, "Unknown"));
      appendFact(facts, "Devices", String(devices.length));
      connectivityContent.appendChild(facts);

      const deviceList = document.createElement("div");
      deviceList.className = "connectivity-device-list";
      if (devices.length === 0) {
        const empty = document.createElement("p");
        empty.className = "connectivity-empty";
        safeText(empty, "No paired devices found");
        deviceList.appendChild(empty);
      } else {
        devices.forEach(function (device) {
          const row = document.createElement("div");
          row.className = "connectivity-device-row";
          const text = document.createElement("div");
          text.className = "connectivity-device-text";
          const name = document.createElement("strong");
          safeText(name, displayValue(device && device.name, "Unnamed device"));
          const status = document.createElement("span");
          safeText(status, displayValue(device && device.status, "Unknown"));
          text.appendChild(name);
          text.appendChild(status);
          const battery = document.createElement("span");
          battery.className = "connectivity-device-battery";
          const level = Number(device && device.battery);
          safeText(battery, Number.isFinite(level) && level >= 0 && level <= 100
            ? "Battery " + Math.round(level) + "%" : "Battery —");
          row.appendChild(text);
          row.appendChild(battery);
          deviceList.appendChild(row);
        });
      }
      connectivityContent.appendChild(deviceList);
    }

    appendConnectivityAction("Refresh", connectivityKind + "Refresh");
    appendConnectivityAction(
      connectivityKind === "wifi" ? "Open Network Settings" : "Open Bluetooth Settings",
      connectivityKind + "Settings");
    connectivityFocusIndex = connectivityFocusButtons.length > 1 ? 1 : 0;
    setConnectivityFocus();
    if (connectivityStatus) safeText(connectivityStatus, "");
  }

  function setConnectivityFocus() {
    connectivityFocusButtons.forEach(function (button, index) {
      button.classList.toggle("is-focused", index === connectivityFocusIndex);
    });
  }

  function moveConnectivityFocus(direction) {
    if (!connectivityPanel || connectivityPanel.hidden || connectivityFocusButtons.length === 0) return;
    const backwards = direction === "up" || direction === "left";
    const delta = backwards ? -1 : 1;
    connectivityFocusIndex = (connectivityFocusIndex + delta + connectivityFocusButtons.length) % connectivityFocusButtons.length;
    setConnectivityFocus();
  }

  function activateConnectivityFocus() {
    const button = connectivityFocusButtons[connectivityFocusIndex];
    if (button && typeof button.click === "function") button.click();
  }

  if (connectivityBack) {
    connectivityBack.addEventListener("click", function () {
      sendAction("connectivityClose");
    });
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
      const muted = !!payload.muted;
      if (volumeFill) volumeFill.style.width = value + "%";
      safeText(volumeValue, value + "%");
      if (elements.volume) {
        elements.volume.classList.toggle("is-muted", muted);
        elements.volume.setAttribute(
          "aria-label",
          "Volume " + value + " percent. " + (muted ? "Click to unmute." : "Click to mute.")
        );
      }
      safeText(volumeState, muted ? "Muted · click to restore" : "Click to mute / unmute");
    },
    setConnectivity: function (payload) {
      payload = payload || {};
      const wifiOn = !!payload.wifiEnabled;
      const bluetoothOn = !!payload.bluetoothEnabled;
      setConnectionState(0, wifiOn);
      setConnectionState(1, bluetoothOn);
      if (elements.wifi) elements.wifi.setAttribute("aria-pressed", String(wifiOn));
      if (elements.bluetooth) elements.bluetooth.setAttribute("aria-pressed", String(bluetoothOn));
    },
    showConnectivity: function (payload) {
      payload = payload || {};
      if (!connectivityPanel) return;
      showConnectivityPanelVisual();
      safeText(connectivityTitle, payload.kind === "bluetooth" ? "Bluetooth" : "Wi-Fi");
      safeText(connectivitySubtitle, payload.kind === "bluetooth"
        ? "Paired and connected devices" : "Available networks");
      renderConnectivity(payload.kind, payload.snapshot);
    },
    setConnectivityDetails: function (payload) {
      payload = payload || {};
      if (!connectivityPanel || connectivityPanel.hidden) return;
      renderConnectivity(connectivityKind, payload.snapshot);
    },
    hideConnectivity: function () {
      hideConnectivityPanelVisual();
      connectivityFocusButtons = [];
    },
    setConnectivityStatus: function (message) {
      safeText(connectivityStatus, message);
    },
    setConnectivityActionResult: function (payload) {
      payload = payload || {};
      const result = payload.result || {};
      const state = result.result;
      if (state === "Connected") {
        safeText(connectivityStatus, "Connection requested — refreshing networks…");
      } else if (state === "NeedsSettings") {
        safeText(connectivityStatus, "Network is not saved — open Network Settings to connect");
      } else if (state === "Invalid") {
        safeText(connectivityStatus, "Invalid network name");
      } else if (state === "Failed") {
        safeText(connectivityStatus, "Could not connect using the saved profile");
      } else {
        safeText(connectivityStatus, "Connection status unavailable");
      }
    },
    moveConnectivityFocus: moveConnectivityFocus,
    activateConnectivityFocus: activateConnectivityFocus,
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
  if (window.chrome && window.chrome.webview && window.location.hostname === "overlay.local") {
    window.chrome.webview.postMessage({ type: "ready" });
  }
}());
