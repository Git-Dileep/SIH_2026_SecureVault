import { NavLink, useLocation } from 'react-router';
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
} from 'lucide-react';

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
    ],
  },
  {
    title: 'OPERATIONS',
    items: [
      { path: '/recovery/results', label: 'Recovery', icon: HardDrive },
      { path: '/erasure', label: 'Erasure', icon: ShieldOff },
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
      { path: '/audit', label: 'Audit Trail', icon: ScrollText },
      { path: '/settings', label: 'Settings', icon: Settings },
    ],
  }
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[240px] flex flex-col border-r"
      style={{
        background: 'var(--color-bg-surface)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-5 border-b" style={{ borderColor: 'var(--color-border)' }}>
        <div className="w-6 h-6 flex items-center justify-center rounded-sm"
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
            <h2 className="text-[11px] font-semibold mb-2 px-2 tracking-widest text-muted uppercase" style={{ color: 'var(--color-text-muted)' }}>
              {section.title}
            </h2>
            <div className="flex flex-col gap-0.5">
              {section.items.map((item) => {
                // simple active matching
                const isActive = item.path.split('#')[0] === '/' 
                  ? location.pathname === '/' 
                  : location.pathname.startsWith(item.path.split('#')[0]);
                
                const Icon = item.icon;

                return (
                  <NavLink
                    key={item.label}
                    to={item.path}
                    className="flex items-center gap-3 px-2 py-1.5 rounded text-[13px] font-medium transition-colors duration-100 no-underline"
                    style={{
                      background: isActive ? 'var(--color-bg-elevated)' : 'transparent',
                      color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                    }}
                  >
                    <Icon size={14} style={{ color: isActive ? 'var(--color-accent)' : 'var(--color-text-muted)' }} />
                    <span>{item.label}</span>
                  </NavLink>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      
      {/* Footer */}
      <div className="px-6 py-4 border-t text-[11px] font-mono text-muted" style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}>
        v2.4.1 (Stable)<br/>
        User: Admin
      </div>
    </aside>
  );
}
