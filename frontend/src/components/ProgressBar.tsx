interface ProgressBarProps {
  value: number; // 0–100
  size?: 'sm' | 'md';
  colorVar?: string;
  active?: boolean;
}

export default function ProgressBar({ value, size = 'sm', colorVar, active = false }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));

  const color =
    colorVar ??
    (clamped >= 80
      ? 'var(--color-success)'
      : clamped >= 50
        ? 'var(--color-warning)'
        : 'var(--color-danger)');

  return (
    <div
      className="progress-track"
      style={{ height: size === 'md' ? '8px' : '6px' }}
    >
      <div
        className={`progress-fill ${active ? 'progress-active' : ''}`}
        style={{
          width: `${clamped}%`,
          background: `linear-gradient(90deg, ${color}, color-mix(in srgb, ${color} 70%, white))`,
        }}
      />
    </div>
  );
}
