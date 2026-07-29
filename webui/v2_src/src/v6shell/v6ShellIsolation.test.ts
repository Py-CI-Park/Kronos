import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('V6 shell uses isolated navigation and main class names', async () => {
  const source = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');
  const context = await readFile(new URL('./ResearchContext.svelte', import.meta.url), 'utf8');

  assert.match(source, /class="v6-sidebar"/u);
  assert.match(source, /class="v6-main"/u);
  assert.doesNotMatch(source, /class="sidebar"/u);
  assert.match(source, /ResearchContext/u);
  assert.match(source, /<ResearchContext \/>/u);
  assert.match(context, /<strong>D5<\/strong>/u);
  assert.match(context, /10 \/ 10 UNITS/u);
  assert.match(context, /NOT_CONFIRMED/u);
  assert.match(context, /NOT_RUN_NO_READ/u);
});
