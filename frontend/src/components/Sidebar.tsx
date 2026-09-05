import { NavLink, useLocation, useNavigate, Link } from 'react-router';
import { clearSession, getOperator } from '../auth';
import { logoutOperator } from '../api/recovery';
import {
  LayoutDashboard,
  Database,
  Upload,
  HardDrive,
  ShieldOff,
  FileSearch,
  FileBarChart,
  ScrollText,
  Settings,
  Brain,
  ShieldAlert,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import Tooltip from './Tooltip';

const SECTIONS = [
  {
    title: 'OVERVIEW',
    items: [{ path: '/', label: 'Dashboard', icon: LayoutDashboard }],
  },
  {
    title: 'EVIDENCE',
    items: [
      { path: '/import#library', label: 'Evidence Library', icon: Database },
      { path: '/import', label: 'Import Evidence', icon: Upload },
      { path: '/demo/delete-recover', label: 'Delete → Recover', icon: FileSearch },
    ],
  },
  {
    title: 'OPERATIONS',
    items: [
      { path: '/recovery/results', label: 'Recovery', icon: HardDrive },
      { path: '/erasure', label: 'Erasure', icon: ShieldOff, requiresAdmin: true },
      { path: '/erasure/ssd', label: 'SSD-Aware Erasure', icon: ShieldOff, requiresAdmin: true },
      { path: '/ai/classifier', label: 'AI Classifier', icon: Brain },
    ],
  },
  {
    title: 'ANALYSIS',
    items: [
      { path: '/recovery/results#files', label: 'Recovered Files', icon: FileSearch },
      { path: '/reports', label: 'Reports', icon: FileBarChart },
    ],
  },
  {
    title: 'SYSTEM',
    items: [
      { path: '/audit/chain', label: 'Blockchain Audit', icon: ScrollText },
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  }
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const operator = getOperator();
  const { user, isAdmin } = useAuth();

  const signOut = async () => {
    try {
      await logoutOperator();
    } catch {
      /* still clear local session */
    }
    clearSession();
    navigate('/login', { replace: true });
  };

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[240px] flex flex-col border-r z-40"
      style={{
        background: 'var(--color-bg-surface)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-5 border-b" style={{ borderColor: 'var(--color-border)' }}>
        <div className="w-6 h-6 flex items-center justify-center rounded-sm hover-glow"
          style={{ background: 'var(--color-accent)' }}
        >
          <span className="text-[12px] font-bold text-white font-mono">SV</span>
        </div>
        <div>
          <h1 className="text-[14px] font-semibold tracking-tight uppercase" style={{ color: 'var(--color-text-primary)' }}>
            SecureVault
          </h1>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 flex flex-col overflow-y-auto">
        {SECTIONS.map((section, idx) => (
          <div key={idx} className="mb-6 px-4">
            <h2 className="text-[11px] font-semibold mb-2 px-2 tracking-widest text-muted uppercase">
              {section.title}
            </h2>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => {
                const current = `${location.pathname}${location.hash}`;
                const isActive = item.path === '/'
                  ? location.pathname === '/' && location.hash === ''
                  : current === item.path;
                
                const Icon = item.icon;
                const disabled = item.requiresAdmin && !isAdmin;

                const navLink = (
                  <NavLink
                    to={disabled ? '#' : item.path}
                    className={`flex items-center gap-3 px-2 py-1.5 rounded text-[13px] font-medium transition-colors duration-100 no-underline ${disabled ? 'role-disabled' : 'hover:bg-bg-surface-hover'}`}
                    style={{
                      background: isActive && !disabled ? 'var(--color-bg-elevated)' : '',
                      color: isActive && !disabled ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                    }}
                    onClick={(e) => disabled && e.preventDefault()}
                  >
                    <Icon size={14} style={{ color: isActive && !disabled ? 'var(--color-accent)' : 'var(--color-text-muted)' }} />
                    <span className="flex-1">{item.label}</span>
                    {disabled && <ShieldAlert size={12} className="text-warning" />}
                  </NavLink>
                );

                return (
                  <div key={item.label} className={disabled ? 'role-disabled-wrap' : ''}>
                    {disabled ? (
                      <Tooltip text="Only admins can access this" position="right">
                        {navLink}
                      </Tooltip>
                    ) : (
                      <Tooltip text={`Navigate to ${item.label}`} position="right">
                        {navLink}
                      </Tooltip>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      
      {/* Footer - User Profile & Sign Out */}
      <div className="p-4 border-t" style={{ borderColor: 'var(--color-border)' }}>
        <div className="flex items-center justify-between gap-2">
          <Link to="/profile" className="flex items-center gap-3 p-2 rounded hover:bg-bg-surface-hover transition-colors no-underline flex-1 min-w-0">
            <div className="w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-mono font-bold shrink-0"
                 style={{ background: 'var(--color-bg-elevated)', color: 'var(--color-text-primary)' }}>
              {user?.initials || operator?.substring(0,2).toUpperCase() || 'SV'}
            </div>
            <div className="flex flex-col flex-1 min-w-0">
              <span className="text-[12px] font-medium text-primary truncate">{user?.name || operator || 'Operator'}</span>
              <span className="text-[10px] text-muted mono uppercase">{user?.role || 'User'}</span>
            </div>
          </Link>
          <button type="button" className="btn-ghost p-2 rounded" onClick={() => void signOut()} title="Sign out">
            <span className="text-[11px] font-mono">Quit</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
