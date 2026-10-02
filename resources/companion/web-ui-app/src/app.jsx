import { useState } from "preact/hooks";
import { sendAction } from "./bridge.js";
import { Icon } from "./icons.jsx";
import { getState, useOverlayState } from "./store.js";
import "./styles.css";

const actionClass = (state, action, extra = "") =>
  `${extra} ${state.focusedAction === action ? "is-controller-focused" : ""}`.trim();

function ActionButton({ action, label, hint, icon, state, className = "", onClick, children, ...props }) {
  return (
    <button
      type="button"
      className={actionClass(state, action, `ui-action ${className}`)}
      data-action={action}
      onClick={onClick || (() => sendAction(action))}
      {...props}
    >
      {icon && <span className="action-icon"><Icon name={icon} size={22} /></span>}
      {label && <span className="action-copy"><span className="action-label">{label}</span>{hint && <span className="action-hint">{hint}</span>}</span>}
      {children}
    </button>
  );
}

function SurfaceHeading({ label, caption }) {
  return (
    <div className="surface-heading">
      <span className="surface-label">{label}</span>
      {caption && <span className="surface-caption">{caption}</span>}
    </div>
  );
}

function GameSurface({ state }) {
  const prompt = state.modal?.type === "power" && state.modal.action === "exit";
  return (
    <section className={`control-group surface surface--game ${prompt ? "surface--prompt" : ""}`} aria-label="Game">
      <SurfaceHeading label="Game" />
      {prompt ? <PowerPrompt state={state} /> : (
        <div className="game-grid">
          <ActionButton action="return" icon="return" label="Return to game" hint="Resume" state={state} className="game-tile game-tile--return" />
          <ActionButton action="exit" icon="exit" label="Exit game" hint="Close session" state={state} className="game-tile game-tile--exit" />
        </div>
      )}
    </section>
  );
}

function VolumeAction({ state }) {
  const volume = Math.max(0, Math.min(100, Number(state.data.volume) || 0));
  return (
    <ActionButton
      action="volume"
      state={state}
      className={`volume-row ${state.data.muted ? "is-muted" : ""}`}
      aria-label={`Volume ${volume} percent. Click to mute or unmute.`}
    >
      <span className="action-icon"><Icon name={state.data.muted ? "mute" : "volume"} size={24} /></span>
      <span className="action-copy volume-copy"><span className="action-label">Volume</span><span className="volume-badge">{state.data.muted ? "Muted" : "Sound on"}</span></span>
      <span className="volume-control" aria-hidden="true">
        <span className="volume-meter"><span className="volume-fill" style={{ width: `${volume}%` }} /><span className="volume-thumb" style={{ left: `${volume}%` }} /></span>
        <span className="volume-value">{volume}%</span>
      </span>
    </ActionButton>
  );
}

function AudioSurface({ state }) {
  const output = state.outputDevices || {};
  const selected = Array.isArray(output.devices) && output.devices.find((device) => device.id === output.defaultId);
  return (
    <section className="control-group surface surface--audio" aria-label="Audio">
      <SurfaceHeading label="Audio" />
      <div className="audio-controls">
        <VolumeAction state={state} />
        <ActionButton action="outputDevice" icon="output" label="Output device" hint={selected?.name || "Choose where game audio plays"} state={state} className="output-device-row">
          <span className="trailing-action"><span>{Array.isArray(output.devices) ? `${output.devices.length} devices` : "Choose"}</span><Icon name="chevron" size={20} /></span>
        </ActionButton>
      </div>
    </section>
  );
}

