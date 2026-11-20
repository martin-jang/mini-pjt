import { useEffect, useState } from 'react';
import { agentApi } from '../api/agentApi';
import type { RunDetail } from '../api/types';

interface RunState {
  run?: RunDetail;
  error?: string;
}

/** 실행 스냅샷을 받고 SSE 이벤트로 갱신한다. log는 바로 붙이고, 그 외 변경은 스냅샷을 다시 받는다 */
export function useRun(alias: string | undefined): RunState {
  const [state, setState] = useState<RunState>({});
  useEffect(() => {
    if (!alias) return;
    let alive = true;
    const load = () => {
      agentApi
        .getRun(alias)
        .then((run) => {
          if (alive) setState({ run });
        })
        .catch((e: unknown) => {
          if (alive) setState({ error: e instanceof Error ? e.message : '불러오지 못했습니다.' });
        });
    };
    load();
    const unsubscribe = agentApi.streamRun(alias, (event) => {
      if (event.type === 'log') {
        setState((prev) =>
          prev.run ? { run: { ...prev.run, logs: [...prev.run.logs, event.line] } } : prev,
        );
      } else {
        load();
      }
    });
    return () => {
      alive = false;
      unsubscribe();
    };
  }, [alias]);
  return alias ? state : {};
}
