/// <reference types="astro/client" />

interface Window {
  turnstile?: {
    reset: (widgetId?: string | HTMLElement) => void;
  };
}

declare namespace Cloudflare {
  interface Env {
    SIGNUPS: D1Database;
    TURNSTILE_SITE_KEY: string;
    TURNSTILE_SECRET_KEY: string;
  }
}
