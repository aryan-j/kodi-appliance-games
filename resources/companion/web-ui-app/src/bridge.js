import {
  defaultConnectivitySnapshot,
  defaultOutputDevices,
  getState,
  patchConnectivity,
  patchData,
  patchState
} from "./store.js";
import { normalizeSnapshot } from "./connector-contract.js";

const hostBridgeAvailable = () => Boolean(
  window.chrome && window.chrome.webview && window.location.hostname === "overlay.local"
);

if (!hostBridgeAvailable()) document.documentElement.classList.add("is-demo");

const allowedLogo = (value) => {
  if (typeof value !== "string" || value.length > 2048) return "";
  if (!value) return "";
  try {
    const url = new URL(value, window.location.href);
    if (url.protocol !== "https:" && url.protocol !== "http:") return "";
    return value;
  } catch {
    return "";
  }
};

export function safeLogo(value) {
  return allowedLogo(value);
}

function postToHost(action, data = {}) {
  const message = { type: "action", action };
  if (typeof data.ssid === "string") message.ssid = data.ssid;
  if (typeof data.deviceId === "string") message.deviceId = data.deviceId;

  if (hostBridgeAvailable()) {
    window.chrome.webview.postMessage(message);
    return;
  }

  runDemoAction(action, data);
}

function cloneWithDefault(outputDevices, selectedId) {
  const devices = Array.isArray(outputDevices?.devices)
    ? outputDevices.devices
    : defaultOutputDevices.devices;
  return {
    defaultId: selectedId,
    devices: devices.map((device) => ({
      ...device,
      isDefault: device.id === selectedId
    }))
  };
}

function updateToggle(kind) {
  const data = getState().data;
  patchData(kind === "wifi"
    ? { wifiEnabled: !data.wifiEnabled }
    : { bluetoothEnabled: !data.bluetoothEnabled });
}

function showPowerPrompt(action) {
  const titles = {
    exit: "Exit Galacticare?",
    sleep: "Put this PC to sleep?",
    restart: "Restart this PC?",
    shutdown: "Shut down this PC?"
  };
  patchState({
    screen: "main",
    modal: { type: "power", action, title: titles[action] || "Are you sure?", focusedAction: "confirmNo" },
    focusedAction: "confirmNo"
  });
}

function runDemoAction(action, data = {}) {
  const current = getState();
  switch (action) {
    case "return":
      patchState({ screen: "main", modal: { type: "toast", message: "Return to game" } });
      window.setTimeout(() => {
        if (getState().modal?.type === "toast") patchState({ modal: null });
      }, 1200);
      break;
    case "exit":
    case "sleep":
    case "restart":
    case "shutdown":
      showPowerPrompt(action);
      break;
    case "volume":
      patchData({ muted: !current.data.muted });
      break;
    case "volumeDown":
      patchData({ volume: Math.max(0, current.data.volume - 5) });
      break;
    case "volumeUp":
      patchData({ volume: Math.min(100, current.data.volume + 5) });
      break;
    case "wifi":
    case "bluetooth":
      updateToggle(action);
      break;
    case "wifiDetails":
    case "bluetoothDetails":
      patchState({
        screen: "connectivity",
        connectivity: {
          ...current.connectivity,
          kind: action === "wifiDetails" ? "wifi" : "bluetooth",
          snapshot: current.connectivity.snapshot || defaultConnectivitySnapshot,
          status: ""
        },
        focusedAction: action === "wifiDetails" ? "wifiRefresh" : "bluetoothRefresh"
      });
      break;
    case "wifiRefresh":
    case "bluetoothRefresh":
      patchConnectivity({ status: "Connection details are up to date" });
      break;
    case "wifiConnect":
      patchConnectivity({ status: `Connecting to ${data.ssid || "network"}…` });
      window.setTimeout(() => patchConnectivity({ status: "Connected" }), 500);
      break;
    case "wifiSettings":
    case "bluetoothSettings":
      patchConnectivity({ status: "Settings are available through the host" });
      break;
    case "connectivityClose":
      patchState({ screen: "main", detailFocus: "" });
      break;
    case "outputDevice":
      patchState({ screen: "output", outputStatus: "", focusedAction: "outputDevice" });
      break;
    case "outputDeviceClose":
      patchState({ screen: "main", detailFocus: "" });
      break;
    case "outputDeviceSelect":
      if (data.deviceId) {
        patchState({
          outputDevices: cloneWithDefault(current.outputDevices, data.deviceId),
          outputStatus: "Output device updated"
        });
      }
      break;
    case "confirmNo":
    case "confirmYes":
      patchState({ modal: null, focusedAction: "return" });
      break;
    default:
      break;
  }
}

