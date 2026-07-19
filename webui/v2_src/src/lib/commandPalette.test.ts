import assert from 'node:assert/strict';
import test from 'node:test';

import type * as CommandPaletteModule from './commandPalette';
import type * as RoutesModule from './routes';

const commandPalettePath = ['.', 'commandPalette.ts'].join('/');
const routesPath = ['.', 'routes.ts'].join('/');
const {
  activateCommand,
  buildCommandPalette,
  filterCommands,
  firstEnabledIndex,
  moveEnabledIndex,
  shouldClosePaletteAfterActivation,
} = (await import(commandPalettePath)) as typeof CommandPaletteModule;
const { DASHBOARD_ROUTES } = (await import(routesPath)) as typeof RoutesModule;

type PaletteCommand = CommandPaletteModule.PaletteCommand;

const PALETTE_COMMANDS = buildCommandPalette(DASHBOARD_ROUTES);
const EXPECTED_ROUTE_COUNT = 12;


const DANGEROUS_VERBS = [
  'train',
  'execute',
  'order',
  'broker',
  'account',
  'paper trade',
  'promote',
  'model build',
  'publish GO',
  'delete artifact',
  'mutate DB',
  'run job',
  'push',
  'merge',
  'tag',
];

test('command inventory represents every canonical dashboard route exactly once', () => {
  const navigationCommands = PALETTE_COMMANDS.filter((command) => command.action.type === 'navigateToTab');
  const canonicalRouteIds = DASHBOARD_ROUTES.map((route) => route.id).sort();
  assert.equal(DASHBOARD_ROUTES.length, EXPECTED_ROUTE_COUNT);
  assert.equal(navigationCommands.length, DASHBOARD_ROUTES.length);
  assert.deepEqual(
    navigationCommands.map((command) => command.action.type === 'navigateToTab' ? command.action.tabId : null).sort(),
    canonicalRouteIds,
  );
});

test('filtering searches titles, route aliases, and keywords without mutating inventory', () => {
  assert.deepEqual(filterCommands('', PALETTE_COMMANDS).map((command) => command.id), PALETTE_COMMANDS.map((command) => command.id));
  assert.deepEqual(filterCommands('rl trading', PALETTE_COMMANDS).map((command) => command.id), ['navigate-rl', 'filter-rl']);
  assert.deepEqual(filterCommands('daily-ohlcv-panel', PALETTE_COMMANDS).map((command) => command.id), ['navigate-daily-ohlcv']);
  assert.deepEqual(filterCommands('readiness', PALETTE_COMMANDS).map((command) => command.id), ['filter-readiness']);
});

test('dangerous verbs are present only as disabled blocked commands with reasons', () => {
  for (const verb of DANGEROUS_VERBS) {
    const matches = PALETTE_COMMANDS.filter((command) => command.title.toLowerCase() === `blocked: ${verb.toLowerCase()}`);
    assert.ok(matches.length >= 1, `${verb} should be represented`);
    assert.ok(matches.every((command) => command.kind === 'blocked'), `${verb} should not appear in enabled commands`);
    assert.ok(matches.every((command) => command.action.type === 'blocked'), `${verb} should have blocked action metadata`);
    assert.ok(matches.every((command) => typeof command.disabledReason === 'string' && command.disabledReason.length > 0));
  }
});

test('builder preserves local route aliases for edge-case filtering', () => {
  const edgeCommands = buildCommandPalette([
    { id: 'edge', label: 'Edge Route', path: '/', aliases: ['/edge-alias'], queryTabs: ['edge-tab'] },
  ]);
  assert.deepEqual(filterCommands('/edge-alias', edgeCommands).map((command) => command.id), ['navigate-edge']);
  assert.deepEqual(filterCommands('edge-tab', edgeCommands).map((command) => command.id), ['navigate-edge']);
});

