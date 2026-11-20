import { useEffect, useState } from 'react';
import { agentApi } from '../api/agentApi';
import type { SiteSummary } from '../api/types';

interface SitesState {
  sites: SiteSummary[];
  error?: string;
}

/** 사이드바 사이트 목록. 실행 상태가 바뀌면 다시 받는다 */
export function useSites(): SitesState {
  const [state, setState] = useState<SitesState>({ sites: [] });
  useEffect(() => {
    let alive = true;
    const load = () => {
      agentApi
        .listSites()
        .then((sites) => {
          if (alive) setState({ sites });
        })
        .catch((e: unknown) => {
          if (alive) {
            setState((prev) => ({
              sites: prev.sites,
              error: e instanceof Error ? e.message : '사이트 목록을 불러오지 못했습니다.',
            }));
          }
        });
    };
    load();
    const unwatch = agentApi.watchSites(load);
    return () => {
      alive = false;
      unwatch();
    };
  }, []);
  return state;
}
