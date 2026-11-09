/** Owned browser operation vocabulary, independent of transport and OS. */
export const browserOperations = [
  "browser.tabs",
  "browser.wait",
  "browser.navigate",
  "browser.snapshot",
  "browser.click",
  "browser.type",
  "browser.key",
  "browser.capture",
  "browser.upload",
  "browser.cdp",
  "browser.eval",
  "browser.release",
  "browser.dialog",
] as const;
export type BrowserOperation = (typeof browserOperations)[number];
export type Json =
  | null
  | boolean
  | number
  | string
  | readonly Json[]
  | { readonly [key: string]: Json };
export type Parameters = Readonly<Record<string, Json>>;
export function observes(operation: string): boolean {
  return [
    "browser.tabs",
    "browser.wait",
    "browser.snapshot",
    "browser.capture",
  ].includes(operation);
}
export function needsDevtools(operation: string): boolean {
  return operation === "browser.cdp" || operation === "browser.eval";
}
const CLAIM_ID = /^c-[a-f0-9]{24}$/;
const SESSION_REF = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
/**
 * Optional claim attribution: `owner` names the target-use claim a request
 * runs under, with that claim's remaining lease; `ownerClaimId` scopes a
 * release to that claim's tabs. Both are self-asserted, never authority.
 * Null means absent, as Windows' typed relay already treats it.
 */
export function validOwnership(
  operation: string,
  request: Readonly<Record<string, unknown>>,
): boolean {
  const owner = request.owner ?? undefined;
  if (owner !== undefined) {
    if (!owner || typeof owner !== "object" || Array.isArray(owner)) return false;
    const fields = owner as Readonly<Record<string, unknown>>;
    if (Object.keys(fields).some((key) => !["claimId", "leaseSeconds", "sessionRef"].includes(key)))
      return false;
    if (typeof fields.claimId !== "string" || !CLAIM_ID.test(fields.claimId)) return false;
    if (
      typeof fields.leaseSeconds !== "number" ||
      !Number.isSafeInteger(fields.leaseSeconds) ||
      fields.leaseSeconds < 1 ||
      fields.leaseSeconds > 86_400
    )
      return false;
    if (
      fields.sessionRef !== undefined &&
      (typeof fields.sessionRef !== "string" || !SESSION_REF.test(fields.sessionRef))
    )
      return false;
  }
  const scope = request.ownerClaimId ?? undefined;
  return (
    scope === undefined ||
    (operation === "browser.release" && typeof scope === "string" && CLAIM_ID.test(scope))
  );
}
/** Copy and freeze a bounded JSON tree; providers cannot mutate admitted work. */
export function parameters(value: unknown, maximum = 1024 * 1024): Parameters {
  let nodes = 0,
    bytes = 0;
  function copy(item: unknown, depth: number): Json {
    if (++nodes > 100_000 || depth > 24) throw new Error("invalid_parameters");
    if (item === null || typeof item === "boolean") return item;
    if (typeof item === "number" && Number.isFinite(item)) return item;
    if (typeof item === "string") {
      bytes += item.length * 3;
      if (bytes > maximum) throw new Error("invalid_parameters");
      return item;
    }
    if (Array.isArray(item))
      return Object.freeze(item.map((part) => copy(part, depth + 1)));
    if (
      item &&
      typeof item === "object" &&
      (Object.getPrototypeOf(item) === Object.prototype ||
        Object.getPrototypeOf(item) === null)
    ) {
      const result: Record<string, Json> = Object.create(null) as Record<
        string,
        Json
      >;
      for (const [key, part] of Object.entries(item)) {
        bytes += key.length * 3 + 8;
        if (bytes > maximum) throw new Error("invalid_parameters");
        Object.defineProperty(result, key, {
          value: copy(part, depth + 1),
          enumerable: true,
        });
      }
      return Object.freeze(result);
    }
    throw new Error("invalid_parameters");
  }
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw new Error("invalid_parameters");
  return copy(value, 0) as Parameters;
}
