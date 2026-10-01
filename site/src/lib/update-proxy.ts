// The shared update service owns release selection and the Tauri protocol.
// Keep the endpoint embedded in existing app versions stable.
export async function proxyUpdate(
  params: Record<string, string | undefined>,
  request: Request,
  fetcher: typeof fetch = fetch,
): Promise<Response> {
  const { target, arch, version } = params;
  if (
    target !== "darwin" ||
    !["aarch64", "x86_64"].includes(arch ?? "") ||
    !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version ?? "")
  ) return new Response("Unsupported update target", { status: 404 });
  const headers = new Headers();
  const reason = request.headers.get("X-Check-Reason");
  if (reason && ["startup", "periodic", "manual", "host"].includes(reason))
    headers.set("X-Check-Reason", reason);
  // Forward only the optional anonymous installation UUID, never cookies or
  // credentials from the website request.
  const id = request.headers.get("X-CFU-Id");
  if (id && /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(id))
    headers.set("X-CFU-Id", id);
  try {
    const upstream = await fetcher(
      `https://updates.graehlarts.com/machine-control/tauri/${target}/${arch}/${version}`,
      { headers, signal: AbortSignal.timeout(15000), redirect: "manual" },
    );
    if (upstream.status !== 200 && upstream.status !== 204)
      throw new Error(`Update service returned HTTP ${upstream.status}`);
    return new Response(upstream.status === 204 ? null : upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("Update proxy failed:", error instanceof Error ? error.message : "Unknown error");
    return new Response("Updates temporarily unavailable", {
      status: 503,
      headers: { "Cache-Control": "no-store", "Retry-After": "60" },
    });
  }
}
