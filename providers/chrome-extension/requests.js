// Bounded ordinary work. A reply deadline fences continuations, but cannot
// cancel a Chrome command already dispatched. Keep its capacity occupied until
// it settles, and keep recovery independent of these slots.
export class RequestQueue {
  constructor({ timeoutMs = 30000, capacity = 64, parallel = 8, abandoned = () => {} } = {}) {
    Object.assign(this, { timeoutMs, capacity, parallel, abandoned });
    this.requests = new Map();
    this.active = 0;
    this.lanes = new Map();
  }

  submit(id, { check, prepare, run, timeoutMs = this.timeoutMs }) {
    if (this.requests.has(id) || this.requests.size >= this.capacity)
      return Promise.reject(Object.assign(new Error("Browser request capacity exceeded"), { code:"browser_busy", delivery:"refused" }));
    return new Promise((resolve, reject) => {
      const context = { id, dispatched:false, tabId:null, active:false, settled:false, ready:false,
        deadline:Date.now() + timeoutMs,
        check:() => {
          if (!context.error && Date.now() >= context.deadline) context.abort("browser_timeout");
          if (context.error) throw context.error;
          check();
        },
        dispatch:() => { context.check(); context.dispatched = true; },
      };
      context.release = () => {
        if (context.released) return;
        context.released = true;
        if (this.requests.get(id) === context) this.requests.delete(id);
        if (context.active) {
          this.active--;
          if (this.lanes.get(context.key) === context) this.lanes.delete(context.key);
        }
        this.pump();
      };
      const finish = (error, value) => {
        if (context.settled) return;
        context.settled = true;
        clearTimeout(context.timer);
        if (error) {
          error.delivery = context.dispatched ? "unknown" : "refused";
          reject(error);
        } else resolve(value);
      };
      context.abort = (code = "browser_cancelled") => {
        if (context.settled) return;
        context.error = Object.assign(new Error(code === "browser_timeout"
          ? "Browser request expired; dispatched effects may be unknown" : "Browser request ended"), { code });
        if (context.active && context.dispatched) this.abandoned(context, code);
        finish(context.error);
        if (!context.active) context.release();
      };
      context.timer = setTimeout(() => context.abort("browser_timeout"), timeoutMs);
      context.run = async () => {
        context.active = true; this.active++; this.lanes.set(context.key, context);
        try { context.check(); const value = await run(context); context.check(); finish(null, value); }
        catch (error) { finish(error); }
        finally {
          clearTimeout(context.timer);
          context.release();
        }
      };
      this.requests.set(id, context);
      Promise.resolve().then(() => { context.check(); return prepare(context); }).then((key) => {
        context.check(); context.key = key; context.ready = true; this.pump();
      }).catch((error) => { finish(error); context.release(); });
    });
  }

  pump() {
    for (const context of this.requests.values()) {
      if (this.active >= this.parallel) break;
      if (context.ready && !context.active && !context.settled && !this.lanes.has(context.key)) context.run();
    }
  }

  cancel(id, code) { this.requests.get(id)?.abort(code); }
  cancelAll(code = "approval_required") { for (const context of this.requests.values()) context.abort(code); }
  cancelTab(tabId, code = "browser_cancelled") {
    for (const context of this.requests.values()) if (context.tabId === tabId) context.abort(code);
  }
  detached(tabId) {
    for (const context of [...this.requests.values()]) if (context.tabId === tabId) {
      context.abort("browser_detached");
      // Confirmed debugger detachment ends the dispatch route even if Chrome
      // never settles an old callback. Its continuations remain fenced.
      context.release();
    }
  }
}

export function bounded(work, milliseconds = 2000) {
  let timer;
  return Promise.race([Promise.resolve().then(work), new Promise((_, reject) => {
    timer = setTimeout(() => reject(Object.assign(new Error("Browser cleanup timed out"), { code:"browser_cleanup_timeout" })), milliseconds);
  })]).finally(() => clearTimeout(timer));
}
