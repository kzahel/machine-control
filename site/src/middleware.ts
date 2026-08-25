import { defineMiddleware } from "astro:middleware";

const STYLE_SOURCE = import.meta.env.DEV
  ? "style-src 'self' 'unsafe-inline'"
  : "style-src 'self'";

const SECURITY_HEADERS = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "base-uri 'self'",
    "connect-src 'self' https://challenges.cloudflare.com",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "frame-src https://challenges.cloudflare.com",
    "img-src 'self' data:",
    "object-src 'none'",
    "script-src 'self' https://challenges.cloudflare.com",
    STYLE_SOURCE,
  ].join("; "),
  "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
} as const;

export const onRequest = defineMiddleware(async (context, next) => {
  if (context.url.hostname === "www.machinecontrol.dev") {
    const destination = new URL(context.url);
    destination.hostname = "machinecontrol.dev";
    return Response.redirect(destination, 308);
  }

  const response = await next();
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    response.headers.set(name, value);
  }
  return response;
});
