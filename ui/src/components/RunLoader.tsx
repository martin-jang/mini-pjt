import type { ReactNode } from 'react';
import { useParams } from 'react-router';
import type { RunDetail } from '../api/types';
import { useRun } from '../hooks/useRun';
import { Callout } from './Callout';

/** URL의 별칭으로 실행을 불러와 화면에 넘긴다 */
export function RunLoader({ children }: { children: (run: RunDetail) => ReactNode }) {
  const { alias } = useParams();
  const { run, error } = useRun(alias);
  if (error) {
    return (
      <Callout tone="error" icon="error" testId="run-error">
        {error}
      </Callout>
    );
  }
  if (!run || run.alias !== alias) return <p className="text-sm text-body">불러오는 중…</p>;
  return <>{children(run)}</>;
}
