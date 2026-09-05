import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  message: string;
  action?: ReactNode;
}

export default function EmptyState({ icon, title, message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border-2 border-dashed rounded-lg" style={{ borderColor: 'var(--color-border-subtle)' }}>
      <div className="w-12 h-12 rounded-full flex items-center justify-center mb-4" style={{ background: 'var(--color-bg-elevated)', color: 'var(--color-text-muted)' }}>
        {icon}
      </div>
      <h3 className="text-[14px] font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>{title}</h3>
      <p className="text-[13px] max-w-sm mb-6" style={{ color: 'var(--color-text-secondary)' }}>{message}</p>
      {action && <div>{action}</div>}
    </div>
  );
}
