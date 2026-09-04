import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export default function AccuracyComparison({
  traditional = 0.65,
  ours = 0.8815,
}: {
  traditional?: number;
  ours?: number;
}) {
  const data = [
    { name: 'Traditional signatures', accuracy: Math.round(traditional * 100) },
    { name: 'SecureVault AI', accuracy: Math.round(ours * 100) },
  ];
  return (
    <div>
      <div className="flex items-end gap-4 mb-4">
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">Traditional</div>
          <div className="text-[28px] font-mono">{Math.round(traditional * 100)}%</div>
        </div>
        <div className="text-muted pb-2">vs</div>
        <div>
          <div className="text-[11px] uppercase tracking-wider text-muted">Our AI</div>
          <div className="text-[28px] font-mono" style={{ color: 'var(--color-success)' }}>{Math.round(ours * 100)}%</div>
        </div>
      </div>
      <div style={{ width: '100%', height: 180 }}>
        <ResponsiveContainer>
          <BarChart data={data} barSize={48}>
            <CartesianGrid stroke="var(--color-border)" vertical={false} />
            <XAxis dataKey="name" tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: 'var(--color-text-muted)', fontSize: 11 }} axisLine={false} />
            <Tooltip
              contentStyle={{ background: 'var(--color-bg-elevated)', border: '1px solid var(--color-border)' }}
              formatter={(value) => [`${String(value)}%`, 'Accuracy']}
            />
            <Bar dataKey="accuracy" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
