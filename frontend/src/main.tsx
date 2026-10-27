import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { AuthBoundary } from './auth/AuthBoundary.tsx';
import './index.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthBoundary>
      <App />
    </AuthBoundary>
  </StrictMode>
);
