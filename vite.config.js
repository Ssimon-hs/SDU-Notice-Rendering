import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist" },
  server: {
    host: "127.0.0.1",
    port: Number(process.env.YIJIAN_WEB_PORT || 5173),
    proxy: {
      "/api": `http://127.0.0.1:${process.env.YIJIAN_API_PORT || 8765}`,
    },
  },
});