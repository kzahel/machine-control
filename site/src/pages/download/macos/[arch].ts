import type { APIRoute } from "astro";
import { loadDesktopRelease } from "../../../lib/desktop-release.ts";

export const GET: APIRoute = async ({ params }) => {
  const arch = params.arch;
  if (arch !== "arm64" && arch !== "x86_64")
    return new Response("Unsupported Mac architecture", { status: 404 });
  try {
    const release = await loadDesktopRelease();
    if (!release)
      return new Response("No public Mac release yet. See /downloads/.", {
        status: 404,
        headers: { "Cache-Control": "public, max-age=60" },
      });
    return new Response(null, {
      status: 302,
      headers: {
        Location: release.downloads[arch],
        "Cache-Control": "public, max-age=300",
      },
    });
  } catch {
    return new Response(
      "Downloads temporarily unavailable. Try again shortly.",
      {
        status: 503,
        headers: { "Retry-After": "60", "Cache-Control": "no-store" },
      },
    );
  }
};
