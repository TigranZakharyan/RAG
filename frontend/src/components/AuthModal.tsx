import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Sparkles, ArrowRight, ShieldCheck } from 'lucide-react';

export const AuthModal: React.FC = () => {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;

    setError(null);
    setLoading(true);
    try {
      if (isRegister) {
        await register(username, password);
      } else {
        await login(username, password);
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrapper">
      <div className="auth-card animate-fade-in">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'center' }}>
          <div className="avatar">
            <Sparkles size={18} />
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700 }}>RAG Intelligence</h2>
        </div>

        <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          {isRegister
            ? 'Create an account to start chatting with your knowledge base'
            : 'Welcome back. Sign in to your workspace'}
        </p>

        {error && (
          <div style={{
            background: 'rgba(244, 63, 94, 0.12)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
            borderRadius: 'var(--radius-sm)',
            padding: '10px 12px',
            color: '#FB7185',
            fontSize: '0.8rem',
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="auth-input-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              className="auth-input"
              type="text"
              placeholder="e.g. johndoe"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>

          <div className="auth-input-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="auth-input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            id="auth-submit-btn"
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          >
            {loading ? (
              <span className="animate-spin">⏳</span>
            ) : (
              <>
                <span>{isRegister ? 'Sign Up' : 'Sign In'}</span>
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </form>

        <div style={{ display: 'flex', justifyContent: 'center', fontSize: '0.825rem', color: 'var(--text-muted)' }}>
          <span>
            {isRegister ? 'Already have an account?' : "Don't have an account?"}{' '}
            <button
              id="toggle-auth-mode-btn"
              onClick={() => {
                setIsRegister(!isRegister);
                setError(null);
              }}
              style={{ color: '#A5B4FC', fontWeight: 600, textDecoration: 'underline' }}
            >
              {isRegister ? 'Sign In' : 'Sign Up'}
            </button>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, color: 'var(--text-dim)', fontSize: '0.725rem' }}>
          <ShieldCheck size={14} />
          <span>Secured with JWT & Vector Hybrid Indexing</span>
        </div>
      </div>
    </div>
  );
};
