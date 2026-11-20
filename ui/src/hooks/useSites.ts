import { useEffect, useState } from 'react';
import { agentApi } from '../api/agentApi';
import type { SiteSummary } from '../api/types';

/** 사이드바 사이트 목록. 실행 상태가 바뀌면 다시 받는다 */
export function useSites(): SiteSummary[] {
  const [sites, setSites] = useState<SiteSummary[]>([]);
  useEffect(() => {
    let alive = true;
    const load = () => {
      void agentApi.listSites().then((list) => {
        if (alive) setSites(list);
      });
    };
    load();
    const unwatch = agentApi.watchSites(load);
    return () => {
      alive = false;
      unwatch();
    };
  }, []);
  return sites;
}
