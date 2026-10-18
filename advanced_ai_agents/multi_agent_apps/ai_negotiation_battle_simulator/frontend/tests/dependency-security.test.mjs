import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const katex = createRequire(require.resolve('@copilotkit/react-core'))('katex');
import parser from 'postcss-selector-parser';
import postcss from 'postcss';
import nested from 'postcss-nested';
import tailwindcss from 'tailwindcss';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
const uiRequire = createRequire(require.resolve('@copilotkit/react-ui'));
const { default: ReactMarkdown } = await import(uiRequire.resolve('react-markdown'));
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';

test('KaTeX ignores inherited trust while preserving explicit trusted rendering', () => {
  const expression = String.raw`\href{javascript:alert(1)}{click}`;
  const inherited = Object.create({ trust: true });
  assert.doesNotMatch(katex.renderToString(expression, inherited), /href="javascript:/);
  Object.defineProperty(Object.prototype, 'trust', { value: true, configurable: true, writable: true });
  try {
    assert.doesNotMatch(katex.renderToString(expression), /href="javascript:/);
  } finally {
    delete Object.prototype.trust;
  }
  assert.match(katex.renderToString(expression, { trust: true }), /href="javascript:/);
});

test('Markdown math integrates with the updated KaTeX renderer', () => {
  const html = renderToStaticMarkup(React.createElement(ReactMarkdown, {
    remarkPlugins: [remarkMath], rehypePlugins: [rehypeKatex],
    children: 'Cost: $x^2 + \\frac{1}{2}$.\n\n$$\n\\sum_{i=1}^{n} i\n$$',
  }));
  assert.match(html, /class="katex"/);
  assert.match(html, /katex-display/);
  assert.match(html, /<math/);
  assert.doesNotMatch(html, /katex-error/);
});

test('Selector parser preserves complex selectors and handles large flat input', () => {
  for (const css of ['.card:hover > :is(.active, #selected)', '.sm\\:hover\\:bg-blue-500:hover', '[data-state="open"] + .panel::before']) {
    assert.equal(parser().processSync(css), css);
  }
  execFileSync(process.execPath, ['-e', "const assert=require('node:assert/strict'); const parser=require('postcss-selector-parser'); const flat='.a'.repeat(200000); assert.equal(parser().processSync(flat),flat);"], { cwd: new URL('..', import.meta.url), timeout: 10000 });
});

test('Nested CSS and Tailwind arbitrary/group variants compile through parser7', async () => {
  const result = await postcss([nested(), tailwindcss({
    content: [{ raw: '<div class="group flex hover:bg-blue-500 [&>p]:mt-2"><p class="group-hover:text-white"></p></div>' }],
    corePlugins: { preflight: false },
  })]).process('@tailwind utilities; .card { &:hover { @apply text-red-500; } & > .child { display: block; } }', { from: undefined });
  assert.match(result.css, /\.card:hover/);
  assert.match(result.css, /\.card > \.child/);
  assert.match(result.css, /display: flex/);
  assert.match(result.css, /group:hover/);
  assert.match(result.css, /margin-top: 0\.5rem/);
  assert.match(result.css, /239 68 68/);
});

test('Selector parser rejects excessive pseudo nesting', () => {
  const deep = ':is('.repeat(2000) + '.x' + ')'.repeat(2000);
  assert.throws(() => parser().processSync(deep), /depth|nesting/i);
});


test('Tailwind consumers use the verified braces backport and retain glob matching', async () => {
  execFileSync(process.execPath, ['scripts/verify-braces.cjs'], { cwd: new URL('..', import.meta.url), timeout: 10000 });
  const tailwindRequire = createRequire(require.resolve('tailwindcss'));
  const glob = tailwindRequire('fast-glob');
  const matcher = createRequire(tailwindRequire.resolve('fast-glob'))('micromatch');
  const directory = mkdtempSync(path.join(tmpdir(), 'negotiation-braces-'));
  try {
    mkdirSync(path.join(directory, 'components'));
    writeFileSync(path.join(directory, 'components', 'lesson.tsx'), '<div class="text-purple-500"/>');
    writeFileSync(path.join(directory, 'components', 'panel.jsx'), '<div class="font-bold"/>');
    writeFileSync(path.join(directory, 'components', 'ignored.md'), 'ignore');
    assert.deepEqual(glob.sync('components/*.{tsx,jsx}', { cwd: directory }).sort(), ['components/lesson.tsx', 'components/panel.jsx']);
    assert.deepEqual(matcher(['lesson.tsx', 'panel.jsx', 'ignored.md'], '*.{tsx,jsx}'), ['lesson.tsx', 'panel.jsx']);
    const result = await postcss([tailwindcss({
      content: [path.join(directory, 'components', '*.{tsx,jsx}')],
      corePlugins: { preflight: false },
    })]).process('@tailwind utilities;', { from: undefined });
    assert.match(result.css, /\.text-purple-500/);
    assert.match(result.css, /\.font-bold/);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('real micromatch and fast-glob consumers reject excessive brace recursion promptly', () => {
  execFileSync(process.execPath, ['-e', `
    const assert = require('node:assert/strict');
    const { createRequire } = require('node:module');
    const load = createRequire(require.resolve('tailwindcss'));
    const glob = load('fast-glob');
    const matcher = createRequire(load.resolve('fast-glob'))('micromatch');
    const deep = '{'.repeat(4000) + 'a,b' + '}'.repeat(4000);
    assert.throws(() => matcher.braces(deep), /depth/i);
    assert.throws(() => glob.generateTasks(deep), /depth/i);
  `], { cwd: new URL('..', import.meta.url), timeout: 5000 });
});
