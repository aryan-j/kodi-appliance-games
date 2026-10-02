import { render } from "preact";
import { App, handleKeyDown } from "./app.jsx";
import "./bridge.js";

document.addEventListener("keydown", handleKeyDown, { passive: false });
render(<App />, document.getElementById("app"));