function normalizedData(payload) {
  const normalized = normalizeSnapshot(payload);
  const data = {};
  for (const [key, value] of Object.entries(normalized)) {
    if (value !== undefined && key !== "outputDevices" && key !== "connectivitySnapshot") {
      data[key] = key === "logoUrl" ? safeLogo(value) : value;
    }
  }
  return { data, normalized };
}

function connectivityFocusActions(state) {
  const kind = state.connectivity.kind === "bluetooth" ? "bluetooth" : "wifi";
  if (kind === "bluetooth") return ["bluetoothRefresh", "bluetoothSettings", "connectivityClose"];
  const networks = Array.isArray(state.connectivity.snapshot?.wifi?.networks)
    ? state.connectivity.snapshot.wifi.networks
    : [];
  const networkActions = networks
    .filter((network) => typeof network?.ssid === "string" && network.ssid.length > 0)
    .map((network) => `wifiNetwork:${network.ssid}`);
  return ["wifiRefresh", ...networkActions, "wifiSettings", "connectivityClose"];
}

export const overlayUI = {
  initialize(payload = {}) {
    const { data, normalized } = normalizedData(payload);
    patchState({
      data: { ...getState().data, ...data },
      outputDevices: normalized.outputDevices || defaultOutputDevices,
      connectivity: {
        ...getState().connectivity,
        snapshot: normalized.connectivitySnapshot || defaultConnectivitySnapshot
      },
      focusedAction: normalized.focusedAction || getState().focusedAction,
      screen: "main",
      modal: null
    });
  },
  updateDynamicState(payload = {}) {
    const { data } = normalizedData(payload);
    // Kodi sends the dynamic audio values as a nested object while the
    // initial snapshot uses a scalar. Normalize both shapes at the boundary.
    if (payload.volume && typeof payload.volume === "object") {
      if (Number.isFinite(Number(payload.volume.value))) data.volume = Number(payload.volume.value);
      if (typeof payload.volume.muted === "boolean") data.muted = payload.volume.muted;
    }
    patchData(data);
  },
  setFocus(payload = {}) {
    if (typeof payload.action === "string") patchState({ focusedAction: payload.action });
  },
  setVolume(payload = {}) {
    patchData({
      volume: Number.isFinite(Number(payload.value)) ? Number(payload.value) : getState().data.volume,
      muted: Boolean(payload.muted)
    });
  },
  setConnectivity(payload = {}) {
    patchData({
      wifiEnabled: typeof payload.wifiEnabled === "boolean" ? payload.wifiEnabled : getState().data.wifiEnabled,
      bluetoothEnabled: typeof payload.bluetoothEnabled === "boolean" ? payload.bluetoothEnabled : getState().data.bluetoothEnabled
    });
  },
  showConnectivity(payload = {}) {
    patchState({
      screen: "connectivity",
      connectivity: {
        ...getState().connectivity,
        kind: payload.kind === "bluetooth" ? "bluetooth" : "wifi",
        snapshot: payload.snapshot || getState().connectivity.snapshot,
        status: ""
      },
      focusedAction: payload.kind === "bluetooth" ? "bluetoothRefresh" : "wifiRefresh"
    });
    if (typeof payload.wifiEnabled === "boolean" || typeof payload.bluetoothEnabled === "boolean") {
      overlayUI.setConnectivity(payload);
    }
  },
  setConnectivityDetails(payload = {}) {
    if (payload.snapshot) {
      const current = getState();
      const connectivity = { ...current.connectivity, snapshot: payload.snapshot };
      const nextState = { ...current, connectivity };
      const actions = connectivityFocusActions(nextState);
      const focusedAction = actions.includes(current.focusedAction)
        ? current.focusedAction
        : actions[0];
      patchState({ connectivity, focusedAction });
    }
    if (typeof payload.wifiEnabled === "boolean" || typeof payload.bluetoothEnabled === "boolean") {
      overlayUI.setConnectivity(payload);
    }
  },
  setConnectivityStatus(status) {
    patchConnectivity({ status: typeof status === "string" ? status : "" });
  },
  setConnectivityActionResult(result = {}) {
    patchConnectivity({
      status: result.message || result.status || (result.success ? "Connected" : "Unable to connect")
    });
  },
  hideConnectivity() {
    patchState({ screen: "main", detailFocus: "" });
  },
  showOutputDevices(snapshot = {}) {
    patchState({
      screen: "output",
      outputDevices: snapshot,
      outputStatus: "",
      focusedAction: "outputDevice"
    });
  },
  setOutputDevices(snapshot = {}) {
    patchState({ outputDevices: snapshot });
  },
  setOutputDeviceStatus(status) {
    patchState({ outputStatus: typeof status === "string" ? status : "" });
  },
  hideOutputDevices() {
    patchState({ screen: "main", detailFocus: "" });
  },
  showPowerPrompt(payload = {}) {
    patchState({
      screen: "main",
      modal: {
        type: "power",
        action: payload.action || "shutdown",
        title: payload.title || "Are you sure?",
        focusedAction: payload.focusedAction || "confirmNo"
      },
      focusedAction: payload.focusedAction || "confirmNo"
    });
  },
  showConfirmation(payload = {}) {
    patchState({
      modal: {
        type: "generic",
        action: payload.action || "",
        title: payload.title || "Are you sure?",
        focusedAction: payload.focusedAction || "confirmNo"
      },
      focusedAction: payload.focusedAction || "confirmNo"
    });
  },
  hideConfirmation() {
    patchState({ modal: null, focusedAction: "return" });
  },
  moveConnectivityFocus(direction) {
    const state = getState();
    const actions = connectivityFocusActions(state);
    const currentIndex = Math.max(0, actions.indexOf(state.focusedAction));
    const nextIndex = direction === "up" || direction === "left"
      ? (currentIndex - 1 + actions.length) % actions.length
      : (currentIndex + 1) % actions.length;
    patchState({ focusedAction: actions[nextIndex] });
  },
  activateConnectivityFocus() {
    const action = getState().focusedAction;
    if (action?.startsWith("wifiNetwork:")) {
      postToHost("wifiConnect", { ssid: action.slice("wifiNetwork:".length) });
      return;
    }
    if (action) postToHost(action);
  },
  moveOutputDeviceFocus(direction) {
    const devices = Array.isArray(getState().outputDevices?.devices)
      ? getState().outputDevices.devices
      : [];
    if (!devices.length) return;
    const actions = devices.map((device) => `outputDevice:${device.id}`);
    const currentIndex = Math.max(0, actions.indexOf(getState().detailFocus));
    const nextIndex = direction === "up" || direction === "left"
      ? (currentIndex - 1 + actions.length) % actions.length
      : (currentIndex + 1) % actions.length;
    patchState({ detailFocus: actions[nextIndex], focusedAction: "outputDevice" });
  },
  activateOutputDeviceFocus() {
    const detailFocus = getState().detailFocus;
    if (detailFocus.startsWith("outputDevice:")) {
      postToHost("outputDeviceSelect", { deviceId: detailFocus.slice("outputDevice:".length) });
    }
  }
};

export function sendAction(action, data = {}) {
  postToHost(action, data);
}

window.overlayUI = overlayUI;
