import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  root: "../extension",
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: {
      react: new URL("./node_modules/react", import.meta.url).pathname,
      "react-dom": new URL("./node_modules/react-dom", import.meta.url)
        .pathname,
      "lightweight-charts": new URL(
        "./node_modules/lightweight-charts",
        import.meta.url,
      ).pathname,
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        panel: new URL("../extension/panel.html", import.meta.url).pathname,
        popup: new URL("../extension/popup.html", import.meta.url).pathname,
      },
    },
  },
});
