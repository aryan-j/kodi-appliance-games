import { defineConfig } from "vite";
import preact from "@preact/preset-vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const directory = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [preact()],
  base: "./",
  build: {
    outDir: path.resolve(directory, "../web-ui-dist"),
    emptyOutDir: true,
    cssCodeSplit: false,
    sourcemap: false,
    minify: "esbuild",
    rollupOptions: {
      output: {
        entryFileNames: "overlay-runtime.js",
        chunkFileNames: "overlay-chunk-[hash].js",
        assetFileNames: (asset) => {
          if (asset.name && asset.name.endsWith(".css")) return "styles.css";
          return "assets/[name][extname]";
        }
      }
    }
  }
});
