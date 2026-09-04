export default function ConfidenceBar({
  value,
  label,
}: {
  value: number;
  label?: string;
}) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const tone = pct >= 80 ? 'high' : pct >= 50 ? 'medium' : 'low';
  return (
    <div className="confidence-bar">
      <div className="flex justify-between text-[11px] mono mb-1">
        <span>{label ?? 'Confidence'}</span>
        <span>{pct}%</span>
      </div>
      <div className="confidence-track">
        <div className={`confidence-fill confidence-${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
