export const OPEN_PALETTE_EVENT = 'kronos:v4-command-palette-open';

export type CommandKind = 'navigation' | 'inspection' | 'filter' | 'shell' | 'blocked';
export type CommandAction =
  | { type: 'navigateToTab'; tabId: string }
  | { type: 'inspect'; selector: string }
  | { type: 'filter'; value: string }
  | { type: 'setDashboardShell'; shell: 'v3' | 'v4' }
  | { type: 'blocked' };

export interface PaletteRoute {
  id: string;
  label: string;
  path: string;
  aliases?: readonly string[];
  queryTabs?: readonly string[];
}

export interface PaletteCommand {
  id: string;
  title: string;
  description: string;
  kind: CommandKind;
  keywords: readonly string[];
  action: CommandAction;
  disabledReason?: string;
}

export interface PaletteHandlers {
  navigateToTab(tabId: string): void;
  inspect(selector: string): void;
  filter(value: string): void;
  setDashboardShell(shell: 'v3' | 'v4'): void;
}

export interface CommandActivationResult {
  status: 'activated' | 'blocked';
  reason?: string;
}

export function shouldClosePaletteAfterActivation(command: PaletteCommand, result: CommandActivationResult): boolean {
  return result.status === 'activated' && command.action.type !== 'filter';
}

const LOCAL_COMMANDS: readonly PaletteCommand[] = [
  {
    id: 'inspect-current-tab',
    title: 'Inspect current tab',
    description: 'Highlight the active dashboard tab host without calling the backend.',
    kind: 'inspection',
    keywords: ['local', 'inspect', 'current', 'tab', 'page'],
    action: { type: 'inspect', selector: '[data-v3-tab-host], main, [data-kronos-shell]' },
  },
  {
    id: 'filter-readiness',
    title: 'Filter for readiness evidence',
    description: 'Populate the palette filter with readiness-focused local commands.',
    kind: 'filter',
    keywords: ['local', 'filter', 'readiness', 'evidence'],
    action: { type: 'filter', value: 'readiness' },
  },
  {
    id: 'filter-rl',
    title: 'Filter for RL surfaces',
    description: 'Populate the palette filter with RL-focused local commands.',
    kind: 'filter',
    keywords: ['local', 'filter', 'rl', 'trading', 'research'],
    action: { type: 'filter', value: 'rl' },
  },
  {
    id: 'shell-v3',
    title: 'Switch shell to V3',
    description: 'Use the stable dashboard shell locally.',
    kind: 'shell',
    keywords: ['shell', 'v3', 'stable', 'default'],
    action: { type: 'setDashboardShell', shell: 'v3' },
  },
  {
    id: 'shell-v4',
    title: 'Switch shell to V4',
    description: 'Use the opt-in V4 dashboard shell locally.',
    kind: 'shell',
    keywords: ['shell', 'v4', 'preview', 'paper', 'ops', 'ledger'],
    action: { type: 'setDashboardShell', shell: 'v4' },
  },
];

const BLOCKED_VERBS: readonly [string, string][] = [
  ['train', 'Training is intentionally blocked from the read-only palette.'],
  ['execute', 'Execution is intentionally blocked from the read-only palette.'],
  ['order', 'Order placement is intentionally blocked from the read-only palette.'],
  ['broker', 'Broker actions are intentionally blocked from the read-only palette.'],
  ['account', 'Account actions are intentionally blocked from the read-only palette.'],
  ['paper trade', 'Paper trade actions are intentionally blocked from the read-only palette.'],
  ['promote', 'Promotion is intentionally blocked from the read-only palette.'],
  ['model build', 'Model build actions are intentionally blocked from the read-only palette.'],
  ['publish GO', 'Publishing GO decisions is intentionally blocked from the read-only palette.'],
  ['delete artifact', 'Artifact deletion is intentionally blocked from the read-only palette.'],
  ['mutate DB', 'Database mutation is intentionally blocked from the read-only palette.'],
  ['run job', 'Job execution is intentionally blocked from the read-only palette.'],
  ['push', 'Push actions are intentionally blocked from the read-only palette.'],
  ['merge', 'Merge actions are intentionally blocked from the read-only palette.'],
  ['tag', 'Tag actions are intentionally blocked from the read-only palette.'],
];

function routeKeywords(route: PaletteRoute): readonly string[] {
  return [route.id, route.label, route.path, ...(route.aliases ?? []), ...(route.queryTabs ?? [])];
}

function navigationCommand(route: PaletteRoute): PaletteCommand {
  return {
    id: `navigate-${route.id}`,
    title: `Open ${route.label}`,
    description: `Navigate to ${route.label} (${route.id}).`,
    kind: 'navigation',
    keywords: routeKeywords(route),
    action: { type: 'navigateToTab', tabId: route.id },
  };
}

function blockedCommand([verb, reason]: readonly [string, string]): PaletteCommand {
  return {
    id: `blocked-${verb.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
    title: `Blocked: ${verb}`,
    description: reason,
    kind: 'blocked',
    keywords: ['blocked', 'dangerous', verb],
    action: { type: 'blocked' },
    disabledReason: reason,
  };
}

export function buildCommandPalette(routes: readonly PaletteRoute[]): readonly PaletteCommand[] {
  return [
    ...routes.map(navigationCommand),
    ...LOCAL_COMMANDS,
    ...BLOCKED_VERBS.map(blockedCommand),
  ];
}

export function dispatchCommandPaletteOpen(target: Window | EventTarget | null): void {
  if (!target) return;
  const event = typeof CustomEvent === 'function' ? new CustomEvent(OPEN_PALETTE_EVENT) : new Event(OPEN_PALETTE_EVENT);
  target.dispatchEvent(event);
}

export function requestCommandPalette(): void {
  dispatchCommandPaletteOpen(typeof window === 'undefined' ? null : window);
}

export function filterCommands(query: string, commands: readonly PaletteCommand[]): PaletteCommand[] {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [...commands];
  return commands.filter((command) => {
    const haystack = [command.id, command.title, command.description, command.kind, ...command.keywords]
      .join(' ')
      .toLowerCase();
    return terms.every((term) => haystack.includes(term));
  });
}

export function firstEnabledIndex(commands: readonly PaletteCommand[]): number {
  return commands.findIndex((command) => !command.disabledReason);
}

export function moveEnabledIndex(commands: readonly PaletteCommand[], currentIndex: number, direction: 1 | -1): number {
  if (commands.length === 0) return -1;
  let next = currentIndex;
  for (let steps = 0; steps < commands.length; steps += 1) {
    next = (next + direction + commands.length) % commands.length;
    if (!commands[next]?.disabledReason) return next;
  }
  return -1;
}

export function activateCommand(command: PaletteCommand, handlers: PaletteHandlers): CommandActivationResult {
  if (command.disabledReason) return { status: 'blocked', reason: command.disabledReason };
  switch (command.action.type) {
    case 'navigateToTab':
      handlers.navigateToTab(command.action.tabId);
      break;
    case 'inspect':
      handlers.inspect(command.action.selector);
      break;
    case 'filter':
      handlers.filter(command.action.value);
      break;
    case 'setDashboardShell':
      handlers.setDashboardShell(command.action.shell);
      break;
    case 'blocked':
      return { status: 'blocked', reason: command.disabledReason ?? 'This command is blocked.' };
  }
  return { status: 'activated' };
}
