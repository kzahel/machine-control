// @ts-check
import { defineConfig } from "astro/config";
import cloudflare from "@astrojs/cloudflare";

export default defineConfig({
  site: "https://machinecontrol.dev",
  output: "server",
  session: false,
  adapter: cloudflare({
    imageService: "compile",
  }),
});
