import type { ReactNode } from 'react';

interface TooltipProps {
  text: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  children: ReactNode;
}

/**
 * Reusable tooltip wrapper. Wraps any element with a hover tooltip.
 * Uses pure CSS positioning for zero-dependency, instant rendering.
 */
export default function Tooltip({ text, position = 'top', children }: TooltipProps) {
  if (!text) return <>{children}</>;

  return (
    <span className="tooltip-wrap">
      {children}
      <span className={`tooltip-text tooltip-${position}`}>{text}</span>
    </span>
  );
}
