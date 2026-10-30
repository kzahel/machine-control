export type Scope = "observe" | "control" | "browser" | "devtools";
export type AccessChoices = { scopes: Scope[]; duration: number };

export const defaultAccessChoices: AccessChoices = {
  scopes: ["observe", "control"],
  duration: 900,
};
const key = "machine-control.access-choices.v1";
const scopes = new Set(["observe", "control", "browser", "devtools"]);

export function validAccessChoices(value: unknown): value is AccessChoices {
  if (!value || typeof value !== "object") return false;
  const candidate = value as AccessChoices;
  return (
    Array.isArray(candidate.scopes) &&
    candidate.scopes.every((scope) => scopes.has(scope)) &&
    new Set(candidate.scopes).size === candidate.scopes.length &&
    Number.isInteger(candidate.duration) &&
    (candidate.duration === 0 ||
      (candidate.duration >= 60 && candidate.duration <= 28800))
  );
}

// This stores form choices only. Loading it never invokes an arming command.
export function readAccessChoices(): AccessChoices | undefined {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "null");
    return validAccessChoices(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

export function writeAccessChoices(value: AccessChoices): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
