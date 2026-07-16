#!/usr/bin/env node
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "../webui/v2_src/node_modules/ajv/dist/2020.js";
import addFormats from "../webui/v2_src/node_modules/ajv-formats/dist/index.js";
import standaloneCode from "../webui/v2_src/node_modules/ajv/dist/standalone/index.js";
import { compile } from "../webui/v2_src/node_modules/json-schema-to-typescript/dist/src/index.js";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(scriptDir, "..");
const projectRoot = join(repositoryRoot, "webui", "v2_src");
const schemaPath = join(repositoryRoot, "docs", "schemas", "kronos_rl_api_v2.schema.json");
const packageLockPath = join(projectRoot, "package-lock.json");
const generatedDirectory = join(projectRoot, "src", "lib", "generated");
const outputNames = Object.freeze({
  types: "kronosRlApiV2.ts",
  validators: "kronosRlApiV2.validators.ts",
  semantic: "kronosRlApiV2.semantic.ts",
});
const outputManifest = Object.freeze(Object.values(outputNames).sort());
const handAuthoredOutputNames = Object.freeze(["kronosRlApiV2.test.ts"]);
const ajvOptions = Object.freeze({
  strict: true,
  strictSchema: true,
  strictTypes: true,
  strictTuples: true,
  allErrors: true,
  validateFormats: true,
  unicodeRegExp: true,
  ownProperties: true,
  coerceTypes: false,
  useDefaults: false,
  removeAdditional: false,
  allowUnionTypes: false,
  code: { esm: true, source: true, lines: true },
});
const typeOptions = Object.freeze({
  bannerComment: "",
  style: {
    singleQuote: true,
    semi: true,
    tabWidth: 2,
    useTabs: false,
    printWidth: 100,
    trailingComma: "es5",
    bracketSpacing: true,
  },
});

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}
function canonicalSchemaText(value) {
  return value.replace(/\r\n?/g, "\n");
}


function banner(schemaSha256, generator) {
  return `/* Generated from docs/schemas/kronos_rl_api_v2.schema.json; schema-sha256: ${schemaSha256}; ${generator}. Do not edit. */\n`;
}

function rootName(reference) {
  const match = /^#\/\$defs\/([A-Za-z][A-Za-z0-9]*)$/.exec(reference);
  if (!match) {
    throw new Error(`Expected a local root reference, received ${reference}.`);
  }
  return match[1];
}

function pascalCase(value) {
  return value.replace(/(^|[_-])([a-z0-9])/g, (_, __, character) => character.toUpperCase());
}

function validatorName(root) {
  return `validate${pascalCase(root)}`;
}

function rootTypeName(root) {
  return `V5${pascalCase(root)}`;
}

