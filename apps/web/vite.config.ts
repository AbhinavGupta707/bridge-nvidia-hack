import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  envPrefix: ["VITE_", "ALLOW_CLOUD"],
  plugins: [react()],
});
