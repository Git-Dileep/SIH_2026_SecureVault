import { Shield, ShieldAlert, Key } from 'lucide-react';
import { useAuth, type UserRole } from '../context/AuthContext';
import PageHeader from '../components/PageHeader';
import Tooltip from '../components/Tooltip';

export default function Profile() {
  const { user, isAdmin, setRole } = useAuth();

  const handleRoleToggle = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setRole(e.target.value as UserRole);
  };

  return (
    <>
      <PageHeader 
        title="Operator Profile" 
        subtitle="Manage your identity and workstation access" 
      />

      <div className="grid grid-cols-3 gap-6">
        <div className="card col-span-1 flex flex-col items-center text-center p-8">
          <div className="w-24 h-24 rounded-full flex items-center justify-center text-[32px] font-bold mb-6 font-mono" 
               style={{ background: 'var(--color-bg-elevated)', color: 'var(--color-accent)', border: '2px solid var(--color-border)' }}>
            {user.initials}
          </div>
          <h2 className="text-[18px] font-semibold mb-1">{user.name}</h2>
          <p className="text-[13px] text-muted mb-6">{user.email}</p>
          
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-[11px] font-mono font-bold uppercase tracking-wider mb-8"
               style={{ 
                 background: isAdmin ? 'var(--color-success-muted)' : 'var(--color-info-muted)', 
                 color: isAdmin ? 'var(--color-success)' : 'var(--color-info)',
                 border: `1px solid ${isAdmin ? 'var(--color-success)' : 'var(--color-info)'}` 
               }}>
            {isAdmin ? <Shield size={14} /> : <ShieldAlert size={14} />}
            {user.role}
          </div>

          <div className="w-full pt-6 border-t" style={{ borderColor: 'var(--color-border)' }}>
            <p className="text-[11px] text-muted uppercase tracking-wider mb-4">Demo Role Override</p>
            <div className="flex flex-col gap-2">
              <select className="input text-center font-mono" value={user.role} onChange={handleRoleToggle}>
                <option value="admin">Admin (Full Access)</option>
                <option value="employee">Employee (Restricted)</option>
              </select>
              <p className="text-[11px] text-muted leading-tight mt-1">
                Toggle role to test RBAC on the Erasure tab.
              </p>
            </div>
          </div>
        </div>

        <div className="col-span-2 flex flex-col gap-6">
          <div className="card">
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted mb-6 flex items-center gap-2">
              <Key size={14} />
              Access Permissions
            </h3>
            
            <div className="space-y-4">
              <div className="grid grid-cols-[200px_1fr] items-center gap-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
                <span className="text-[13px] font-medium">Evidence Library</span>
                <span className="badge badge-success w-fit">READ / WRITE</span>
              </div>
              <div className="grid grid-cols-[200px_1fr] items-center gap-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
                <span className="text-[13px] font-medium">Forensic Recovery</span>
                <span className="badge badge-success w-fit">EXECUTE</span>
              </div>
              <div className="grid grid-cols-[200px_1fr] items-center gap-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
                <span className="text-[13px] font-medium">Audit Log</span>
                <span className="badge badge-success w-fit">READ ONLY</span>
              </div>
              <div className="grid grid-cols-[200px_1fr] items-center gap-4 py-3 border-b" style={{ borderColor: 'var(--color-border)' }}>
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium">Secure Erasure</span>
                  {!isAdmin && <Tooltip text="Requires Admin role"><ShieldAlert size={14} className="text-warning" /></Tooltip>}
                </div>
                {isAdmin ? (
                  <span className="badge badge-success w-fit">EXECUTE</span>
                ) : (
                  <span className="badge badge-danger w-fit">DENIED</span>
                )}
              </div>
            </div>
          </div>

          <div className="card">
            <h3 className="text-[13px] font-medium uppercase tracking-wider text-muted mb-4">Current Session</h3>
            <div className="grid grid-cols-[140px_1fr] gap-x-4 gap-y-3 text-[13px]">
              <span className="text-muted">Workstation ID</span>
              <span className="mono">WS-0042-ALPHA</span>
              
              <span className="text-muted">IP Address</span>
              <span className="mono">127.0.0.1</span>
              
              <span className="text-muted">Session Started</span>
              <span className="mono">{new Date().toISOString().slice(0,19).replace('T', ' ')}</span>
              
              <span className="text-muted">Security Policy</span>
              <span className="mono">Strict (Local Only)</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