function schemaMetadata(schema) {
  const roots = schema.oneOf.map((entry) => rootName(entry.$ref));
  const descriptors = schema.$defs.routeDescriptors?.const;
  if (!descriptors || typeof descriptors !== "object") {
    throw new Error("Schema is missing $defs.routeDescriptors.const.");
  }

  const routeEntries = Object.entries(descriptors).map(([routeId, descriptor]) => {
    const root = descriptor.root;
    if (typeof root !== "string" || !roots.includes(root)) {
      throw new Error(`Route ${routeId} references an unknown root.`);
    }
    if (schema.$defs[root]?.properties?.route_id?.const !== routeId) {
      throw new Error(`Route ${routeId} does not match ${root}.route_id.`);
    }
    const pathBindings = descriptor.path_bindings;
    const queryBindings = descriptor.query_bindings ?? [];
    if (!Array.isArray(pathBindings) || pathBindings.some((name) => typeof name !== "string" || !name)) {
      throw new Error(`Route ${routeId} has invalid path_bindings.`);
    }
    if (!Array.isArray(queryBindings) || queryBindings.some((name) => typeof name !== "string" || !name)) {
      throw new Error(`Route ${routeId} has invalid query_bindings.`);
    }
    return { routeId, root, descriptor: { ...descriptor, path_bindings: pathBindings, query_bindings: queryBindings } };
  });
  const routeIds = schema.$defs.routeId?.enum;
  if (
    !Array.isArray(routeIds) ||
    routeIds.length !== routeEntries.length ||
    routeIds.some((routeId, index) => routeId !== routeEntries[index].routeId)
  ) {
    throw new Error("Schema routeId enum must exactly match routeDescriptors keys.");
  }
  return { roots, routeEntries };
}
function localDefinition(schema, reference, context) {
  const match = /^#\/\$defs\/([A-Za-z][A-Za-z0-9]*)$/.exec(reference ?? "");
  const definition = match && schema.$defs?.[match[1]];
  if (!definition || typeof definition !== "object") {
    throw new Error(`${context} must be a local $defs reference.`);
  }
  return definition;
}
function propertiesForFields(definition, fields, context) {
  const variants = Array.isArray(definition.oneOf) ? definition.oneOf : [definition];
  if (!variants.length || variants.some((variant) => !fields.every((field) => variant?.properties?.[field]))) {
    throw new Error(`${context} does not expose all cursor fields.`);
  }
  const properties = variants[0].properties;
  for (const field of fields) {
    if (variants.some((variant) => JSON.stringify(variant.properties[field]) !== JSON.stringify(properties[field]))) {
      throw new Error(`${context}.${field} must have one schema shape across variants.`);
    }
  }
  return properties;
}

function paginationMetadata(schema, routeEntries) {
  return Object.fromEntries(
    routeEntries
      .filter(({ descriptor }) => descriptor.cursor)
      .map(({ routeId, root, descriptor }) => {
        const item = localDefinition(
          schema,
          schema.$defs[root]?.properties?.list?.properties?.items?.items?.$ref,
          `${routeId}.list.items`,
        );
        const terms = descriptor.cursor.order.map((term) => {
          const [field, direction] = term.split(":");
          if (!field || !["asc", "desc"].includes(direction)) {
            throw new Error(`${routeId}.cursor.order contains an unsupported term.`);
          }
          return { field, direction };
        });
        const fields = terms.map(({ field }) => field);
        let properties;
        try {
          properties = propertiesForFields(item, fields, `${routeId} cursor item`);
        } catch {
          properties = null;
        }
        const nested = Object.entries(item.properties ?? {}).filter(([key, value]) => {
          if (!value || typeof value !== "object" || typeof value.$ref !== "string") return false;
          try {
            propertiesForFields(localDefinition(schema, value.$ref, `${routeId}.${key}`), fields, `${routeId}.${key}`);
            return true;
          } catch {
            return false;
          }
        });
        const path = properties ? [] : nested.length === 1 ? [nested[0][0]] : null;
        if (!path) throw new Error(`${routeId} cursor fields must be direct or share one nested object.`);
        if (path.length > 0) {
          properties = propertiesForFields(
            localDefinition(schema, item.properties[path[0]].$ref, `${routeId} cursor item`),
            fields,
            `${routeId}.${path[0]}`,
          );
        }
        return [
          routeId,
          {
            path,
            terms: terms.map(({ field, direction }) => ({
              field,
              direction,
              timestamp: properties[field]?.$ref === "#/$defs/utc",
            })),
          },
        ];
      }),
  );
}

