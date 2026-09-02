import type { ReactNode } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatCardProps {
  label: string;
  value: string | number;
  icon: ReactNode;
  trend?: { value: string; direction: 'up' | 'down' | 'flat' };
  accent?: string; // CSS color for the icon background
}

export default function StatCard({ label, value, icon, trend, accent = 'var(--color-accent)' }: StatCardProps) {
  return (
    <div className="card flex flex-col gap-4 group hover:translate-y-[-2px] transition-transform duration-200">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-medium" style={{ color: 'var(--color-text-muted)' }}>
          {label}
        </span>
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center transition-shadow duration-200"
          style={{
            background: `color-mix(in srgb, ${accent} 15%, transparent)`,
            color: accent,
          }}
        >
          {icon}
        </div>
      </div>
      <div className="flex items-end justify-between">
        <span className="text-[28px] font-bold leading-none tracking-tight" style={{ color: 'var(--color-text-primary)' }}>
          {value}
        </span>
        {trend && (
          <div className="flex items-center gap-1 text-[12px] font-medium" style={{
            color: trend.direction === 'up'
              ? 'var(--color-success)'
              : trend.direction === 'down'
                ? 'var(--color-danger)'
                : 'var(--color-text-muted)',
          }}>
            {trend.direction === 'up' && <TrendingUp size={14} />}
            {trend.direction === 'down' && <TrendingDown size={14} />}
            {trend.direction === 'flat' && <Minus size={14} />}
            <span>{trend.value}</span>
          </div>
        )}
      </div>
    </div>
  );
}
