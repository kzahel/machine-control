import type { APIRoute } from "astro";
import { loadDesktopRelease } from "../../../../lib/desktop-release.ts";

export const GET: APIRoute = async ({ params }) => {
  const { arch, format } = params;
  if ((arch !== "amd64" && arch !== "arm64") || (format !== "appimage" && format !== "deb"))
    return new Response("Unsupported Linux package", { status: 404 });
  try {
    const release = await loadDesktopRelease();
    if (!release?.linuxDownloads)
      return new Response("No public Linux release yet. See /downloads/.", {
        status: 404, headers: { "Cache-Control": "public, max-age=60" },
      });
    return new Response(null, {
      status: 302, headers: { Location: release.linuxDownloads[arch][format],
                             "Cache-Control": "public, max-age=300" },
    });
  } catch {
    return new Response("Downloads temporarily unavailable. Try again shortly.", {
      status: 503, headers: { "Retry-After": "60", "Cache-Control": "no-store" },
    });
  }
};
