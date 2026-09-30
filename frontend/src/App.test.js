import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the authentication entry point', () => {
  render(<App />);
  const linkElement = screen.getByRole('link', { name: /login \/ register/i });
  expect(linkElement).toBeInTheDocument();
});
