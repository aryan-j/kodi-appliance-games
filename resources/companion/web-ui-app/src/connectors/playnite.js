import { normalizeSnapshot } from "../connector-contract.js";

function formatDuration(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = String(Math.floor(total / 3600)).padStart(2, "0");
  const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
  const remainder = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}:${remainder}`;
}

function sessionSeconds(activatedTime, now = Date.now()) {
  if (!activatedTime) return 0;
  const started = new Date(activatedTime).getTime();
  if (!Number.isFinite(started)) return 0;
  return Math.max(0, (now - started) / 1000);
}

/*
 * Maps the public RunningApp shape used by hikaps/playnite-overlay into the
 * frontend snapshot. ImagePath is deliberately not treated as a browser URL:
 * the Playnite transport must expose it through a local asset endpoint and
 * pass that endpoint as logoUrl.
 */
export function normalizePlayniteRunningApp(app = {}, now = Date.now()) {
  return normalizeSnapshot({
    title: app.Title || app.title || "Game",
    subtitle: app.Subtitle || app.subtitle || "Playnite",
    sessionTime: formatDuration(sessionSeconds(app.ActivatedTime || app.activatedTime, now)),
    totalPlaytime: formatDuration(app.TotalPlaytime || app.totalPlaytime),
    logoUrl: app.LogoUrl || app.logoUrl || app.ImageUrl || app.imageUrl || "",
    source: "playnite"
  });
}

export function createPlayniteConnector(transport) {
  return {
    name: "playnite",
    normalize: normalizePlayniteRunningApp,
    async snapshot() {
      const app = await transport.request("overlay.snapshot");
      return normalizePlayniteRunningApp(app);
    },
    dispatch(action, data = {}) {
      return transport.request("overlay.action", { action, ...data });
    },
    subscribe(listener) {
      return transport.subscribe("overlay.snapshot", (payload) => listener(normalizePlayniteRunningApp(payload)));
    }
  };
}