function ConnectionCard({ kind, label, state }) {
  const enabled = kind === "wifi" ? state.data.wifiEnabled : state.data.bluetoothEnabled;
  const source = state.connectivity.snapshot?.[kind] || {};
  const summary = kind === "wifi"
    ? (source.ssid || (enabled ? "Available networks" : "Wi-Fi is off"))
    : ((source.devices || []).find((device) => device.status === "Connected")?.name || (enabled ? "Paired devices" : "Bluetooth is off"));
  const status = enabled ? (source.state || "On") : "Off";
  return (
    <div className={`connection-card ${enabled ? "is-enabled" : "is-disabled"}`} role="group" aria-label={`${label} connection`}>
      <button
        type="button"
        className={actionClass(state, kind, "connection-toggle")}
        data-connection-action={kind}
        data-action={kind}
        aria-pressed={enabled}
        onClick={() => sendAction(kind)}
      >
        <span className="connection-icon"><Icon name={kind} size={22} /></span>
        <span className="connection-copy"><span className="action-label">{label}</span><span className="connection-summary">{summary}</span><span className="connection-status">{status}</span></span>
        <span className={`switch ${enabled ? "is-on" : ""}`} aria-hidden="true"><span className="switch-thumb" /></span>
      </button>
      <button
        type="button"
        className="connection-details"
        data-connectivity-details={kind}
        data-action={`${kind}Details`}
        aria-label={`Open ${label} details`}
        onClick={() => sendAction(`${kind}Details`)}
      >
        <ControllerGlyph name="square" />
      </button>
    </div>
  );
}

function ConnectionsSurface({ state }) {
  return (
    <section className="control-group surface surface--connections" aria-label="Connections">
      <SurfaceHeading label="Connections" caption="Toggle or open details" />
      <div className="connection-grid">
        <ConnectionCard kind="wifi" label="Wi-Fi" state={state} />
        <ConnectionCard kind="bluetooth" label="Bluetooth" state={state} />
      </div>
    </section>
  );
}

const powerMeta = {
  sleep: { label: "Sleep", hint: "Suspend", icon: "sleep" },
  restart: { label: "Restart", hint: "Reboot", icon: "restart" },
  shutdown: { label: "Shut down", hint: "Power off", icon: "shutdown" }
};

function PowerSurface({ state }) {
  const prompt = state.modal?.type === "power" && state.modal.action !== "exit";
  return (
    <section className={`control-group surface surface--power ${prompt ? "surface--prompt" : ""}`} aria-label="Power">
      <SurfaceHeading label="Power" caption="System controls" />
      {prompt ? <PowerPrompt state={state} /> : (
        <div className="power-grid">
          {Object.entries(powerMeta).map(([action, item]) => (
            <ActionButton key={action} action={action} icon={item.icon} label={item.label} hint={item.hint} state={state} className={`power-tile ${action === "shutdown" ? "power-tile--danger" : ""}`} data-power-action={action} />
          ))}
        </div>
      )}
    </section>
  );
}

function PowerPrompt({ state }) {
  const prompt = state.modal || {};
  const danger = prompt.action === "shutdown" || prompt.action === "exit";
  return (
    <div className={`power-prompt ${danger ? "power-prompt--danger" : ""}`} role="dialog" aria-live="polite" aria-label="Confirm action">
      <div className="prompt-copy"><span className="prompt-eyebrow">CONFIRM ACTION</span><strong>{prompt.title || "Are you sure?"}</strong><span>This will end the current session.</span></div>
      <div className="prompt-actions">
        <button type="button" className={actionClass(state, "confirmNo", "prompt-button")} onClick={() => sendAction("confirmNo")}>Cancel</button>
        <button type="button" className={actionClass(state, "confirmYes", "prompt-button prompt-button--confirm")} onClick={() => sendAction("confirmYes")}>{prompt.action === "exit" ? "Exit game" : powerMeta[prompt.action]?.label || "Continue"}</button>
      </div>
    </div>
  );
}

function MainControls({ state }) {
  return (
    <section className="control-panel" aria-label="Pause menu controls">
      <GameSurface state={state} />
      <AudioSurface state={state} />
      <ConnectionsSurface state={state} />
      <PowerSurface state={state} />
    </section>
  );
}

