import test from "node:test";
import assert from "node:assert/strict";
import { presentationParams } from "../../providers/chrome-extension/presentation.js";
import { BrowserCdp } from "../../providers/chrome-extension/browser_cdp.js";

test("presentation defaults stay in the background and require a boolean opt-in", () => {
  assert.deepEqual(presentationParams("Target.createTarget", {url:"about:blank"}), {url:"about:blank", background:true});
  for (const [method, params] of [["Page.bringToFront", {}], ["Target.activateTarget", {targetId:"page"}],
    ["Target.createTarget", {background:false}], ["Target.createTarget", {newWindow:true}]]) {
    assert.throws(() => presentationParams(method, params), {code:"foreground_required"});
    assert.doesNotThrow(() => presentationParams(method, params, true));
  }
  assert.throws(() => presentationParams("Runtime.enable", []), {cdpCode:-32602});
});

test("withdrawn foreground opt-in fences queued activation and resets on reconnect", async () => {
  const event = {addListener() {}};
  const frames = [], updates = [], native = [];
  const chrome = {
    tabs: {onCreated:event, onUpdated:event, onRemoved:event,
      async query() { return [{id:1, url:"https://fixture.invalid/"}]; },
      async update(...args) { updates.push(args); }},
    debugger: {onEvent:event, onDetach:event,
      async getTargets() { return [{id:"page", tabId:1, type:"page"}]; },
      async sendCommand(...args) { native.push(args); return {}; }},
  };
  const cdp = new BrowserCdp({chrome, ensureAttached:async()=>{}, releaseTab:async()=>{},
    trackNewTab:async()=>{}, authority:()=>"fixture", post:frame=>frames.push(frame)});
  let cmdId = 0;
  const call = async (method, params={}, id="root") => {
    const n = ++cmdId;
    await cdp.command({id, cmdId:n, method, params});
    return frames.find(frame=>frame.cmdId===n);
  };
  await cdp.open("root",0);
  await call("MachineControl.setForegroundAllowed", {allowed:true});
  let unblock;
  const held = cdp.enqueue(()=>new Promise(resolve=>{unblock=resolve;}));
  await new Promise(resolve=>setImmediate(resolve));
  const activation = call("Target.activateTarget", {targetId:"page"});
  await call("MachineControl.setForegroundAllowed", {allowed:false});
  unblock(); await held;
  assert.match((await activation).error.message, /explicit opt-in/);
  assert.equal(updates.length,0);
  await call("MachineControl.setForegroundAllowed", {allowed:true});
  await cdp.closeAll("finished");
  await cdp.open("root",1);
  assert.match((await call("Page.bringToFront")).error.message, /explicit opt-in/);
  assert.equal(native.length,0);
  await cdp.closeAll("finished");
});

test("streamed input uses virtual page focus and fences late preparation", async () => {
  const event = {addListener() {}};
  const commands = [], frames = [];
  let releaseFocus, holdFocus = false;
  const chrome = {
    tabs: {onCreated:event, onUpdated:event, onRemoved:event},
    debugger: {onEvent:event, onDetach:event,
      async sendCommand(target, method, params) {
        commands.push({target, method, params});
        if (method === "Emulation.setFocusEmulationEnabled" && holdFocus)
          await new Promise(resolve=>{releaseFocus=resolve;});
        return {};
      }},
  };
  const cdp = new BrowserCdp({chrome, ensureAttached:async()=>{}, releaseTab:async()=>{},
    trackNewTab:async()=>{}, authority:()=>"fixture", post:frame=>frames.push(frame)});
  await cdp.open("page",1);
  await cdp.command({id:"page", cmdId:1, method:"Input.insertText", params:{text:"background"}});
  assert.deepEqual(commands.map(command=>command.method), ["Emulation.setFocusEmulationEnabled", "Input.insertText"]);
  assert.deepEqual(commands[0].params, {enabled:true});
  holdFocus = true;
  const pending = cdp.command({id:"page", cmdId:2, method:"Input.insertText", params:{text:"stale"}});
  await new Promise(resolve=>setImmediate(resolve));
  await cdp.closeAll("ended");
  await cdp.open("page",1);
  releaseFocus(); await pending;
  assert.equal(commands.some(command=>command.params?.text === "stale"), false);
  await cdp.closeAll("finished");
});