function schemaSemantics(schema, routeEntries) {
  const progress = schema.$defs.progress?.properties;
  const maxProgress = progress?.step?.maximum;
  if (
    maxProgress !== Number.MAX_SAFE_INTEGER ||
    progress?.total_steps?.maximum !== maxProgress
  ) {
    throw new Error("progress.step and progress.total_steps must both cap at Number.MAX_SAFE_INTEGER.");
  }
  const eventVariants = schema.$defs.event?.oneOf;
  if (!Array.isArray(eventVariants)) throw new Error("event must use oneOf variants.");
  const eventProjections = Object.fromEntries(
    eventVariants.map((variant) => {
      const eventType = variant?.properties?.event_type?.const;
      const required = variant?.required;
      if (typeof eventType !== "string" || !Array.isArray(required)) {
        throw new Error("event variant must declare a constant event_type and required fields.");
      }
      const fields = required.filter(
        (field) => !["event_id", "occurred_at", "payload_sha256"].includes(field),
      );
      if (fields[0] !== "event_type" || fields.length < 2 || fields.some((field) => !variant.properties?.[field])) {
        throw new Error(`event variant ${eventType} has an unsupported payload projection.`);
      }
      return [eventType, fields];
    }),
  );
  const matrix = schema.$defs.matrixCell?.properties;
  const matrixSummary = schema.$defs.matrixSummary?.properties;
  if (
    !Array.isArray(matrix?.row_id?.enum) ||
    !Array.isArray(matrix?.column_id?.enum) ||
    !Array.isArray(matrix?.state?.enum) ||
    matrixSummary?.total_cells?.const !== matrix.row_id.enum.length * matrix.column_id.enum.length
  ) {
    throw new Error("matrix definitions must use complete row, column, state enums and a matching total.");
  }
  const artifact = schema.$defs.artifact?.properties;
  const filenamePattern = artifact?.filename?.pattern;
  const mediaTypes = artifact?.media_type?.enum;
  const mediaByExtension = schema.$defs.artifact?.["x-kronos-extension-media-map"];
  const extensions = typeof filenamePattern === "string" && /\\\.\(\?:([A-Za-z0-9|]+)\)\$$/.exec(filenamePattern)?.[1].split("|");
  if (
    typeof filenamePattern !== "string" ||
    !Array.isArray(mediaTypes) ||
    !mediaTypes.every((value) => typeof value === "string") ||
    !mediaByExtension ||
    typeof mediaByExtension !== "object" ||
    Array.isArray(mediaByExtension) ||
    !extensions ||
    new Set(extensions).size !== extensions.length ||
    Object.keys(mediaByExtension).length !== extensions.length ||
    Object.entries(mediaByExtension).some(([extension, mediaType]) => !extensions.includes(extension) || typeof mediaType !== "string") ||
    new Set(Object.values(mediaByExtension)).size !== Object.keys(mediaByExtension).length ||
    new Set(mediaTypes).size !== mediaTypes.length ||
    Object.values(mediaByExtension).length !== mediaTypes.length ||
    Object.values(mediaByExtension).some((mediaType) => !mediaTypes.includes(mediaType))
  ) {
    throw new Error("artifact.x-kronos-extension-media-map must uniquely and completely bind filename extensions to media_type enum values.");
  }
  return {
    eventProjections,
    eventVariants,
    filenamePattern,
    matrix: {
      rows: matrix.row_id.enum,
      columns: matrix.column_id.enum,
      states: matrix.state.enum,
      total: matrixSummary.total_cells.const,
    },
    maxProgress,
    mediaByExtension,
    mediaTypes,
    pagination: paginationMetadata(schema, routeEntries),
  };
}

async function resolvedVersions() {
  const packageLock = JSON.parse(await readFile(packageLockPath, "utf8"));
  const packageVersion = (packageName) => {
    const version = packageLock.packages?.[`node_modules/${packageName}`]?.version;
    if (typeof version !== "string") {
      throw new Error(`package-lock.json has no resolved version for ${packageName}.`);
    }
    return version;
  };
  return {
    ajv: packageVersion("ajv"),
    ajvFormats: packageVersion("ajv-formats"),
    jsonSchemaToTypescript: packageVersion("json-schema-to-typescript"),
  };
}