function OutputDevices({ state }) {
  const devices = Array.isArray(state.outputDevices?.devices) ? state.outputDevices.devices : [];
  return (
    <section className="detail-panel surface" aria-label="Output devices">
      <div className="detail-header"><button type="button" className="back-button" onClick={() => sendAction("outputDeviceClose")}><Icon name="arrowLeft" size={20} /><span>Audio</span></button><SurfaceHeading label="Output device" caption="Choose where game audio plays" /></div>
      <div className="detail-list">
        {devices.map((device) => {
          const action = `outputDevice:${device.id}`;
          const focused = state.detailFocus === action;
          return <button type="button" key={device.id} className={`device-option ${focused ? "is-controller-focused" : ""}`} data-device-id={device.id} onClick={() => sendAction("outputDeviceSelect", { deviceId: device.id })}><span className="device-icon"><Icon name="output" size={22} /></span><span className="device-copy"><strong>{device.name}</strong><span>{device.type || "Audio output"}</span></span>{device.isDefault && <Icon name="check" size={22} className="device-check" />}</button>;
        })}
      </div>
      {state.outputStatus && <p className="detail-status" aria-live="polite">{state.outputStatus}</p>}
    </section>
  );
}

function ConnectivityDetails({ state }) {
  const kind = state.connectivity.kind || "wifi";
  const snapshot = state.connectivity.snapshot?.[kind] || {};
  const enabled = kind === "wifi" ? state.data.wifiEnabled : state.data.bluetoothEnabled;
  const networks = Array.isArray(snapshot.networks) ? snapshot.networks : [];
  const devices = Array.isArray(snapshot.devices) ? snapshot.devices : [];
  return (
    <section className="detail-panel surface" aria-label={`${kind === "wifi" ? "Wi-Fi" : "Bluetooth"} details`}>
      <div className="detail-header"><button type="button" className="back-button" onClick={() => sendAction("connectivityClose")}><Icon name="arrowLeft" size={20} /><span>Connections</span></button><SurfaceHeading label={kind === "wifi" ? "Wi-Fi" : "Bluetooth"} caption={enabled ? "Connected devices and networks" : "Turned off"} /></div>
      <div className="detail-toolbar"><span className="detail-state"><span className={`state-dot ${enabled ? "is-on" : ""}`} />{enabled ? (snapshot.state || "On") : "Off"}</span><button type="button" className={actionClass(state, `${kind}Refresh`, "small-action")} data-connectivity-action={`${kind}Refresh`} onClick={() => sendAction(`${kind}Refresh`)}><Icon name="refresh" size={18} />Refresh</button></div>
      {kind === "wifi" ? (
        <div className="detail-list">
          {networks.map((network) => {
            const networkAction = `wifiNetwork:${network.ssid}`;
            return <button type="button" key={network.ssid} className={actionClass(state, networkAction, "network-option")} data-connectivity-action="wifiConnect" data-ssid={network.ssid} onClick={() => sendAction("wifiConnect", { ssid: network.ssid })}><span className="network-signal" style={{ "--signal": `${network.signal || 0}%` }} /><span className="device-copy"><strong>{network.ssid}</strong><span>{network.authentication || "Network"} · {network.signal || 0}% signal</span></span><Icon name="chevron" size={20} /></button>;
          })}
          {!networks.length && <p className="empty-state">No networks found.</p>}
        </div>
      ) : (
        <div className="detail-list">
          {devices.map((device) => <div className="device-option device-option--static" key={device.name}><span className="device-icon"><Icon name="bluetooth" size={22} /></span><span className="device-copy"><strong>{device.name}</strong><span>{device.status || "Paired"}{device.battery !== null && device.battery !== undefined ? ` · ${device.battery}% battery` : ""}</span></span></div>)}
          {!devices.length && <p className="empty-state">No paired devices found.</p>}
        </div>
      )}
      <div className="detail-footer"><button type="button" className={actionClass(state, `${kind}Settings`, "text-action")} data-connectivity-action={`${kind}Settings`} onClick={() => sendAction(`${kind}Settings`)}><Icon name="settings" size={18} />Open Windows settings</button><button type="button" className={actionClass(state, "connectivityClose", "text-action")} data-connectivity-action="connectivityClose" onClick={() => sendAction("connectivityClose")}>Close</button></div>
      {state.connectivity.status && <p className="detail-status" aria-live="polite">{state.connectivity.status}</p>}
    </section>
  );
}

