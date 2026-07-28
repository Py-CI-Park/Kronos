import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { ErrorObject } from 'ajv';

import {
  sanitizeV5SchemaDiagnostics,
  V5SchemaValidationError,
  type V5SchemaDiagnostic,
} from './v5SchemaValidationError';

const asAjvErrors = (errors: readonly unknown[]): readonly ErrorObject[] => errors as readonly ErrorObject[];

function assertFrozenDiagnostics(diagnostics: readonly V5SchemaDiagnostic[]): void {
  assert.ok(Object.isFrozen(diagnostics));
  for (const diagnostic of diagnostics) {
    assert.ok(Object.isFrozen(diagnostic));
    assert.deepEqual(Object.keys(diagnostic).sort(), ['instancePath', 'keyword']);
  }
}

test('sanitizeV5SchemaDiagnostics retains only bounded sanitized instancePath and keyword pairs', () => {
  const longPointer = `/${'😀'.repeat(300)}`;
  const truncatedLongPointer = [...longPointer].slice(0, 256).join('');
  const diagnostics = sanitizeV5SchemaDiagnostics(asAjvErrors([
    { instancePath: '/z', keyword: 'type', params: { token: 'secret-token' }, message: 'server detail' },
    { instancePath: '/z', keyword: 'type', schemaPath: '#/secret' },
    { instancePath: '/a\u0000b\u007fc', keyword: 'required' },
    { instancePath: 'not-a-pointer', keyword: 'minLength' },
    { instancePath: '/bad~2token', keyword: 'bad keyword!' },
    { instancePath: 7, keyword: null },
    { instancePath: '/tilde~0slash~1literal', keyword: 'pattern' },
    { instancePath: longPointer, keyword: 'emoji' },
  ]));

  assert.deepEqual(diagnostics, [
    { instancePath: '', keyword: 'minLength' },
    { instancePath: '', keyword: 'unknown' },
    { instancePath: '/abc', keyword: 'required' },
    { instancePath: '/tilde~0slash~1literal', keyword: 'pattern' },
    { instancePath: '/z', keyword: 'type' },
    { instancePath: truncatedLongPointer, keyword: 'emoji' },
  ]);
  assert.equal([...(diagnostics.at(-1)?.instancePath ?? '')].length, 256);
  assert.ok(!JSON.stringify(diagnostics).includes('secret-token'));
  assert.ok(!JSON.stringify(diagnostics).includes('schemaPath'));
  assertFrozenDiagnostics(diagnostics);
});

test('sanitizeV5SchemaDiagnostics falls back, deduplicates, sorts, and caps diagnostics', () => {
  assert.deepEqual(sanitizeV5SchemaDiagnostics(null), [{ instancePath: '', keyword: 'unknown' }]);
  assert.deepEqual(sanitizeV5SchemaDiagnostics(undefined), [{ instancePath: '', keyword: 'unknown' }]);
  assert.deepEqual(sanitizeV5SchemaDiagnostics([]), [{ instancePath: '', keyword: 'unknown' }]);

  const diagnostics = sanitizeV5SchemaDiagnostics(asAjvErrors(
    Array.from({ length: 20 }, (_, index) => ({
      instancePath: `/${String(19 - index).padStart(2, '0')}`,
      keyword: 'type',
    }))
  ));

  assert.equal(diagnostics.length, 16);
  assert.equal(diagnostics[0].instancePath, '/00');
  assert.equal(diagnostics[15].instancePath, '/15');
  assertFrozenDiagnostics(diagnostics);
});

test('V5SchemaValidationError exposes exact immutable public contract without retaining raw data', () => {
  const input = [
    { instancePath: '/b', keyword: 'type', params: { token: 'secret-token' } },
    { instancePath: 'invalid', keyword: 'bad keyword', message: 'server-only diagnostic' },
  ] as unknown as V5SchemaDiagnostic[];
  const error = new V5SchemaValidationError('RUNS', input);

  input[0] = { instancePath: '/mutated', keyword: 'required' };

  assert.ok(error instanceof Error);
  assert.ok(error instanceof V5SchemaValidationError);
  assert.equal(Object.getPrototypeOf(error), V5SchemaValidationError.prototype);
  assert.equal(error.name, 'V5SchemaValidationError');
  assert.equal(error.message, 'V5 response failed schema validation');
  assert.equal(error.code, 'V5_SCHEMA_INVALID');
  assert.equal(error.routeId, 'RUNS');
  assert.deepEqual(error.diagnostics, [
    { instancePath: '', keyword: 'unknown' },
    { instancePath: '/b', keyword: 'type' },
  ]);
  assert.ok(!('cause' in error));
  assert.ok(!JSON.stringify(error).includes('secret-token'));
  assert.ok(!JSON.stringify(error).includes('server-only diagnostic'));
  assert.ok(Object.isFrozen(error));
  assertFrozenDiagnostics(error.diagnostics);
});
