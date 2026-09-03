import { useEffect, useState } from 'react';
import { API_BASE_URL, USE_MOCKS } from '../config';
import { getHealth } from '../api/recovery';
import type { HealthStatus } from '../types';
import PageHeader from '../components/PageHeader';

export default function Settings() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'API unreachable');
      });
  }, []);

  return (
    <>
      <PageHeader title="Settings" subtitle="Runtime configuration for this workstation" />

      <div className="grid grid-cols-2 gap-6">
        <div className="card flex flex-col gap-4">
          <h3 className="text-[13px] uppercase tracking-wider text-muted">API connection</h3>
          <div className="grid grid-cols-[140px_1fr] gap-2 text-[13px]">
            <span className="text-muted">Mock data</span>
            <span className="mono" style={{ color: USE_MOCKS ? 'var(--color-warning)' : 'var(--color-success)' }}>
              {USE_MOCKS ? 'ENABLED' : 'DISABLED'}
            </span>
            <span className="text-muted">API base URL</span>
            <span className="mono break-all">{API_BASE_URL}</span>
            <span className="text-muted">Engine</span>
            <span className="mono">{health ? `${health.tool} ${health.version}` : error ? 'unreachable' : 'checking…'}</span>
          </div>
          <p className="text-[12px] text-muted">
            {USE_MOCKS
              ? 'The UI is serving local mock data. Set VITE_USE_MOCKS=false to call ForensicRecover.'
              : error
                ? `Cannot reach ${API_BASE_URL}. Start the engine with python3 server.py`
                : 'The UI is calling the ForensicRecover API (carver.py, erasure.py, report.py).'}
          </p>
        </div>

        <div className="card flex flex-col gap-4">
          <h3 className="text-[13px] uppercase tracking-wider text-muted">Workstation</h3>
          <div className="grid grid-cols-[140px_1fr] gap-2 text-[13px]">
            <span className="text-muted">Product</span>
            <span className="mono">SecureVault / ForensicRecover</span>
            <span className="text-muted">Version</span>
            <span className="mono">{health?.version ?? '1.0.0-mvp'}</span>
            <span className="text-muted">Role</span>
            <span className="mono">local-operator</span>
            <span className="text-muted">Mode</span>
            <span className="mono">Read-only evidence · copy-only erasure demo</span>
          </div>
        </div>
      </div>
    </>
  );
}
