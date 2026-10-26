// Cooperative presentation policy, not containment of arbitrary page scripts
// or a caller with desktop/shell access. Never turn an ordinary browser action
// into an implicit request to take over the user's foreground.
export function presentationParams(method, params = {}, allowForeground = false) {
  if (!params || typeof params !== "object" || Array.isArray(params)) {
    throw Object.assign(new Error("CDP parameters must be an object"), { code: "invalid_request", cdpCode: -32602 });
  }
  if (!allowForeground && ["Page.bringToFront", "Target.activateTarget"].includes(method)) {
    throw Object.assign(new Error("Foreground presentation requires explicit opt-in; keep ordinary browser work in the background"),
      { code: "foreground_required", cdpCode: -32000 });
  }
  if (method === "Target.createTarget") {
    if (!allowForeground && (params.background === false || params.newWindow === true)) {
      throw Object.assign(new Error("Foreground tab/window creation requires explicit opt-in"),
        { code: "foreground_required", cdpCode: -32000 });
    }
    return { ...params, background: params.background ?? true };
  }
  return params;
}
