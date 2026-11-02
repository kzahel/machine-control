/** Shared host wiring: providers must not independently start core dispatch. */
import { ResidentCore } from "./core.ts";
import type { DispatchCommand, Effect, ProviderAdapter } from "./core.ts";

export function dispatchToProvider(
  core: ResidentCore,
  provider: ProviderAdapter,
  command: DispatchCommand,
  effects: (effects: readonly Effect[]) => void,
): boolean {
  if (provider.connection !== command.connection)
    throw new Error("provider_route_mismatch");
  const beginning = core.begin(command);
  // No callback, await or external preparation between the fresh check and
  // provider submission. Adapters get the remaining budget, not the old one.
  if (beginning.started) provider.execute(command, beginning.timeoutMs);
  effects(beginning.effects);
  return beginning.started;
}
