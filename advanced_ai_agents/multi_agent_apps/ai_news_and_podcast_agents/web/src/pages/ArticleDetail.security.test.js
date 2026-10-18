import React from 'react';
import { render, waitFor, fireEvent } from '@testing-library/react';
import ArticleDetail from './ArticleDetail';
import api from '../services/api';

jest.mock('react-router-dom', () => ({
  useParams: () => ({ articleId: '1' }),
  useNavigate: () => jest.fn(),
  Link: ({ children }) => children,
}));

jest.mock('../services/api', () => ({ articles: { getById: jest.fn() } }));

it('renders article formatting while stripping scripts and handlers', async () => {
  api.articles.getById.mockResolvedValue({ data: { title: 'Article', content: '<strong>Safe article</strong><img src=x onerror="alert(1)"><script>alert(1)</script>' + 'word '.repeat(130), categories: [] } });
  const { container, findByRole } = render(<ArticleDetail />);
  fireEvent.click(await findByRole('button', { name: 'Show full content' }));
  await waitFor(() => expect(container.querySelector('.article-content')).not.toBeNull());
  expect(container.querySelector('.article-content strong').textContent).toBe('Safe article');
  expect(container.querySelector('script')).toBeNull();
  expect(container.querySelector('[onerror]')).toBeNull();
});
