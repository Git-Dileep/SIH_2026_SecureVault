import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
  fullHeight?: boolean;
}

export default function LoadingSpinner({ message = 'Loading...', fullHeight = false }: LoadingSpinnerProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-muted gap-4 ${fullHeight ? 'h-[60vh]' : 'py-12'}`}>
      <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-accent)' }} />
      <span className="text-[13px] uppercase tracking-wider">{message}</span>
    </div>
  );
}
