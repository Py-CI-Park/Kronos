import assert from 'node:assert/strict';
import test from 'node:test';
import { PROGRAM_EXECUTION } from './programExecution';

test('execution banner preserves the research boundary and delivery lineage', () => {
  assert.equal(PROGRAM_EXECUTION.overallScore, 74);
  assert.equal(PROGRAM_EXECUTION.pageCount, 12);
  assert.equal(PROGRAM_EXECUTION.freshOos, 'NOT_RUN_NO_READ');
  assert.equal(PROGRAM_EXECUTION.liveTrading, 'BLOCKED');
  assert.match(PROGRAM_EXECUTION.branch, /^codex\//);
  assert.equal(PROGRAM_EXECUTION.stage, 'PRIMARY_COMPLETE_NO_GO');
  assert.match(PROGRAM_EXECUTION.nextAction, /preregister/i);
});
