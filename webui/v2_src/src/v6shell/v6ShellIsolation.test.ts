import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

test('V6 shell uses isolated navigation and main class names', async () => {
  const source = await readFile(new URL('./V6Shell.svelte', import.meta.url), 'utf8');

  assert.match(source, /class="v6-sidebar"/u);
  assert.match(source, /class="v6-main"/u);
  assert.doesNotMatch(source, /class="sidebar"/u);
});
