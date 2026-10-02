const paths = {
  return: <><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v6h-6"/></>,
  exit: <><path d="M10 5H6.8A1.8 1.8 0 0 0 5 6.8v10.4A1.8 1.8 0 0 0 6.8 19H10"/><path d="M13 8l4 4-4 4"/><path d="M17 12H9"/></>,
  volume: <><path d="M4 10v4h3l4 3V7l-4 3H4Z"/><path d="M15 9.5a4 4 0 0 1 0 5"/></>,
  mute: <><path d="M4 10v4h3l4 3V7l-4 3H4Z"/><path d="m16 10 4 4m0-4-4 4"/></>,
  output: <><rect x="3.5" y="5" width="12" height="14" rx="2"/><path d="M7 9h5M7 13h3"/><path d="M19.5 8.5v7M17.5 10.5v3"/></>,
  wifi: <><path d="M3 9.5a14 14 0 0 1 18 0"/><path d="M6.5 13a8.5 8.5 0 0 1 11 0"/><path d="M10 16.5a3.2 3.2 0 0 1 4 0"/><path d="M12 20h.01"/></>,
  bluetooth: <><path d="m8 7 8 10-4 3V4l4 3-8 10"/></>,
  sleep: <><path d="M20 13.5A8.5 8.5 0 1 1 10.5 4 7 7 0 0 0 20 13.5Z"/></>,
  restart: <><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v6h-6"/></>,
  shutdown: <><path d="M12 3v8"/><path d="M7.05 5.65a8 8 0 1 0 9.9 0"/></>,
  clock: <><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/></>,
  timer: <><circle cx="12" cy="13" r="7.5"/><path d="M9 3h6M12 5.5V3M12 13l3-2"/></>,
  history: <><path d="M4 12a8 8 0 1 0 2.3-5.65"/><path d="M4 5v5h5"/><path d="M12 8v5l3 2"/></>,
  chevron: <path d="m9 5 7 7-7 7"/>,
  arrowLeft: <><path d="m15 5-7 7 7 7"/><path d="M8 12h12"/></>,
  refresh: <><path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v6h-6"/></>,
  settings: <><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/><path d="m19.4 15 .1.1a1.8 1.8 0 0 1-2.55 2.55l-.1-.1a1.8 1.8 0 0 0-3.07 1.28v.17a1.8 1.8 0 0 1-3.6 0v-.17a1.8 1.8 0 0 0-3.07-1.28l-.1.1a1.8 1.8 0 0 1-2.55-2.55l.1-.1a1.8 1.8 0 0 0-1.28-3.07H3.2a1.8 1.8 0 0 1 0-3.6h.17a1.8 1.8 0 0 0 1.28-3.07l-.1-.1A1.8 1.8 0 0 1 7.1 2.6l.1.1a1.8 1.8 0 0 0 3.07-1.28v-.17a1.8 1.8 0 0 1 3.6 0v.17a1.8 1.8 0 0 0 3.07 1.28l.1-.1a1.8 1.8 0 0 1 2.55 2.55l-.1.1a1.8 1.8 0 0 0 1.28 3.07h.17a1.8 1.8 0 0 1 0 3.6h-.17A1.8 1.8 0 0 0 19.4 15Z"/></>,
  check: <path d="m5 12 4 4L19 6"/>
};

export function Icon({ name, size = 22, className = "" }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.chevron}
    </svg>
  );
}
