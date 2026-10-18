import assert from 'node:assert/strict';
import test from 'node:test';
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