function typedDescriptors(routeEntries) {
  const imports = [...new Set(routeEntries.map(({ root }) => rootTypeName(root)))].sort();
  const entries = routeEntries
    .map(
      ({ routeId, root, descriptor }) =>
        `  ${routeId}: {\n    method: ${JSON.stringify(descriptor.method)},\n    path: ${JSON.stringify(descriptor.path)},\n    pathBindings: ${JSON.stringify(descriptor.path_bindings)},\n    queryBindings: ${JSON.stringify(descriptor.query_bindings)},\n    allowedErrors: ${JSON.stringify(descriptor.allowed_errors)},\n    validator: ${validatorName(root)} as V5Validator<${rootTypeName(root)}>,\n  },`,
    )
    .join("\n");
  return `\nimport type { ErrorObject } from 'ajv';\nimport type { ${imports.join(", ")}, V5RouteId } from './kronosRlApiV2';\n\nexport type V5Validator<T> = ((data: unknown) => data is T) & {\n  errors?: readonly ErrorObject[] | null;\n};\n\nexport type V5RouteRootMap = {\n  [K in V5RouteId]: Extract<${imports.join(" | ")}, { route_id: K }>;\n};\n\nexport type V5RouteDescriptorMap = {\n  [K in V5RouteId]: {\n    method: string;\n    path: string;\n    pathBindings: readonly string[];\n    queryBindings: readonly string[];\n    allowedErrors: readonly string[];\n    validator: V5Validator<V5RouteRootMap[K]>;\n  };\n};\n\nexport const v5RouteDescriptors = {\n${entries}\n} satisfies V5RouteDescriptorMap;\n`;
}
function schemaTypeExpression(definition) {
  if (typeof definition?.$ref === "string") return pascalCase(rootName(definition.$ref));
  if (Object.hasOwn(definition ?? {}, "const")) return JSON.stringify(definition.const);
  if (Array.isArray(definition?.enum) && definition.enum.length > 0) return definition.enum.map(JSON.stringify).join(" | ");
  if (["string", "number", "integer", "boolean", "null"].includes(definition?.type)) {
    return definition.type === "integer" ? "number" : definition.type;
  }
  throw new Error("Event variant property has an unsupported schema type.");
}

function postprocessTypes(types, routeEntries, eventVariants) {
  const errors = routeEntries.map(({ routeId, descriptor }) =>
    `  | { route_id: ${JSON.stringify(routeId)}; error: Omit<Error, "code"> & { code: ${descriptor.allowed_errors.map(JSON.stringify).join(" | ")} } }`,
  ).join("\n");
  const event = `export type Event =\n${eventVariants.map((variant) => {
    const required = variant?.required;
    if (variant?.type !== "object" || variant.additionalProperties !== false || !Array.isArray(required) || required.some((field) => typeof field !== "string" || !variant.properties?.[field])) {
      throw new Error("event.oneOf must contain closed object variants with declared required properties.");
    }
    return `  | { ${required.map((field) => `${field}: ${schemaTypeExpression(variant.properties[field])}`).join("; ")} }`;
  }).join("\n")};\nexport type ArtifactId`;
  const replaceExactly = (source, pattern, replacement, name) => {
    const matches = source.match(pattern);
    if (!matches || matches.length !== 1) throw new Error(`Generated type postprocess did not match exactly one ${name} declaration.`);
    return source.replace(pattern, replacement);
  };
  const withEvent = replaceExactly(types, /export type Event =[\s\S]*?;\nexport type ArtifactId/g, event, "Event");
  const withMatrixCells = replaceExactly(withEvent, /export type MatrixCells = (?:never\[\]|\[[\s\S]*?\]);/g, "export type MatrixCells = MatrixCell[];", "MatrixCells");
  return replaceExactly(withMatrixCells, /export type ErrorRoot =[\s\S]*?;\nexport type RouteId/g, `export type ErrorRoot =\n${errors};\nexport type RouteId`, "ErrorRoot");
}

