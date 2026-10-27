import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import { AuthBoundary } from './auth/AuthBoundary.tsx';
import { initializeTelemetry } from './observability';
import './index.css';

if ((import.meta.env.VITE_APP_MODE ?? 'local') === 'local') {
  initializeTelemetry();
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthBoundary>
      <App />
    </AuthBoundary>
  </StrictMode>
);
