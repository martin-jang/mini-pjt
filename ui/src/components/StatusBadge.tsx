import type { RunStatus } from '../api/types';
import { STATUS_LABEL } from '../lib/format';

export type Tone = 'success' | 'waiting' | 'error' | 'pending' | 'running';

const DOT_CLASS: Record<Tone, string> = {
  success: 'bg-success',
  waiting: 'bg-warning',
  error: 'bg-error',
  pending: 'bg-pending',
  running: 'bg-running',
};

const STATUS_TONE: Record<RunStatus, Tone> = {
  running: 'running',
  awaiting_auth: 'waiting',
  awaiting_analysis: 'waiting',
  awaiting_design: 'waiting',
  done: 'success',
  stopped: 'error',
  failed: 'error',
};

export function Dot({ tone }: { tone: Tone }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block size-1.5 shrink-0 rounded-full ${DOT_CLASS[tone]}`}
    />
  );
}

interface BadgeProps {
  tone: Tone;
  children: string;
  plain?: boolean;
  testId?: string;
}

/** 상태 배지: 흰 배경 + 테두리 + 작은 상태 점. plain이면 테두리 없이 점과 글자만 */
export function Badge({ tone, children, plain = false, testId }: BadgeProps) {
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 text-xs whitespace-nowrap ${
        plain
          ? 'text-mute'
          : `rounded-full border border-hairline px-2.5 py-0.5 font-medium text-ink ${
              tone === 'waiting' ? 'bg-warning-soft' : 'bg-canvas'
            }`
      }`}
    >
      <Dot tone={tone} />
      {children}
    </span>
  );
}

export function StatusBadge({
  status,
  plain,
  testId,
}: {
  status: RunStatus;
  plain?: boolean;
  testId?: string;
}) {
  return (
    <Badge tone={STATUS_TONE[status]} plain={plain} testId={testId}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}
