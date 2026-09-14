import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider } from '../context/AuthContext';
import App from '../App';

describe('App', () => {
  it('renders the login page initially when unauthenticated', () => {
    render(
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    );
    
    // Should see login text (e.g., from the Auth callback or layout)
    expect(screen.getByText(/log in/i, { selector: 'button' })).toBeInTheDocument();
  });
});
