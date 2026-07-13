// G009 Todo 9 — request-race guard. A component that fires an async request in
// response to a user/state change (e.g. selecting a different run) can receive
// a stale response after a newer request has already superseded it. This
// helper hands out monotonically increasing generation tokens so a caller can
// discard any response whose token is no longer the current one.
//
// Usage:
//   const gate = createRequestGate();
//   async function load(name: string) {
//     const token = gate.next();
//     const result = await fetchSomething(name);
//     if (!gate.isCurrent(token)) return; // a newer load() call superseded us
//     applyResult(result);
//   }

export interface RequestGate {
  /** Advance to a new generation and return its token. Call once per request. */
  next(): number;
  /** The token of the most recently started request. */
  current(): number;
  /** True when `token` is still the newest generation (i.e. not superseded). */
  isCurrent(token: number): boolean;
}

export function createRequestGate(): RequestGate {
  let gen = 0;
  return {
    next(): number {
      return ++gen;
    },
    current(): number {
      return gen;
    },
    isCurrent(token: number): boolean {
      return token === gen;
    },
  };
}

// Cancel a superseded in-flight request (if any) and return a fresh
// AbortController for the new one. Callers that don't need real network
// cancellation can still use this to keep a single "current controller"
// reference around for bookkeeping.
export function makeAbortable(prev?: AbortController): AbortController {
  prev?.abort();
  return new AbortController();
}