function semanticOutput(schemaSha256, routeEntries, rules, semantics) {
  const descriptors = Object.fromEntries(routeEntries.map(({ routeId, descriptor }) => [routeId, descriptor]));
  return `${banner(schemaSha256, "canonical semantic_rules")}
import { canonicalizeV5Utf8 } from '../jcs';
import type { V5RouteId } from './kronosRlApiV2';
export class V5SemanticError extends Error { constructor(message: string) { super(message); this.name = 'V5SemanticError'; } }
export type V5SemanticContext = { method?: string; path?: string; pathParams?: Readonly<Record<string, string>>; queryParams?: Readonly<Record<string, string>> };
export const v5SemanticRules = ${JSON.stringify(rules, null, 2)} as const;
const routes = ${JSON.stringify(descriptors)} as const;
const pagination = ${JSON.stringify(semantics.pagination)} as const;
const eventProjections = ${JSON.stringify(semantics.eventProjections)} as const;
const matrix = ${JSON.stringify(semantics.matrix)} as const;
const maxProgress = ${semantics.maxProgress};
const portableFilenamePattern = new RegExp(${JSON.stringify(semantics.filenamePattern)}, 'u');
const mediaTypes = ${JSON.stringify(semantics.mediaTypes)} as readonly string[];
const mediaByExtension: Readonly<Record<string, string>> = ${JSON.stringify(semantics.mediaByExtension)};
const downloadUrlPattern = /^\\/api\\/v5\\/rl\\/artifacts\\/([A-Za-z0-9][A-Za-z0-9_-]{0,127})\\/download(?:\\?run_id=([A-Za-z0-9][A-Za-z0-9._%~-]{0,383})&(revision|run_revision)=([1-9][0-9]{0,15}))?$/u;
const fail = (message: string): never => { throw new V5SemanticError(message); };
const hasOwn = (value: object, key: string): boolean => Object.prototype.hasOwnProperty.call(value, key);
const canonicalJson = (value: unknown): string => new TextDecoder().decode(canonicalizeV5Utf8(value));
async function digest(value: unknown): Promise<string> { const bytes = canonicalizeV5Utf8(value); const hash = await crypto.subtle.digest('SHA-256', bytes as BufferSource); return Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, '0')).join(''); }
function roundedPercent(step: number, totalSteps: number): number { if (!Number.isSafeInteger(step) || !Number.isSafeInteger(totalSteps) || step > maxProgress || totalSteps > maxProgress) fail('invalid progress'); const numerator = BigInt(step) * 100000000n; const denominator = BigInt(totalSteps); const quotient = numerator / denominator; const remainder = numerator % denominator; return Number(quotient + (remainder * 2n >= denominator ? 1n : 0n)) / 1000000; }
function progress(value: any): void { if (!Number.isInteger(value.step) || !Number.isInteger(value.total_steps) || value.step < 0 || value.total_steps < 1 || value.step > maxProgress || value.total_steps > maxProgress || value.step > value.total_steps || value.percent !== roundedPercent(value.step, value.total_steps)) fail('invalid progress'); }
type Instant = readonly [number, string];
function instant(value: unknown): Instant { if (typeof value !== 'string') fail('invalid RFC3339 timestamp'); const text = value as string; const match = /^(\\d{4})-(\\d{2})-(\\d{2})T(\\d{2}):(\\d{2}):(\\d{2})(?:\\.(\\d+))?(Z|[+-]\\d{2}:\\d{2})$/.exec(text); if (!match) fail('invalid RFC3339 timestamp'); const [year, month, day, hour, minute, second] = match.slice(1, 7).map(Number), zone = match[8], fraction = (match[7] ?? '').replace(/0+$/, ''); if (year < 1 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59 || second > 59) fail('invalid RFC3339 timestamp'); const calendar = new Date(0); calendar.setUTCFullYear(year, month - 1, day); calendar.setUTCHours(hour, minute, second, 0); const local = calendar.getTime(); if (calendar.getUTCFullYear() !== year || calendar.getUTCMonth() !== month - 1 || calendar.getUTCDate() !== day) fail('invalid RFC3339 timestamp'); const offset = zone === 'Z' ? 0 : (Number(zone.slice(1, 3)) * 60 + Number(zone.slice(4, 6))) * (zone[0] === '+' ? 1 : -1); if (Math.abs(offset) > 23 * 60 + 59) fail('invalid RFC3339 timestamp'); return [local - offset * 60000, fraction]; }
function compareInstant(left: Instant, right: Instant): number { if (left[0] !== right[0]) return left[0] < right[0] ? -1 : 1; const width = Math.max(left[1].length, right[1].length), leftFraction = left[1].padEnd(width, '0'), rightFraction = right[1].padEnd(width, '0'); return leftFraction === rightFraction ? 0 : leftFraction < rightFraction ? -1 : 1; }
function state(value: any): void { progress(value.progress); const updated = instant(value.updated_at), started = value.started_at === null ? null : instant(value.started_at), finished = value.finished_at === null ? null : instant(value.finished_at); if (value.status === 'QUEUED' && (started !== null || finished !== null || value.progress.step !== 0)) fail('invalid queued state'); if (value.status === 'RUNNING' && (started === null || finished !== null)) fail('invalid running state'); if (['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(value.status) && (started === null || finished === null)) fail('invalid terminal state'); if (value.status === 'SUCCEEDED' && value.progress.step !== value.progress.total_steps) fail('incomplete succeeded state'); if ((started !== null && compareInstant(started, updated) > 0) || (finished !== null && (compareInstant(finished, updated) > 0 || (started !== null && compareInstant(finished, started) < 0)))) fail('unordered state timestamps'); }
function page(routeId: V5RouteId, payload: any): void { const rule = pagination[routeId as keyof typeof pagination] as { path: readonly string[]; terms: readonly { field: string; direction: 'asc' | 'desc'; timestamp: boolean }[] } | undefined; if (!rule) return; for (let index = 1; index < payload.list.items.length; index += 1) { const before = rule.path.reduce<any>((value, key) => value[key], payload.list.items[index - 1]), after = rule.path.reduce<any>((value, key) => value[key], payload.list.items[index]); let ordering = 0; for (const term of rule.terms) { const left = before[term.field], right = after[term.field]; if (typeof left !== 'string' || typeof right !== 'string') fail('page key is not a string'); const comparison = term.timestamp ? compareInstant(instant(left), instant(right)) : left === right ? 0 : left < right ? -1 : 1; if (comparison !== 0) { ordering = term.direction === 'desc' ? -comparison : comparison; break; } } if (ordering >= 0) fail('page items are not strictly in canonical order'); } }
function portableFilename(filename: string): boolean { return portableFilenamePattern.test(filename); }
function download(item: any): void { const artifact = item.artifact, extension = artifact.filename.split('.').at(-1), url = downloadUrlPattern.exec(item.download_url), hasRunId = hasOwn(item, 'run_id'), hasRunRevision = hasOwn(item, 'run_revision'); if (!portableFilename(artifact.filename) || !extension || mediaByExtension[extension] !== artifact.media_type || !mediaTypes.includes(artifact.media_type) || item.portable_filename !== artifact.filename || url === null || url[1] !== artifact.artifact_id || hasRunId !== hasRunRevision) fail('download metadata is not bound'); if (url[2] !== undefined && (!hasRunId || item.run_id !== url[2] || String(item.run_revision) !== url[4])) fail('download metadata is not bound'); }
export async function validateV5Semantic(routeId: V5RouteId, payload: any, context?: V5SemanticContext): Promise<void> {
  const route = routes[routeId]; if (payload.route_id !== routeId) fail('payload route_id does not match request');
  let expectedPath: string = route.path; for (const name of route.path_bindings as readonly string[]) { const value = context?.pathParams?.[name]; if (!value) fail(\`missing path binding \${name}\`); expectedPath = expectedPath.replace(\`{\${name}}\`, value); }
  if (context?.queryParams !== undefined) for (const name of route.query_bindings as readonly string[]) { const value = context.queryParams[name]; if (!value) fail(\`missing query binding \${name}\`); }
  if (context?.method && context.method !== route.method) fail('request method does not match route descriptor'); if (context?.path && context.path !== expectedPath) fail('request path does not match route descriptor');
  if (payload.error) { if (!(route.allowed_errors as readonly string[]).includes(payload.error.code)) fail('error code is not allowed for this route'); return; }
  const root = payload.source.source_sha256, same = (...values: string[]) => values.every((value) => value === root) || fail('nested source_sha256 differs from root source');
  if (routeId === 'RUN_DETAIL') { state(payload.run.state); same(payload.run.source_sha256); }
  else if (routeId === 'RUNS') for (const item of payload.list.items) { state(item.state); same(item.source_sha256); }
  else if (routeId === 'EVENTS') for (const event of payload.list.items) {
    if (event.event_type === 'PROGRESS') progress(event.progress);
    if (event.event_type === 'STATE') state(event.state);
    const fields = eventProjections[event.event_type as keyof typeof eventProjections];
    if (!fields) fail('unsupported event projection');
    const projection = Object.fromEntries(fields.map((field) => [field, event[field]]));
    if (event.payload_sha256 !== await digest(projection)) fail('event payload_sha256 does not match canonical payload projection');
  } else if (routeId === 'MATRIX') {
    const matrixOrder = matrix.rows.flatMap((row) => matrix.columns.map((column) => [row, column] as const));
    if (payload.cells.length !== matrix.total || payload.cells.some((cell: any, index: number) => cell.row_id !== matrixOrder[index][0] || cell.column_id !== matrixOrder[index][1])) fail('matrix cells are not canonical');
    const counts = Object.fromEntries(matrix.states.map((name) => [name.toLowerCase() + '_count', payload.cells.filter((cell: any) => cell.state === name).length]));
    if (canonicalJson(payload.summary) !== canonicalJson({ total_cells: matrix.total, ...counts })) fail('matrix summary does not conserve cells');
  } else if (routeId === 'LEDGER') for (const item of payload.list.items) same(item.source_sha256);
  else if (routeId === 'ARTIFACTS') for (const item of payload.list.items) download(item);
  else if (routeId === 'D0' || routeId === 'D1') same(payload[routeId.toLowerCase()].source_sha256);
  else if (routeId === 'FIXTURE') { state(payload.fixture.run.state); same(payload.fixture.source_sha256, payload.fixture.run.source_sha256); }
  page(routeId, payload);
  if ((route.path_bindings as readonly string[]).includes('run_id') && context?.pathParams?.run_id && (routeId === 'RUN_DETAIL' ? payload.run.run_id : payload.run_id) !== context.pathParams.run_id) fail('run_id path binding does not match payload');
}
`;
}

