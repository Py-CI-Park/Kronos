const LABEL_ALIASES: Readonly<Record<string, string>> = {
  NO_TRADE: 'NO TRADE',
  ALWAYS_INVEST: 'ALWAYS',
  COST_AWARE_MOMENTUM_RULE: 'MOMENTUM',
  CQL_REWARD_SHUFFLED: 'CQL-RS',
  CQL_ACTION_SHUFFLED: 'CQL-AS',
};

export function compactOutcomeLabel(label: string): string {
  const seedMatch = /\/seed-(\d+)$/u.exec(label);
  const base = seedMatch ? label.slice(0, seedMatch.index) : label;
  const readable = LABEL_ALIASES[base] ?? base.replaceAll('_', ' ');
  const compact = readable.length > 15 ? `${readable.slice(0, 14)}…` : readable;
  return seedMatch ? `${compact}/s${seedMatch[1]}` : compact;
}
