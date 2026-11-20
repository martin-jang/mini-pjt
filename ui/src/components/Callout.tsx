import type { ReactNode } from 'react';
import { Icon } from './Icon';
import type { Tone } from './StatusBadge';

const TONE_CLASS: Record<Tone, string> = {
  success: 'border-l-success bg-canvas-soft-2',
  waiting: 'border-l-warning bg-warning-soft',
  error: 'border-l-error bg-error-soft',
  pending: 'border-l-pending bg-canvas-soft-2',
  running: 'border-l-running bg-running-soft',
};

interface CalloutProps {
  tone?: Tone;
  icon?: string;
  title?: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
  testId?: string;
}

/** 안내 배너: 상태 연한 배경 + 왼쪽 2px 상태 색 테두리 */
export function Callout({
  tone = 'pending',
  icon,
  title,
  children,
  actions,
  testId,
}: CalloutProps) {
  return (
    <div
      data-testid={testId}
      className={`flex items-center gap-3 rounded-md border-l-2 px-4 py-3 ${TONE_CLASS[tone]}`}
    >
      {icon && <Icon name={icon} className="text-body" />}
      <div className="min-w-0 flex-1 text-sm">
        {title && <p className="font-medium text-ink">{title}</p>}
        {children && <div className={title ? 'mt-0.5 text-body' : 'text-ink'}>{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
