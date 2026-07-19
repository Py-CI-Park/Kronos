import canonicalize from 'canonicalize';

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;

export type JcsProfileErrorCode =
  | 'malformed_json'
  | 'utf8_bom'
  | 'duplicate_member'
  | 'non_finite_number'
  | 'unsafe_integer'
  | 'invalid_unicode'
  | 'unsupported_value'
  | 'non_json_object'
  | 'cyclic_value';

export class JcsProfileError extends Error {
  readonly code: JcsProfileErrorCode;

  constructor(code: JcsProfileErrorCode, message: string) {
    super(message);
    this.name = 'JcsProfileError';
    this.code = code;
  }
}

function fail(code: JcsProfileErrorCode, message: string): never {
  throw new JcsProfileError(code, message);
}

function assertScalarUnicode(value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const codeUnit = value.charCodeAt(index);
    if (codeUnit < 0xd800 || codeUnit > 0xdfff) {
      continue;
    }

    if (
      codeUnit >= 0xdc00 ||
      index + 1 === value.length ||
      value.charCodeAt(index + 1) < 0xdc00 ||
      value.charCodeAt(index + 1) > 0xdfff
    ) {
      fail('invalid_unicode', 'JCS input contains an unpaired Unicode surrogate');
    }

    index += 1;
  }
}

function assertIJson(
  value: unknown,
  ancestors: Set<object>,
  rejectUnsafeIntegers: boolean
): void {
  if (value === null || typeof value === 'boolean') {
    return;
  }

  if (typeof value === 'string') {
    assertScalarUnicode(value);
    return;
  }

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      fail('non_finite_number', 'JCS input contains a non-finite number');
    }
    if (rejectUnsafeIntegers && Number.isInteger(value) && !Number.isSafeInteger(value)) {
      fail('unsafe_integer', 'JCS input contains an integer outside the I-JSON safe range');
    }
    return;
  }

  if (typeof value !== 'object') {
    fail('unsupported_value', 'JCS input contains a non-JSON value');
  }

  if (ancestors.has(value)) {
    fail('cyclic_value', 'JCS input contains a cycle');
  }

  ancestors.add(value);
  try {
    if (Array.isArray(value)) {
      const keys = Reflect.ownKeys(value);
      for (const key of keys) {
        if (key === 'length') {
          continue;
        }
        if (typeof key !== 'string' || !/^(0|[1-9]\d*)$/.test(key) || Number(key) >= value.length) {
          fail('non_json_object', 'JCS input contains an array property outside its JSON elements');
        }
      }
      for (let index = 0; index < value.length; index += 1) {
        const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
        if (descriptor === undefined) {
          fail('unsupported_value', 'JCS input contains a sparse array');
        }
        if (!descriptor.enumerable || !('value' in descriptor)) {
          fail('non_json_object', 'JCS input contains an accessor or non-enumerable array property');
        }
        assertIJson(descriptor.value, ancestors, rejectUnsafeIntegers);
      }
      return;
    }

    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      fail('non_json_object', 'JCS input contains a non-JSON object');
    }

    for (const key of Reflect.ownKeys(value)) {
      if (typeof key !== 'string' || !Object.prototype.propertyIsEnumerable.call(value, key)) {
        fail('non_json_object', 'JCS input contains a non-JSON object property');
      }
      assertScalarUnicode(key);
      const descriptor = Object.getOwnPropertyDescriptor(value, key);
      if (descriptor === undefined || !('value' in descriptor)) {
        fail('non_json_object', 'JCS input contains an accessor property');
      }
      assertIJson(descriptor.value, ancestors, rejectUnsafeIntegers);
    }
  } finally {
    ancestors.delete(value);
  }
}

function canonicalizeParsedV5(value: unknown, rejectUnsafeIntegers: boolean): string {
  assertIJson(value, new Set<object>(), rejectUnsafeIntegers);
  const result = canonicalize(value);
  if (typeof result !== 'string') {
    fail('unsupported_value', 'JCS input could not be canonicalized');
  }
  return result;
}

/** Canonicalizes an already-parsed I-JSON value using the V5 RFC 8785 profile. */
export function canonicalizeV5(value: unknown): string {
  return canonicalizeParsedV5(value, true);
}

/** Returns the RFC 8785 canonical JSON encoded as strict UTF-8 bytes. */
export function canonicalizeV5Utf8(value: unknown): Uint8Array {
  return new TextEncoder().encode(canonicalizeV5(value));
}

/** Canonicalizes raw JSON while retaining number-token lexical evidence. */
export function canonicalizeV5Json(inputUtf8: string): string {
  return canonicalizeParsedV5(parseV5JsonInternal(inputUtf8), false);
}

/** Returns canonical raw JSON as strict UTF-8 bytes. */
export function canonicalizeV5JsonUtf8(input: Uint8Array): Uint8Array {
  if (input[0] === 0xef && input[1] === 0xbb && input[2] === 0xbf) {
    fail('utf8_bom', 'JCS input must not begin with a UTF-8 BOM');
  }
  let decoded: string;
  try {
    decoded = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(input);
  } catch {
    fail('malformed_json', 'JCS input is not valid UTF-8');
  }
  return new TextEncoder().encode(canonicalizeV5Json(decoded));
}
function isJsonWhitespace(value: string): boolean {
  return value === ' ' || value === '\t' || value === '\n' || value === '\r';
}

class StrictJsonParser {
  #index = 0;

  constructor(private readonly source: string) {}