test('enabled index movement skips disabled commands and wraps', () => {
  const commands: PaletteCommand[] = [
    PALETTE_COMMANDS.find((command) => command.id === 'blocked-train')!,
    PALETTE_COMMANDS.find((command) => command.id === 'navigate-rl')!,
    PALETTE_COMMANDS.find((command) => command.id === 'blocked-order')!,
    PALETTE_COMMANDS.find((command) => command.id === 'shell-v4')!,
  ];

  assert.equal(firstEnabledIndex(commands), 1);
  assert.equal(moveEnabledIndex(commands, 1, 1), 3);
  assert.equal(moveEnabledIndex(commands, 3, 1), 1);
  assert.equal(moveEnabledIndex(commands, 1, -1), 3);
  assert.equal(moveEnabledIndex([commands[0], commands[2]], 0, 1), -1);
});

test('activation exposes only local read-only actions and blocked enter returns the reason', () => {
  const events: string[] = [];
  const handlers = {
    navigateToTab: (tabId: string) => events.push(`navigate:${tabId}`),
    inspect: (selector: string) => events.push(`inspect:${selector}`),
    filter: (value: string) => events.push(`filter:${value}`),
    setDashboardShell: (shell: 'v3' | 'v4') => events.push(`shell:${shell}`),
  };

  assert.deepEqual(activateCommand(PALETTE_COMMANDS.find((command) => command.id === 'navigate-docs')!, handlers), { status: 'activated' });
  assert.deepEqual(activateCommand(PALETTE_COMMANDS.find((command) => command.id === 'inspect-current-tab')!, handlers), { status: 'activated' });
  assert.deepEqual(activateCommand(PALETTE_COMMANDS.find((command) => command.id === 'filter-rl')!, handlers), { status: 'activated' });
  assert.deepEqual(activateCommand(PALETTE_COMMANDS.find((command) => command.id === 'shell-v4')!, handlers), { status: 'activated' });
  assert.deepEqual(events, ['navigate:docs', 'inspect:[data-v3-tab-host], main, [data-kronos-shell]', 'filter:rl', 'shell:v4']);

  const blocked = activateCommand(PALETTE_COMMANDS.find((command) => command.id === 'blocked-execute')!, handlers);
  assert.equal(blocked.status, 'blocked');
  assert.match(blocked.reason ?? '', /blocked/i);
  assert.deepEqual(events, ['navigate:docs', 'inspect:[data-v3-tab-host], main, [data-kronos-shell]', 'filter:rl', 'shell:v4']);
});

test('activation close policy keeps local filters open and closes read-only actions', () => {
  const noopHandlers = {
    navigateToTab: () => undefined,
    inspect: () => undefined,
    filter: () => undefined,
    setDashboardShell: () => undefined,
  };

  const filterCommand = PALETTE_COMMANDS.find((command) => command.id === 'filter-rl')!;
  const navigationCommand = PALETTE_COMMANDS.find((command) => command.id === 'navigate-docs')!;
  const blockedCommand = PALETTE_COMMANDS.find((command) => command.id === 'blocked-execute')!;

  assert.equal(shouldClosePaletteAfterActivation(filterCommand, activateCommand(filterCommand, noopHandlers)), false);
  assert.equal(shouldClosePaletteAfterActivation(navigationCommand, activateCommand(navigationCommand, noopHandlers)), true);
  assert.equal(shouldClosePaletteAfterActivation(blockedCommand, activateCommand(blockedCommand, noopHandlers)), false);
});

test('commands do not carry backend, network, or mutation metadata', () => {
  const forbiddenKeys = ['url', 'endpoint', 'href', 'method', 'httpMethod', 'body', 'payload', 'fetch', 'post', 'put', 'patch', 'delete', 'mutation'];
  for (const command of PALETTE_COMMANDS) {
    for (const key of forbiddenKeys) {
      assert.equal(Object.hasOwn(command, key), false, `${command.id} must not expose ${key}`);
      assert.equal(Object.hasOwn(command.action, key), false, `${command.id} action must not expose ${key}`);
    }
  }
});
