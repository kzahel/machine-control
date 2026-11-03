/** Stateful browser effects; authorization is exclusively ResidentCore's job. */
import type {
  DispatchCommand,
  ProviderAdapter,
  ProviderConnection,
  ProviderReply,
} from "../src/core.ts";
import type { Parameters } from "../src/browser-contract.ts";

export class ReferenceBrowser implements ProviderAdapter {
  readonly connection: ProviderConnection;
  readonly received: DispatchCommand[] = [];
  readonly #replies = new Map<DispatchCommand, ProviderReply>();
  readonly #tabs = new Map<
    number,
    {
      url: string;
      title: string;
      revision: number;
      clicks: number;
      text: string;
      saved: string;
      uploads: readonly string[];
    }
  >();
  #nextTab = 0;

  constructor(connection: ProviderConnection) {
    this.connection = connection;
    this.#newTab("about:blank");
  }
  #newTab(url: string): number {
    const id = ++this.#nextTab;
    this.#tabs.set(id, {
      url,
      title: "Fixture",
      revision: 0,
      clicks: 0,
      text: "",
      saved: "",
      uploads: [],
    });
    return id;
  }
  observe(
    tabId = 1,
  ): Readonly<{
    url: string;
    title: string;
    revision: number;
    clicks: number;
    text: string;
    saved: string;
    uploads: readonly string[];
  }> {
    const tab = this.#tabs.get(tabId);
    if (!tab) throw new Error("unknown_fixture_tab");
    return Object.freeze({ ...tab, uploads: Object.freeze([...tab.uploads]) });
  }
  execute(command: DispatchCommand): void {
    if (command.connection !== this.connection || this.#replies.has(command))
      throw new Error("fixture_dispatch_mismatch");
    this.received.push(command);
    const params: Parameters =
      "params" in command
        ? command.params
        : command.operation === "browser.click"
          ? { reference: command.target }
          : command.operation === "browser.snapshot"
            ? { tabId: command.tabId }
            : {};
    try {
      this.#replies.set(command, {
        ok: true,
        data: this.#perform(command.operation, params),
      });
    } catch {
      this.#replies.set(command, { ok: false, delivery: "refused" });
    }
  }
  #perform(operation: string, params: Parameters): unknown {
    if (operation === "browser.tabs")
      return {
        tabs: [...this.#tabs].map(([tabId, tab]) => ({
          tabId,
          title: tab.title,
          url: tab.url,
        })),
      };
    if (operation === "browser.navigate" && params.newTab === true) {
      const tabId = this.#newTab(String(params.url));
      const tab = this.#tabs.get(tabId)!;
      return { tab: { tabId, title: tab.title, url: tab.url } };
    }
    const ref =
      typeof params.reference === "string"
        ? /^(\d+):(\d+):(button|input)$/.exec(params.reference)
        : null;
    const tabId = ref ? Number(ref[1]) : Number(params.tabId ?? 1);
    const tab = this.#tabs.get(tabId);
    if (!tab || (ref && Number(ref[2]) !== tab.revision))
      throw new Error("stale_fixture_reference");
    switch (operation) {
      case "browser.snapshot":
        tab.revision++;
        return {
          tab: { tabId },
          elements: [
            {
              reference: `${tabId}:${tab.revision}:button`,
              role: "button",
              name: "Increment",
            },
            {
              reference: `${tabId}:${tab.revision}:input`,
              role: "textbox",
              name: "Message",
            },
          ],
        };
      case "browser.navigate":
        tab.url = String(params.url);
        tab.revision++;
        return { tabId };
      case "browser.click":
        if (ref?.[3] !== "button") throw new Error("bad_fixture_reference");
        tab.clicks++;
        return { tabId };
      case "browser.type":
        if (ref?.[3] !== "input") throw new Error("bad_fixture_reference");
        tab.text = String(params.text);
        return { tabId };
      case "browser.key":
        if (params.key === "Enter") tab.saved = tab.text;
        return { tabId };
      case "browser.upload":
        if (!Array.isArray(params.files)) throw new Error("bad_fixture_upload");
        tab.uploads = params.files.map(String);
        return { tabId, files: tab.uploads.length };
      case "browser.wait":
        return { tabId, ready: true };
      case "browser.capture":
        return {
          tabId,
          fixturePixels: [
            tab.clicks & 255,
            tab.text.length & 255,
            tab.uploads.length & 255,
          ],
        };
      case "browser.release":
        tab.revision++;
        return { tabId, released: true };
      case "browser.dialog":
        return { tabId, dialog: null };
      case "browser.eval":
        return { tabId, value: tab.clicks };
      case "browser.cdp":
        return { tabId, result: { value: tab.clicks } };
      default:
        throw new Error("unsupported_fixture_operation");
    }
  }
  cancel(_command: DispatchCommand): void {
    /* Effects are independent of cancellation. */
  }
  reply(command: DispatchCommand): ProviderReply {
    const reply = this.#replies.get(command);
    if (!reply) throw new Error("missing_fixture_reply");
    this.#replies.delete(command);
    return reply;
  }
}