  parse(): unknown {
    this.skipWhitespace();
    const value = this.parseValue();
    this.skipWhitespace();
    if (this.#index !== this.source.length) {
      fail('malformed_json', 'JCS input contains trailing content');
    }
    return value;
  }

  private parseValue(): unknown {
    const token = this.source[this.#index];
    if (token === '"') return this.parseString();
    if (token === '{') return this.parseObject();
    if (token === '[') return this.parseArray();
    if (token === 't' && this.consumeLiteral('true')) return true;
    if (token === 'f' && this.consumeLiteral('false')) return false;
    if (token === 'n' && this.consumeLiteral('null')) return null;
    if (token === '-' || (token !== undefined && token >= '0' && token <= '9')) {
      return this.parseNumber();
    }
    fail('malformed_json', 'JCS input contains an invalid JSON value');
  }

  private parseObject(): Record<string, unknown> {
    this.#index += 1;
    this.skipWhitespace();
    const result = Object.create(null) as Record<string, unknown>;
    const names = new Set<string>();
    if (this.consume('}')) return result;

    while (true) {
      if (this.source[this.#index] !== '"') {
        fail('malformed_json', 'JCS object member names must be JSON strings');
      }
      const name = this.parseString();
      if (names.has(name)) {
        fail('duplicate_member', 'JCS input contains duplicate object member names');
      }
      names.add(name);
      this.skipWhitespace();
      if (!this.consume(':')) {
        fail('malformed_json', 'JCS object member is missing a colon');
      }
      this.skipWhitespace();
      result[name] = this.parseValue();
      this.skipWhitespace();
      if (this.consume('}')) return result;
      if (!this.consume(',')) {
        fail('malformed_json', 'JCS object members must be comma-separated');
      }
      this.skipWhitespace();
    }
  }

  private parseArray(): unknown[] {
    this.#index += 1;
    this.skipWhitespace();
    const result: unknown[] = [];
    if (this.consume(']')) return result;

    while (true) {
      result.push(this.parseValue());
      this.skipWhitespace();
      if (this.consume(']')) return result;
      if (!this.consume(',')) {
        fail('malformed_json', 'JCS array elements must be comma-separated');
      }
      this.skipWhitespace();
    }
  }

  private parseString(): string {
    this.#index += 1;
    let result = '';
    while (this.#index < this.source.length) {
      const character = this.source[this.#index];
      if (character === '"') {
        this.#index += 1;
        assertScalarUnicode(result);
        return result;
      }
      if (character === '\\') {
        this.#index += 1;
        const escape = this.source[this.#index];
        const escaped = escape === '"' || escape === '\\' || escape === '/' ? escape
          : escape === 'b' ? '\b'
          : escape === 'f' ? '\f'
          : escape === 'n' ? '\n'
          : escape === 'r' ? '\r'
          : escape === 't' ? '\t'
          : undefined;
        if (escaped !== undefined) {
          result += escaped;
          this.#index += 1;
          continue;
        }
        if (escape !== 'u') {
          fail('malformed_json', 'JCS input contains an invalid string escape');
        }
        const hex = this.source.slice(this.#index + 1, this.#index + 5);
        if (!/^[0-9a-fA-F]{4}$/.test(hex)) {
          fail('malformed_json', 'JCS input contains an invalid Unicode escape');
        }
        result += String.fromCharCode(Number.parseInt(hex, 16));
        this.#index += 5;
        continue;
      }
      if (character < ' ' || character === undefined) {
        fail('malformed_json', 'JCS input contains an invalid JSON string');
      }
      result += character;
      this.#index += 1;
    }
    fail('malformed_json', 'JCS input contains an unterminated JSON string');
  }

  private parseNumber(): number {
    const match = /-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/y;
    match.lastIndex = this.#index;
    const found = match.exec(this.source);
    if (found === null) {
      fail('malformed_json', 'JCS input contains an invalid JSON number');
    }
    const token = found[0];
    this.#index += token.length;
    const value = Number(token);
    assertIJson(value, new Set<object>(), false);
    if (!/[.eE]/.test(token) && Math.abs(value) > MAX_SAFE_INTEGER) {
      fail('unsafe_integer', 'JCS input contains an integer outside the I-JSON safe range');
    }
    return value;
  }

  private consumeLiteral(literal: string): boolean {
    if (!this.source.startsWith(literal, this.#index)) return false;
    this.#index += literal.length;
    return true;
  }

  private consume(token: string): boolean {
    if (this.source[this.#index] !== token) return false;
    this.#index += 1;
    return true;
  }

  private skipWhitespace(): void {
    while (isJsonWhitespace(this.source[this.#index])) this.#index += 1;
  }
}

function parseV5JsonInternal(inputUtf8: string): unknown {
  if (inputUtf8.startsWith('\ufeff')) {
    fail('utf8_bom', 'JCS input must not begin with a UTF-8 BOM');
  }
  return new StrictJsonParser(inputUtf8).parse();
}

/** Parses strict JSON for the V5 profile, rejecting BOMs and duplicate member names. */
export function parseV5Json(inputUtf8: string): unknown {
  return parseV5JsonInternal(inputUtf8);
}

/** Decodes strict UTF-8 JSON input before applying the V5 parser. */
export function parseV5JsonUtf8(input: Uint8Array): unknown {
  if (input[0] === 0xef && input[1] === 0xbb && input[2] === 0xbf) {
    fail('utf8_bom', 'JCS input must not begin with a UTF-8 BOM');
  }
  let decoded: string;
  try {
    decoded = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(input);
  } catch {
    fail('malformed_json', 'JCS input is not valid UTF-8');
  }
  return parseV5Json(decoded);
}
