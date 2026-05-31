import { defineConfig } from 'astro/config';

// Fully static output (the default) — builds to ./dist and deploys
// directly to Cloudflare Pages with no adapter required.
export default defineConfig({
  site: 'https://www.linkcanary.io',
});
