/*
 * Connector boundary shared by Kodi, Playnite, and the browser demo.
 *
 * A connector supplies this normalized snapshot:
 * {
 *   title, subtitle, clock, sessionTime, totalPlaytime, logoUrl,
 *   volume, muted, wifiEnabled, bluetoothEnabled,
 *   outputDevices, connectivitySnapshot, focusedAction
 * }
 *
 * Commands are intentionally small strings with JSON-safe arguments. The
 * frontend never calls Kodi, Playnite, Windows, or an audio API directly.
 */

export const connectorActions = Object.freeze([
  "return", "exit", "volume", "outputDevice", "outputDeviceClose",
  "outputDeviceSelect", "wifi", "wifiDetails", "wifiRefresh", "wifiConnect",
  "wifiSettings", "bluetooth", "bluetoothDetails", "bluetoothRefresh",
  "bluetoothSettings", "connectivityClose", "sleep", "restart", "shutdown",
  "volumeDown", "volumeUp", "confirmNo", "confirmYes"
]);

export function normalizeSnapshot(payload = {}) {
  const source = payload || {};
  return {
    title: typeof source.title === "string" ? source.title : undefined,
    subtitle: typeof source.subtitle === "string" ? source.subtitle : undefined,
    clock: typeof source.clock === "string" ? source.clock : undefined,
    sessionTime: typeof source.sessionTime === "string" ? source.sessionTime : undefined,
    totalPlaytime: typeof source.totalPlaytime === "string" ? source.totalPlaytime : undefined,
    logoUrl: typeof source.logoUrl === "string" ? source.logoUrl : undefined,
    volume: Number.isFinite(Number(source.volume)) ? Number(source.volume) : undefined,
    muted: typeof source.muted === "boolean" ? source.muted : undefined,
    wifiEnabled: typeof source.wifiEnabled === "boolean" ? source.wifiEnabled : undefined,
    bluetoothEnabled: typeof source.bluetoothEnabled === "boolean" ? source.bluetoothEnabled : undefined,
    outputDevices: source.outputDevices || undefined,
    connectivitySnapshot: source.connectivitySnapshot || undefined,
    focusedAction: typeof source.focusedAction === "string" ? source.focusedAction : undefined
  };
}
