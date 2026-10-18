import React from 'react';
import { render } from '@testing-library/react';
import ChatMessage from './ChatMessage';

it('preserves formatted messages without executable markup', () => {
  const { container } = render(<ChatMessage role="assistant" message={'**Hello** <img src=x onerror="alert(1)"><script>alert(1)</script><a href="javascript:alert(1)">click</a>'} />);
  expect(container.querySelector('strong').textContent).toBe('Hello');
  expect(container.querySelector('script')).toBeNull();
  expect(container.querySelector('img').hasAttribute('onerror')).toBe(false);
  expect(container.querySelector('a').hasAttribute('href')).toBe(false);
});

it('blocks attribute injection through markdown images', () => {
  const { container } = render(<ChatMessage role="assistant" message={'![image](x" onerror="alert(1))'} />);
  expect(container.querySelector('[onerror]')).toBeNull();
});
