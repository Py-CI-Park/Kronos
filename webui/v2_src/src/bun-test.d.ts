declare module 'bun:test' {
  export const test: typeof import('node:test').test;
}
