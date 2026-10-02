import { normalizeSnapshot } from "../connector-contract.js";

// Kodi's current WebView2 host already implements this transport. Keeping the
// adapter explicit makes it possible to reuse the UI from a different host
// without importing Kodi-specific code into a component.
export function normalizeKodiSnapshot(payload) {
  return normalizeSnapshot(payload);
}

export function createKodiConnector(transport) {
  return {
    name: "kodi",
    normalize: normalizeKodiSnapshot,
    dispatch(action, data = {}) {
      return transport.post({ type: "action", action, ...data });
    }
  };
}
