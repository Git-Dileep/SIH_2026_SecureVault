import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router';
import { getToken, setSession } from '../auth';
import { loginOperator, registerOperator } from '../api/recovery';

export default function Login() {
  const navigate = useNavigate();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (getToken()) {
    return <Navigate to="/" replace />;
  }

  const switchMode = (next: 'login' | 'register') => {
    setMode(next);
    setError(null);
    setConfirm('');
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === 'register' && password !== confirm) {
      setError('Passwords do not match.');
      return;
    }
    setBusy(true);
    try {
      const result = mode === 'register'
        ? await registerOperator(username.trim(), password)
        : await loginOperator(username.trim(), password);
      const name = result.username || result.operator_id;
      setSession(name, result.token);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-shell">
      <aside className="login-brand" aria-hidden="true">
        <div className="login-brand-mark">SV</div>
        <div>
          <p className="login-kicker">SecureVault</p>
          <h1 className="login-brand-title">Forensic recovery and secure erasure</h1>
        </div>
      </aside>

      <main className="login-panel">
        <form className="login-card" onSubmit={(e) => void submit(e)}>
          <div className="login-card-head">
            <div className="login-brand-mark login-brand-mark-sm">SV</div>
            <h2>{mode === 'register' ? 'Create account' : 'Sign in'}</h2>
            <p>{mode === 'register' ? 'Choose a user ID and password.' : 'Enter your user ID and password.'}</p>
          </div>

          <div className="login-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              className={mode === 'login' ? 'is-active' : ''}
              onClick={() => switchMode('login')}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'register'}
              className={mode === 'register' ? 'is-active' : ''}
              onClick={() => switchMode('register')}
            >
              New user
            </button>
          </div>

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <label className="login-field" htmlFor="login-username">
            <span>User ID</span>
            <input
              id="login-username"
              className="input"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              minLength={3}
              maxLength={32}
              autoFocus
            />
          </label>

          <label className="login-field" htmlFor="login-password">
            <span>Password</span>
            <input
              id="login-password"
              className="input"
              type="password"
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </label>

          {mode === 'register' && (
            <label className="login-field" htmlFor="login-confirm">
              <span>Confirm password</span>
              <input
                id="login-confirm"
                className="input"
                type="password"
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                minLength={6}
              />
            </label>
          )}

          <button className="btn btn-primary login-submit" type="submit" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Sign in'}
          </button>
        </form>
      </main>
    </div>
  );
}
