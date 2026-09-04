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
  const volumeThumb = stage.querySelector(".volume-thumb");
  const volumeValue = stage.querySelector(".volume-value");
  const volumeIcon = stage.querySelector(".volume-icon-image");
  const volumeBadge = stage.querySelector("[data-volume-badge]");
  const connectionStates = stage.querySelectorAll("[data-connection-status]");
  const volumeState = stage.querySelector(".volume-state");
  const outputDeviceName = stage.querySelector(".output-device-name");
  const outputDeviceCount = stage.querySelector(".output-device-count");
  const outputDevicePanel = stage.querySelector(".output-device-panel");
  const outputDeviceList = stage.querySelector(".output-device-list");
  const outputDeviceStatus = stage.querySelector(".output-device-status");
  const outputDeviceClose = stage.querySelector(".output-device-close");
  const powerGroup = stage.querySelector(".control-group--power");
  const powerGrid = stage.querySelector(".power-grid");
  const powerPrompt = stage.querySelector(".power-prompt");
  const powerPromptTitle = stage.querySelector(".power-prompt-title");
  const powerPromptSubtitle = stage.querySelector(".power-prompt-subtitle");
  const powerPromptButtons = stage.querySelectorAll("[data-power-prompt-action]");
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
    ["outputDevice"],
    ["wifi", "wifiDetails"],
    ["bluetooth", "bluetoothDetails"],
    ["sleep", "restart", "shutdown"]
  ];
  const elements = Object.create(null);
  let demoOutputSnapshot = {
    defaultId: "living-room",
    devices: [
      { id: "living-room", name: "Living room soundbar", type: "HDMI · 5.1 audio", isDefault: true },
      { id: "gaming-headset", name: "Wireless gaming headset", type: "Bluetooth · Stereo", isDefault: false },
      { id: "controller-audio", name: "DualSense Wireless Controller", type: "USB · Headset output", isDefault: false }
    ]
  };

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
    "return", "exit", "volume", "outputDevice", "wifi", "bluetooth",
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

  if (outputDeviceClose) {
    outputDeviceClose.addEventListener("click", function () {
      sendAction("outputDeviceClose");
    });
  }

  powerPromptButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      sendAction(button.getAttribute("data-power-prompt-action"));
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
    if (data && typeof data.deviceId === "string") message.deviceId = data.deviceId;
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
    if (action === "outputDevice") {
      window.overlayUI.showOutputDevices(demoOutputSnapshot);
      return;
    }
    if (action === "outputDeviceClose") {
      window.overlayUI.hideOutputDevices();
      return;
    }
    if (action === "outputDeviceSelect") {
      const selectedId = data && data.deviceId;
      if (selectedId) {
        demoOutputSnapshot = {
          defaultId: selectedId,
          devices: demoOutputSnapshot.devices.map(function (device) {
            return Object.assign({}, device, { isDefault: device.id === selectedId });
          })
        };
        window.overlayUI.setOutputDevices(demoOutputSnapshot);
        window.overlayUI.setOutputDeviceStatus("Output device updated");
      }
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
      window.overlayUI.showPowerPrompt({ action: action, title: labels[action], focusedAction: "confirmNo" });
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

  let outputDeviceFocusIndex = 0;
  let outputDeviceFocusButtons = [];
  let outputDeviceHideTimer = null;

  function showOutputDevicePanelVisual() {
    if (!outputDevicePanel) return;
    if (outputDeviceHideTimer) {
      window.clearTimeout(outputDeviceHideTimer);
      outputDeviceHideTimer = null;
    }
    outputDevicePanel.hidden = false;
    outputDevicePanel.classList.remove("is-leaving");
    outputDevicePanel.classList.remove("is-visible");
    window.requestAnimationFrame(function () {
      if (outputDevicePanel) outputDevicePanel.classList.add("is-visible");
    });
  }

  function hideOutputDevicePanelVisual() {
    if (!outputDevicePanel) return;
    outputDevicePanel.classList.remove("is-visible");
    outputDevicePanel.classList.add("is-leaving");
    if (outputDeviceHideTimer) window.clearTimeout(outputDeviceHideTimer);
    outputDeviceHideTimer = window.setTimeout(function () {
      if (!outputDevicePanel || outputDevicePanel.classList.contains("is-visible")) return;
      outputDevicePanel.hidden = true;
      outputDevicePanel.classList.remove("is-leaving");
      outputDeviceHideTimer = null;
    }, 220);
  }

  function setOutputDeviceSummary(snapshot) {
    const source = snapshot || {};
    const devices = Array.isArray(source.devices) ? source.devices : [];
    let selected = null;
    devices.forEach(function (device) {
      if (!device) return;
      if (device.isDefault || (source.defaultId && device.id === source.defaultId)) selected = device;
    });
    safeText(outputDeviceName, selected
      ? displayValue(selected.name, "Selected output")
      : (devices.length ? "Select an output" : "No output devices found"));
    safeText(outputDeviceCount, devices.length ? devices.length + " device" + (devices.length === 1 ? "" : "s") : "Unavailable");
    if (elements.outputDevice) {
      elements.outputDevice.setAttribute("aria-label", selected
        ? "Output device. Currently " + displayValue(selected.name, "selected") + ". Choose another."
        : "Output device. Choose where game audio plays.");
    }
  }

  function setOutputDeviceFocus() {
    outputDeviceFocusButtons.forEach(function (button, index) {
      button.classList.toggle("is-focused", index === outputDeviceFocusIndex);
    });
  }

  function renderOutputDevices(snapshot) {
    if (!outputDeviceList) return;
    const source = snapshot || {};
    const devices = Array.isArray(source.devices) ? source.devices : [];
    while (outputDeviceList.firstChild) outputDeviceList.removeChild(outputDeviceList.firstChild);
    outputDeviceFocusButtons = [];
    if (outputDeviceClose) outputDeviceFocusButtons.push(outputDeviceClose);

    let selectedIndex = -1;
    devices.forEach(function (device, index) {
      if (!device || typeof device.id !== "string" || !device.id ||
          typeof device.name !== "string" || !device.name) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "output-device-option";
      button.dataset.deviceId = device.id;
      const isSelected = !!device.isDefault || (source.defaultId && device.id === source.defaultId);
      button.classList.toggle("is-selected", isSelected);
      if (isSelected) selectedIndex = outputDeviceFocusButtons.length;
      const copy = document.createElement("span");
      copy.className = "output-device-option-copy";
      const name = document.createElement("strong");
      name.className = "output-device-option-name";
      safeText(name, device.name);
      const type = document.createElement("span");
      type.className = "output-device-option-type";
      safeText(type, displayValue(device.type, "Windows audio output"));
      copy.appendChild(name);
      copy.appendChild(type);
      const state = document.createElement("span");
      state.className = "output-device-option-state";
      safeText(state, isSelected ? "Selected" : "Choose");
      button.appendChild(copy);
      button.appendChild(state);
      button.addEventListener("click", function () {
        sendAction("outputDeviceSelect", { deviceId: device.id });
      });
      outputDeviceList.appendChild(button);
      outputDeviceFocusButtons.push(button);
    });

    if (outputDeviceFocusButtons.length === 1) {
      const empty = document.createElement("p");
      empty.className = "output-device-empty";
      safeText(empty, "No active output devices found");
      outputDeviceList.appendChild(empty);
    }
    setOutputDeviceSummary(source);
    outputDeviceFocusIndex = selectedIndex >= 0 ? selectedIndex : (outputDeviceFocusButtons.length > 1 ? 1 : 0);
    setOutputDeviceFocus();
  }

  function moveOutputDeviceFocus(direction) {
    if (!outputDevicePanel || outputDevicePanel.hidden || outputDeviceFocusButtons.length === 0) return;
    const delta = direction === "up" || direction === "left" ? -1 : 1;
    outputDeviceFocusIndex = (outputDeviceFocusIndex + delta + outputDeviceFocusButtons.length) % outputDeviceFocusButtons.length;
    setOutputDeviceFocus();
  }

  function activateOutputDeviceFocus() {
    const button = outputDeviceFocusButtons[outputDeviceFocusIndex];
    if (!button) return;
    if (button === outputDeviceClose) {
      sendAction("outputDeviceClose");
      return;
    }
    const deviceId = button.dataset.deviceId;
    if (deviceId) sendAction("outputDeviceSelect", { deviceId: deviceId });
  }

  let powerPromptHideTimer = null;

  function setPowerPromptFocus(action) {
    powerPromptButtons.forEach(function (button) {
      button.classList.toggle("is-focused", button.getAttribute("data-power-prompt-action") === action);
    });
  }

  function showPowerPromptVisual(payload) {
    if (!powerPrompt || !powerGrid) return;
    if (powerPromptHideTimer) {
      window.clearTimeout(powerPromptHideTimer);
      powerPromptHideTimer = null;
    }
    const action = payload && payload.action;
    Object.keys(elements).forEach(function (name) {
      if (elements[name] && elements[name].classList.contains("power-tile"))
        elements[name].classList.toggle("is-expanded", name === action);
    });
    powerGrid.classList.add("is-prompt-open");
    if (powerGroup) powerGroup.classList.add("is-prompt-open");
    safeText(powerPromptTitle, payload && payload.title ? payload.title : "Are you sure?");
    safeText(powerPromptSubtitle, "Choose Cancel or Continue to confirm.");
    const focusedAction = payload && payload.focusedAction === "confirmYes" ? "confirmYes" : "confirmNo";
    setPowerPromptFocus(focusedAction);
    powerPrompt.hidden = false;
    powerPrompt.classList.remove("is-leaving");
    powerPrompt.classList.remove("is-visible");
    window.requestAnimationFrame(function () {
      if (powerPrompt) powerPrompt.classList.add("is-visible");
    });
  }

  function hidePowerPromptVisual() {
    if (!powerPrompt) return;
    powerPrompt.classList.remove("is-visible");
    powerPrompt.classList.add("is-leaving");
    if (powerGrid) powerGrid.classList.remove("is-prompt-open");
    if (powerGroup) powerGroup.classList.remove("is-prompt-open");
    Object.keys(elements).forEach(function (name) {
      if (elements[name]) elements[name].classList.remove("is-expanded");
    });
    if (powerPromptHideTimer) window.clearTimeout(powerPromptHideTimer);
    powerPromptHideTimer = window.setTimeout(function () {
      if (!powerPrompt || powerPrompt.classList.contains("is-visible")) return;
      powerPrompt.hidden = true;
      powerPrompt.classList.remove("is-leaving");
      powerPromptHideTimer = null;
    }, 220);
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
      this.setOutputDevices(payload.outputDevices || demoOutputSnapshot);
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
      if (volumeThumb) volumeThumb.style.left = value + "%";
      safeText(volumeValue, value + "%");
      if (volumeIcon) volumeIcon.src = muted ? "assets/icons/mute.svg" : "assets/icons/volume.svg";
      safeText(volumeBadge, muted ? "Muted" : "Sound on");
      if (elements.volume) {
        elements.volume.classList.toggle("is-muted", muted);
        elements.volume.setAttribute(
          "aria-label",
          "Volume " + value + " percent. " + (muted ? "Click to unmute." : "Click to mute.")
        );
      }
      safeText(volumeState, muted ? "Muted · click to restore" : "Click to mute / unmute");
    },
    setOutputDevices: function (payload) {
      payload = payload || {};
      if (Array.isArray(payload.devices) && payload.devices.length) demoOutputSnapshot = payload;
      renderOutputDevices(payload);
    },
    showOutputDevices: function (payload) {
      payload = payload || demoOutputSnapshot;
      showOutputDevicePanelVisual();
      renderOutputDevices(payload);
      safeText(outputDeviceStatus, "");
    },
    hideOutputDevices: function () {
      hideOutputDevicePanelVisual();
      outputDeviceFocusButtons = [];
    },
    setOutputDeviceStatus: function (message) {
      safeText(outputDeviceStatus, message);
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
      hidePowerPromptVisual();
      safeText(confirmationTitle, payload && payload.title);
      confirmation.hidden = false;
      const yes = payload && payload.focusedAction === "confirmYes";
      confirmationYes.classList.toggle("is-focused", yes);
      confirmationNo.classList.toggle("is-focused", !yes);
    },
    showPowerPrompt: function (payload) {
      if (confirmation) confirmation.hidden = true;
      showPowerPromptVisual(payload || {});
    },
    hideConfirmation: function () {
      if (confirmation) confirmation.hidden = true;
      hidePowerPromptVisual();
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