function Header({ state }) {
  return (
    <header className="overlay-header">
      <div className="overlay-identity"><h1 className="overlay-title">{state.data.title}</h1><p className="overlay-subtitle">{state.data.subtitle}</p></div>
      <section className="status-widget" aria-label="System time and playtime">
        <div className="system-time"><Icon name="clock" size={22} /><time>{state.data.clock}</time></div>
        <div className="status-divider" />
        <div className="status-stats"><div className="status-stat"><Icon name="timer" size={20} /><span><strong>{state.data.sessionTime}</strong><small>This session</small></span></div><div className="status-stat"><Icon name="history" size={20} /><span><strong>{state.data.totalPlaytime}</strong><small>Total play time</small></span></div></div>
      </section>
    </header>
  );
}

function GameLogo({ state }) {
  const [broken, setBroken] = useState(false);
  const hasLogo = state.data.logoUrl && !broken;
  return <div className="game-logo" aria-label={`${state.data.title} logo`}>{hasLogo ? <img src={state.data.logoUrl} alt="" className="game-logo-image" onError={() => setBroken(true)} /> : <span className="game-logo-fallback">{state.data.title}</span>}</div>;
}

const controllerGlyphs = {
  select: "face-cross.svg",
  back: "face-circle.svg",
  square: "face-square.svg",
  return: "ps-badge.svg",
  volumeDown: "trigger-l2.svg",
  volumeUp: "trigger-r2.svg"
};

function ControllerGlyph({ name, wide = false }) {
  return <span className={`prompt-glyph ${wide ? "prompt-glyph--wide" : ""}`}><img src={`./assets/controller-glyphs/${controllerGlyphs[name]}`} alt="" /></span>;
}

function Footer() {
  return <footer className="footer-legend" aria-label="Controller controls"><span className="prompt-item"><ControllerGlyph name="select" /><span>Select</span></span><span className="prompt-item"><ControllerGlyph name="back" /><span>Back</span></span><span className="prompt-item"><ControllerGlyph name="return" wide /><span>Return to game</span></span><span className="prompt-item"><ControllerGlyph name="volumeDown" wide /><span>Volume −</span></span><span className="prompt-item"><ControllerGlyph name="volumeUp" wide /><span>Volume +</span></span></footer>;
}

function Toast({ message }) {
  return message ? <div className="toast" role="status">{message}</div> : null;
}

export function App() {
  const state = useOverlayState();
  const detailView = state.screen === "output"
    ? <OutputDevices state={state} />
    : state.screen === "connectivity"
      ? <ConnectivityDetails state={state} />
      : <MainControls state={state} />;
  const toast = state.modal?.type === "toast" ? state.modal.message : "";
  return (
    <main className="stage-wrapper"><div className="stage" aria-label="Gaming overlay"><div className="background-layer" /><div className="overlay-shell"><Header state={state} /><div className="stage-row"><div className="content-row">{detailView}<GameLogo state={state} /></div></div><Footer /></div><Toast message={toast} /></div></main>
  );
}

export function handleKeyDown(event) {
  const state = getState();
  if (event.key === "Escape") {
    event.preventDefault();
    sendAction(state.modal ? "confirmNo" : state.screen === "main" ? "return" : state.screen === "output" ? "outputDeviceClose" : "connectivityClose");
    return;
  }
  if (event.key === "Enter" || event.key === " ") {
    const target = event.target?.closest?.("[data-action]");
    if (target && target.dataset.action) return;
  }
}
