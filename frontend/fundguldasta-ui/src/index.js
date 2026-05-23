import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error, info) {
    console.error('[FundGuldasta] Runtime error:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', alignItems: 'center',
          justifyContent: 'center', background: '#090C11', padding: 24,
          fontFamily: 'Outfit, sans-serif',
        }}>
          <div style={{ maxWidth: 480, textAlign: 'center' }}>
            <div style={{
              fontFamily: '"Cormorant Garamond", serif', fontSize: 36,
              color: '#D4AF37', marginBottom: 16, fontWeight: 600,
            }}>Something went wrong</div>
            <div style={{
              fontSize: 14, color: 'rgba(255,255,255,0.5)',
              lineHeight: 1.8, marginBottom: 28,
            }}>
              An unexpected error occurred. Your data is safe.<br />
              Please refresh the page to continue.
            </div>
            <button
              onClick={() => window.location.reload()}
              style={{
                background: 'linear-gradient(135deg,rgba(212,175,55,0.15),rgba(212,175,55,0.05))',
                border: '1px solid rgba(212,175,55,0.35)', borderRadius: 12,
                padding: '12px 36px', color: '#D4AF37', fontSize: 14,
                fontWeight: 600, cursor: 'pointer', fontFamily: 'Outfit, sans-serif',
                letterSpacing: '.04em',
              }}
            >
              Refresh Page
            </button>
            <div style={{ marginTop: 20, fontSize: 11, color: 'rgba(255,255,255,0.2)' }}>
              FundGuldasta — Mutual Fund Research. Unfiltered.
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

const container = document.getElementById('root');
const root = createRoot(container);
root.render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
