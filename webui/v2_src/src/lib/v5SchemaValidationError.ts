import type { ErrorObject } from 'ajv';
import type { V5RouteId } from './generated/kronosRlApiV2';

export interface V5SchemaDiagnostic {
  readonly instancePath: string;
  readonly keyword: string;
}

const MAX_DIAGNOSTICS = 16;
const MAX_DIAGNOSTIC_CODE_POINTS = 256;
const ASCII_CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/gu;
const JSON_POINTER = /^(?:\/(?:[^~/\x00-\x1f\x7f]|~[01])*)*$/u;
const KEYWORD = /^[A-Za-z0-9_-]{1,64}$/u;
const UNKNOWN_KEYWORD = 'unknown';

function truncateCodePoints(value: string): string {
  let truncated = '';
  let length = 0;
  for (const codePoint of value) {
    if (length >= MAX_DIAGNOSTIC_CODE_POINTS) break;
    truncated += codePoint;
    length += 1;
  }
  return truncated;
}

function compareCodePointStrings(left: string, right: string): number {
  const leftCodePoints = [...left];
  const rightCodePoints = [...right];
  const length = Math.min(leftCodePoints.length, rightCodePoints.length);

  for (let index = 0; index < length; index += 1) {
    const leftCodePoint = leftCodePoints[index].codePointAt(0) ?? 0;
    const rightCodePoint = rightCodePoints[index].codePointAt(0) ?? 0;
    if (leftCodePoint !== rightCodePoint) return leftCodePoint - rightCodePoint;
  }

  return leftCodePoints.length - rightCodePoints.length;
}

function compareDiagnostics(left: V5SchemaDiagnostic, right: V5SchemaDiagnostic): number {
  const pathOrder = compareCodePointStrings(left.instancePath, right.instancePath);
  return pathOrder !== 0 ? pathOrder : compareCodePointStrings(left.keyword, right.keyword);
}

function sanitizeInstancePath(value: unknown): string {
  if (typeof value !== 'string') return '';

  const sanitized = truncateCodePoints(value.replace(ASCII_CONTROL_CHARACTERS, ''));
  return JSON_POINTER.test(sanitized) ? sanitized : '';
}

function sanitizeKeyword(value: unknown): string {
  return typeof value === 'string' && KEYWORD.test(value) ? value : UNKNOWN_KEYWORD;
}

type V5SchemaDiagnosticInput = Readonly<{
  readonly instancePath?: unknown;
  readonly keyword?: unknown;
}>;

function freezeDiagnostics(diagnostics: readonly V5SchemaDiagnostic[]): readonly V5SchemaDiagnostic[] {
  return Object.freeze(diagnostics.map((diagnostic) => Object.freeze({ ...diagnostic })));
}

function sanitizeDiagnosticPairs(values: readonly V5SchemaDiagnosticInput[] | null | undefined): readonly V5SchemaDiagnostic[] {
  const diagnostics = new Map<string, V5SchemaDiagnostic>();

  for (const value of values ?? []) {
    const diagnostic = {
      instancePath: sanitizeInstancePath(value?.instancePath),
      keyword: sanitizeKeyword(value?.keyword),
    };
    const key = `${diagnostic.instancePath}\u0000${diagnostic.keyword}`;
    if (!diagnostics.has(key)) diagnostics.set(key, diagnostic);
  }

  const sortedDiagnostics = diagnostics.size === 0
    ? [{ instancePath: '', keyword: UNKNOWN_KEYWORD }]
    : [...diagnostics.values()].sort(compareDiagnostics).slice(0, MAX_DIAGNOSTICS);

  return freezeDiagnostics(sortedDiagnostics);
}

export function sanitizeV5SchemaDiagnostics(errors: readonly ErrorObject[] | null | undefined): readonly V5SchemaDiagnostic[] {
  return sanitizeDiagnosticPairs(errors);
}

export class V5SchemaValidationError extends Error {
  readonly name: 'V5SchemaValidationError';
  readonly code: 'V5_SCHEMA_INVALID';
  readonly routeId: V5RouteId;
  readonly diagnostics: readonly V5SchemaDiagnostic[];

  constructor(routeId: V5RouteId, diagnostics: readonly V5SchemaDiagnostic[]) {
    super('V5 response failed schema validation');
    this.name = 'V5SchemaValidationError';
    this.code = 'V5_SCHEMA_INVALID';
    this.routeId = routeId;
    this.diagnostics = sanitizeDiagnosticPairs(diagnostics);
    Object.setPrototypeOf(this, new.target.prototype);
    Object.freeze(this);
  }
}
