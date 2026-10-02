import { useEffect, useState } from "preact/hooks";

export const defaultConnectivitySnapshot = {
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
};

export const defaultOutputDevices = {
  defaultId: "living-room",
  devices: [
    { id: "living-room", name: "Living room soundbar", type: "HDMI · 5.1 audio", isDefault: true },
    { id: "gaming-headset", name: "Wireless gaming headset", type: "Bluetooth · Stereo", isDefault: false },
    { id: "controller-audio", name: "DualSense Wireless Controller", type: "USB · Headset output", isDefault: false }
  ]
};

export const initialState = {
  data: {
    title: "GALACTICARE",
    subtitle: "Simulation  |  BrightrockGames",
    clock: "3:36 PM",
    sessionTime: "00:08:44",
    totalPlaytime: "02:02:00",
    logoUrl: "",
    volume: 66,
    muted: false,
    wifiEnabled: true,
    bluetoothEnabled: true
  },
  outputDevices: defaultOutputDevices,
  outputStatus: "",
  connectivity: {
    kind: null,
    snapshot: defaultConnectivitySnapshot,
    status: "",
    actionInFlight: false
  },
  screen: "main",
  modal: null,
  focusedAction: "return",
  detailFocus: ""
};

let state = initialState;
const subscribers = new Set();

export function getState() {
  return state;
}

export function setState(nextState) {
  state = nextState;
  subscribers.forEach((subscriber) => subscriber(state));
  return state;
}

export function patchState(patch) {
  return setState({ ...state, ...patch });
}

export function patchData(patch) {
  return patchState({ data: { ...state.data, ...patch } });
}

export function patchConnectivity(patch) {
  return patchState({ connectivity: { ...state.connectivity, ...patch } });
}

export function subscribe(subscriber) {
  subscribers.add(subscriber);
  return () => subscribers.delete(subscriber);
}

export function useOverlayState() {
  const [, redraw] = useState(0);

  useEffect(() => subscribe(() => redraw((value) => value + 1)), []);
  return state;
}
