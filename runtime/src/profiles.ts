import type { ProviderConnection } from "./core.ts";

export interface Profile {
  readonly profileId: string;
  readonly extensionId: string;
  readonly installationId: string;
  name: string;
  enabled: boolean;
  connection?: ProviderConnection;
}

/** Installation selectors and presentation metadata; contains no grant engine. */
export class Profiles {
  readonly #known = new Map<string, Profile>();

  announce(extensionId: string, metadata: unknown): Profile {
    if (
      !/^[a-p]{32}$/.test(extensionId) ||
      !metadata ||
      typeof metadata !== "object" ||
      Array.isArray(metadata)
    )
      throw new Error("browser_profile_protocol_required");
    const value = metadata as Record<string, unknown>;
    if (
      value.protocolVersion !== 1 ||
      typeof value.installationId !== "string" ||
      !/^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(
        value.installationId,
      ) ||
      typeof value.name !== "string" ||
      value.name.trim() !== value.name ||
      value.name.length < 1 ||
      value.name.length > 64 ||
      /[\u0000-\u001f\u007f]/.test(value.name) ||
      typeof value.enabled !== "boolean"
    )
      throw new Error("browser_profile_protocol_required");
    const profileId = `extension.${extensionId}:${value.installationId}`;
    const previous = this.#known.get(profileId);
    if (previous?.connection) throw new Error("profile_conflict");
    if (!previous && this.#known.size >= 256)
      throw new Error("browser_profile_capacity");
    const profile: Profile = {
      profileId,
      extensionId,
      installationId: value.installationId,
      name: value.name,
      enabled: value.enabled,
    };
    this.#known.set(profileId, profile);
    return profile;
  }

  update(profile: Profile, metadata: unknown): void {
    if (this.#known.get(profile.profileId) !== profile || !profile.connection)
      throw new Error("profile_unavailable");
    if (
      !metadata ||
      typeof metadata !== "object" ||
      (metadata as Record<string, unknown>).installationId !==
        profile.installationId
    )
      throw new Error("profile_identity_changed");
    const connection = profile.connection;
    delete profile.connection;
    try {
      const updated = this.announce(profile.extensionId, metadata);
      if (updated.profileId !== profile.profileId) {
        this.#known.delete(updated.profileId);
        throw new Error("profile_identity_changed");
      }
      profile.name = updated.name;
      profile.enabled = updated.enabled;
    } finally {
      profile.connection = connection;
      this.#known.set(profile.profileId, profile);
    }
  }

  disconnected(profile: Profile, connection: ProviderConnection): void {
    if (profile.connection === connection) delete profile.connection;
  }

  select(selector: string | undefined, approved: readonly string[]): Profile {
    let profile: Profile | undefined;
    if (selector) {
      profile = this.#known.get(selector);
      if (!profile) {
        const matches = [...this.#known.values()].filter(
          (item) => item.name === selector,
        );
        if (matches.length > 1) throw new Error("browser_profile_ambiguous");
        profile = matches[0];
      }
    } else {
      if (!approved.length) throw new Error("approval_required");
      if (approved.length !== 1) throw new Error("browser_profile_required");
      profile = this.#known.get(approved[0]!);
    }
    if (!profile?.connection) throw new Error("profile_unavailable");
    if (!profile.enabled) throw new Error("profile_disabled");
    return profile;
  }

  get(id: string): Profile | undefined {
    return this.#known.get(id);
  }
  state(): readonly object[] {
    return [...this.#known.values()].map((profile) => ({
      profileId: profile.profileId,
      name: profile.name,
      enabled: profile.enabled,
      connected: !!profile.connection,
      extensionId: profile.extensionId,
    }));
  }
}