async function generate(outputDirectory) {
  const [schemaSource, versions] = await Promise.all([readFile(schemaPath, "utf8"), resolvedVersions()]);
  const schemaText = canonicalSchemaText(schemaSource);
  const schema = JSON.parse(schemaText);
  const { roots, routeEntries } = schemaMetadata(schema);
  const schemaSha256 = sha256(schemaText);
  const types = await compile(schema, "KronosRlApiV2", typeOptions);
  const typeAliases = roots.map((root) => `export type ${rootTypeName(root)} = ${pascalCase(root)};`).join("\n");
  const semantics = schemaSemantics(schema, routeEntries);
  const typeOutput = `${banner(schemaSha256, `json-schema-to-typescript@${versions.jsonSchemaToTypescript}`)}\n${postprocessTypes(types.trimEnd(), routeEntries, semantics.eventVariants)}\n\nexport type V5RouteId = RouteId;\nexport type V5DeepReadonly<T> = T extends (...args: never[]) => unknown ? T : T extends readonly (infer Item)[] ? readonly V5DeepReadonly<Item>[] : T extends object ? { readonly [K in keyof T]: V5DeepReadonly<T[K]> } : T;\n\n${typeAliases}\n`;

  const ajv = new Ajv2020(ajvOptions);
  ajv.addKeyword("x-kronos-extension-media-map");
  addFormats(ajv, { mode: "full", formats: ["date-time", "date", "uuid"] });
  ajv.addSchema(schema);
  const validatorReferences = Object.fromEntries(
    roots.map((root) => {
      const reference = `${schema.$id}#/$defs/${root}`;
      if (!ajv.getSchema(reference)) {
        throw new Error(`Unable to compile validator ${validatorName(root)}.`);
      }
      return [validatorName(root), reference];
    }),
  );
  const standalone = standaloneCode(ajv, validatorReferences)
    .replace(/const formats0 = require\("ajv-formats\/dist\/formats"\)\.fullFormats\["date-time"\];/, 'import formats from "ajv-formats/dist/formats.js";\nconst formats0 = formats.fullFormats["date-time"];')
    .replace(/const (func\d+) = require\("ajv\/dist\/runtime\/ucs2length"\)\.default;/, 'import ucs2length from "ajv/dist/runtime/ucs2length.js";\nconst $1 = ucs2length;')
    .trimEnd();
  const forbidden = standalone.match(/\b(?:require|eval)\s*\(/);
  if (forbidden) {
    throw new Error(`Generated standalone validator must be browser ESM without require or eval: ${standalone.slice(Math.max(0, forbidden.index - 80), forbidden.index + 120)}`);
  }
  const validatorOutput = `${banner(schemaSha256, `ajv@${versions.ajv} + ajv-formats@${versions.ajvFormats}`)}/* Ajv2020 options: ${JSON.stringify(ajvOptions)}; formats: date-time,date,uuid. */\n// @ts-nocheck\n${standalone}${typedDescriptors(routeEntries)}\n`;

  await mkdir(outputDirectory, { recursive: true });
  await Promise.all([
    writeFile(join(outputDirectory, outputNames.types), typeOutput, "utf8"),
    writeFile(join(outputDirectory, outputNames.validators), validatorOutput, "utf8"),
    writeFile(join(outputDirectory, outputNames.semantic), semanticOutput(schemaSha256, routeEntries, schema.$defs.semantic_rules.const, semantics), "utf8"),
  ]);
}

async function assertManifest(directory) {
  const manifest = new Set(await readdir(directory));
  const permitted = new Set([...outputManifest, ...handAuthoredOutputNames]);
  for (const outputName of outputManifest) {
    if (!manifest.has(outputName)) throw new Error(`Generated output is missing in ${directory}: ${outputName}.`);
  }
  for (const outputName of manifest) {
    if (!permitted.has(outputName)) throw new Error(`Unexpected generated-directory output in ${directory}: ${outputName}.`);
  }
}

async function byteCheck() {
  const [firstDirectory, secondDirectory] = await Promise.all([
    mkdtemp(join(tmpdir(), "kronos-v5-api-first-")),
    mkdtemp(join(tmpdir(), "kronos-v5-api-second-")),
  ]);
  try {
    await assertManifest(generatedDirectory);
    await Promise.all([generate(firstDirectory), generate(secondDirectory)]);
    await Promise.all([assertManifest(firstDirectory), assertManifest(secondDirectory)]);
    for (const outputName of outputManifest) {
      const [expected, first, second] = await Promise.all([
        readFile(join(generatedDirectory, outputName)),
        readFile(join(firstDirectory, outputName)),
        readFile(join(secondDirectory, outputName)),
      ]);
      if (!expected.equals(first) || !first.equals(second)) {
        throw new Error(`Generated ${outputName} differs. Run npm run generate:v5-api.`);
      }
    }
  } finally {
    await Promise.all([
      rm(firstDirectory, { recursive: true, force: true }),
      rm(secondDirectory, { recursive: true, force: true }),
    ]);
  }
}

if (process.argv.length !== 2 && !(process.argv.length === 3 && process.argv[2] === "--check")) {
  throw new Error("Usage: node scripts/generate_kronos_v5_api_types.mjs [--check]");
}

if (process.argv[2] === "--check") {
  await byteCheck();
} else {
  await generate(generatedDirectory);
}
