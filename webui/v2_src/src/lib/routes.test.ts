import assert from 'node:assert/strict';
import { test } from 'node:test';

import type * as Routes from './routes';

const routesPath = ['.', 'routes.ts'].join('/');
const {
  DASHBOARD_ROUTES,
  resolveRoute,
  routeUrl,
  syncTabFromLocation,
}: typeof Routes = await import(routesPath);

function locationLike(pathname: string, search = ''): Pick<Location, 'pathname' | 'search'> {
  return { pathname, search };
}

function withWindow(
  pathname: string,
  search: string,
  callback: (historyUrls: string[]) => void,
): void {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const historyUrls: string[] = [];

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      location: { pathname, search },
      history: {
        replaceState(_state: unknown, _title: string, url: string): void {
          historyUrls.push(url);
        },
      },
    },
  });

  try {
    callback(historyUrls);
  } finally {
    if (descriptor) {
      Object.defineProperty(globalThis, 'window', descriptor);
    } else {
      delete (globalThis as { window?: unknown }).window;
    }
  }
}

test('direct route aliases are executable route data', () => {
  assert.equal(resolveRoute(locationLike('/rl'))?.id, 'rl');
  assert.equal(resolveRoute(locationLike('/daily-ohlcv'))?.id, 'daily-ohlcv');
  assert.equal(resolveRoute(locationLike('/daily-rl-guide'))?.id, 'daily-rl-guide');
  assert.equal(resolveRoute(locationLike('/daily-ohlcv/rl-guide'))?.id, 'daily-rl-guide');

  for (const alias of ['/rl', '/daily-ohlcv', '/daily-rl-guide', '/daily-ohlcv/rl-guide']) {
    assert.ok(
      DASHBOARD_ROUTES.some((route) => route.path === alias || route.aliases?.includes(alias)),
      `${alias} must be represented in route data`,
    );
  }
});

test('query tabs take precedence over direct alias paths', () => {
  assert.equal(resolveRoute(locationLike('/daily-ohlcv', '?tab=rl'))?.id, 'rl');
  assert.equal(resolveRoute(locationLike('/rl', '?tab=daily-ohlcv'))?.id, 'daily-ohlcv');
  assert.equal(resolveRoute(locationLike('/daily-ohlcv/rl-guide', '?tab=mission'))?.id, 'mission-control');
});

test('resolveRoute is safe without a browser location', () => {
  assert.equal(resolveRoute(), null);
});

test('routeUrl preserves shell opt-in query while keeping canonical tab URLs', () => {
  assert.equal(routeUrl('rl', { currentSearch: '?ui=v4&ui_persist=1&tab=settings' }), '/?tab=rl&ui=v4&ui_persist=1');
  assert.equal(routeUrl('daily-ohlcv', { currentSearch: '?ui=v4' }), '/?tab=daily-ohlcv&ui=v4');
  assert.equal(routeUrl('mission-control', { currentSearch: '?ui=v4&ui_persist=1' }), '/?ui=v4&ui_persist=1');
});

test('valid /rl section canonicalization preserves the direct section route and shell query', () => {
  withWindow('/rl', '?section=evidence&ui=v4&ui_persist=1&extra=drop', (historyUrls) => {
    assert.equal(syncTabFromLocation({ replaceAlias: true }), 'rl');
    assert.deepEqual(historyUrls, ['/rl?section=evidence&ui=v4&ui_persist=1']);
  });
});

test('invalid /rl section canonicalization falls back to canonical query tab route', () => {
  withWindow('/rl', '?section=bogus&ui=v4&ui_persist=1', (historyUrls) => {
    assert.equal(syncTabFromLocation({ replaceAlias: true }), 'rl');
    assert.deepEqual(historyUrls, ['/?tab=rl&ui=v4&ui_persist=1']);
  });
});
