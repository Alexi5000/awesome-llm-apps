import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import test from 'node:test';

const appRequire = createRequire(resolve('package.json'));
const clientRequire = createRequire(appRequire.resolve('@motiadev/core'));
const roots = [...new Set([clientRequire, appRequire].map(require => dirname(require.resolve('zod/package.json'))))];
assert.equal(roots.length, 1);

for (const root of roots) {
  const require = createRequire(resolve(root, 'package.json'));
  const version = require('./package.json').version;
  assert.ok(['3.25.76', '4.6.7'].includes(version));
  const entries = version === '3.25.76' ? ['index.js', 'index.cjs', 'v3/index.js', 'v3/index.cjs'] : ['v3/index.js', 'v3/index.cjs'];
  for (const entry of entries) {
    const { z } = await import(pathToFileURL(resolve(root, entry)));
    const label = `zod ${version} ${entry}`;

    for (const kind of ['array max', 'array length', 'set max', 'set size']) {
      for (const async of [false, true]) {
        test(`${label}: ${kind} rejects oversized input before parsing elements (${async ? 'async' : 'sync'})`, async () => {
          let elements = 0;
          let refinements = 0;
          const element = z.any().superRefine((_value, ctx) => {
            elements++;
            ctx.addIssue({ code: 'custom', message: 'invalid element' });
          });
          let schema;
          let input;
          if (kind.startsWith('array')) {
            schema = kind.endsWith('length') ? z.array(element).length(2, 'collection too large') : z.array(element).max(2, 'collection too large');
            input = new Array(100_000).fill(1);
          } else {
            schema = kind.endsWith('size') ? z.set(element).size(2, 'collection too large') : z.set(element).max(2, 'collection too large');
            input = new Set(Array.from({ length: 100_000 }, (_, i) => i));
          }
          schema = z.object({ items: schema.superRefine(() => { refinements++; }) });
          const result = async ? await schema.safeParseAsync({ items: input }) : schema.safeParse({ items: input });
          assert.equal(result.success, false);
          assert.equal(result.error.issues.length, 1);
          assert.equal(result.error.issues[0].code, 'too_big');
          assert.equal(result.error.issues[0].message, 'collection too large');
          assert.deepEqual(result.error.issues[0].path, ['items']);
          assert.equal(elements, 0);
          assert.equal(refinements, 0);
        });
      }
    }

    test(`${label}: valid collections retain transforms and asynchronous refinements`, async () => {
      const value = z.string().transform(value => value.toUpperCase());
      assert.deepEqual(z.array(value).max(2).parse(['a', 'b']), ['A', 'B']);
      assert.deepEqual(z.array(value).length(2).parse(['a', 'b']), ['A', 'B']);
      assert.deepEqual([...z.set(value).size(2).parse(new Set(['a', 'b']))], ['A', 'B']);
      const asyncValue = z.string().refine(async value => value !== 'bad');
      assert.equal((await z.array(asyncValue).max(2).safeParseAsync(['a'])).success, true);
      assert.equal((await z.array(asyncValue).max(2).safeParseAsync(['bad'])).success, false);
      assert.equal((await z.set(asyncValue).max(2).safeParseAsync(new Set(['bad']))).success, false);
    });

    test(`${label}: zero bounds, types, and lower-size errors remain accurate`, () => {
      assert.deepEqual(z.array(z.string()).max(0).parse([]), []);
      assert.equal(z.array(z.string()).max(0).safeParse(['a']).error.issues[0].code, 'too_big');
      assert.equal(z.set(z.string()).max(0).safeParse(new Set(['a'])).error.issues[0].code, 'too_big');
      assert.equal(z.array(z.string()).length(0).safeParse(['a']).error.issues[0].exact, true);
      assert.equal(z.array(z.string()).max(2).safeParse(null).error.issues[0].code, 'invalid_type');
      assert.equal(z.set(z.string()).max(2).safeParse(['a']).error.issues[0].code, 'invalid_type');
      const tooSmall = z.array(z.string()).length(2).safeParse([1]);
      assert.deepEqual(tooSmall.error.issues.map(issue => issue.code), ['too_small', 'invalid_type']);
      const setTooSmall = z.set(z.string()).min(2).safeParse(new Set([1]));
      assert.deepEqual(setTooSmall.error.issues.map(issue => issue.code), ['too_small', 'invalid_type']);
    });

    test(`${label}: preprocess, union, defaults, and catch retain supported recovery`, () => {
      const bounded = z.array(z.number()).max(1);
      assert.deepEqual(z.preprocess(value => value.slice(0, 1), bounded).parse([1, 2]), [1]);
      assert.deepEqual(z.union([bounded, z.array(z.number()).max(2)]).parse([1, 2]), [1, 2]);
      assert.deepEqual(bounded.default([]).parse(undefined), []);
      assert.deepEqual(bounded.catch([]).parse([1, 2]), []);
      assert.deepEqual(z.array(z.number()).parse([1, 2]), [1, 2]);
    });


  }
}
