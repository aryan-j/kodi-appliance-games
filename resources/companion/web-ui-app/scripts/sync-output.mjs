import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appDirectory = path.dirname(fileURLToPath(import.meta.url));
const distDirectory = path.resolve(appDirectory, "..", "..", "web-ui-dist");
const outputDirectory = path.resolve(appDirectory, "..", "..", "web-ui");

fs.mkdirSync(outputDirectory, { recursive: true });

for (const fileName of ["index.html", "overlay-runtime.js", "styles.css"]) {
  fs.copyFileSync(
    path.join(distDirectory, fileName),
    path.join(outputDirectory, fileName)
  );
}

// Keep the old artwork directory available for older packaged assets. The new
// UI uses inline icons and only asks the host for the game logo URL.
for (const fileName of ["design-tokens.css", "runtime-overrides.css"]) {
  const legacyPath = path.join(outputDirectory, fileName);
  if (fs.existsSync(legacyPath)) fs.unlinkSync(legacyPath);
}

console.log(`Synced overlay build to ${outputDirectory}`);
