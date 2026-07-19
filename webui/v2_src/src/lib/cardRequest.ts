export interface CardRequestState {
  readonly loading: boolean;
  readonly error: string | null;
}

export interface CardRequestManager {
  load<T>(
    key: string,
    request: (signal: AbortSignal) => Promise<T | null>,
    apply: (payload: T) => void,
    publish: (key: string, state: CardRequestState) => void,
  ): Promise<void>;
  abort(key: string): void;
  abortAll(): void;
}

export function createCardRequestManager(timeoutMs: number): CardRequestManager {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new RangeError('timeoutMs must be a positive finite number');
  }

  const controllers = new Map<string, AbortController>();
  const generations = new Map<string, number>();

  function abort(key: string): void {
    controllers.get(key)?.abort();
    controllers.delete(key);
  }

  async function load<T>(
    key: string,
    request: (signal: AbortSignal) => Promise<T | null>,
    apply: (payload: T) => void,
    publish: (key: string, state: CardRequestState) => void,
  ): Promise<void> {
    abort(key);
    const generation = (generations.get(key) ?? 0) + 1;
    generations.set(key, generation);
    const controller = new AbortController();
    controllers.set(key, controller);
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    publish(key, { loading: true, error: null });

    try {
      const payload = await request(controller.signal);
      if (generations.get(key) !== generation) return;
      if (payload === null) {
        publish(key, {
          loading: false,
          error: timedOut ? `${key} request timed out` : `${key} request unavailable`,
        });
        return;
      }
      apply(payload);
      publish(key, { loading: false, error: null });
    } catch (error) {
      if (generations.get(key) !== generation) return;
      const aborted = controller.signal.aborted;
      publish(key, {
        loading: false,
        error: timedOut ? `${key} request timed out` : aborted ? `${key} request aborted` : `${key} request failed`,
      });
    } finally {
      clearTimeout(timer);
      if (generations.get(key) === generation) controllers.delete(key);
    }
  }

  function abortAll(): void {
    for (const key of [...controllers.keys()]) abort(key);
  }

  return { load, abort, abortAll };
}
