// 실제 에이전트 서버(FastAPI) 구현. 실행 이벤트는 SSE(EventSource)로 받는다

import type { AgentApi } from './agentApi';
import { ApiError } from './errors';
import type { QueryAnswer, RunDetail, RunEvent, SiteSummary } from './types';

interface QueryResponse {
  intent: 'new' | 'extend' | 'query' | 'out_of_scope';
  run?: RunDetail | null;
  answer?: QueryAnswer | null;
}

export function createHttpAgentApi(baseUrl: string): AgentApi {
  const url = (path: string) => `${baseUrl.replace(/\/$/, '')}${path}`;
  const sitePath = (alias: string) => `/runs/${encodeURIComponent(alias)}`;

  async function request<T>(path: string, body?: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(url(path), {
        method: body === undefined ? 'GET' : 'POST',
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(
        `에이전트 서버(${baseUrl})에 연결할 수 없습니다. 서버가 켜져 있는지 확인하세요.`,
      );
    }
    if (!res.ok) {
      let detail: string | undefined;
      try {
        const data = (await res.json()) as { detail?: unknown };
        if (typeof data.detail === 'string') detail = data.detail;
      } catch {
        // 본문이 JSON이 아니면 상태 코드로 알린다
      }
      throw new ApiError(detail ?? `요청에 실패했습니다 (HTTP ${res.status}).`);
    }
    return (await res.json()) as T;
  }

  /** EventSource 구독. 끊기면 브라우저가 자동으로 다시 연결한다 */
  function subscribe(path: string, onMessage: (data: string) => void): () => void {
    const source = new EventSource(url(path));
    source.onmessage = (e: MessageEvent<string>) => onMessage(e.data);
    return () => source.close();
  }

  return {
    listSites: () => request<SiteSummary[]>('/runs'),

    watchSites: (onChange) => subscribe('/events', () => onChange()),

    getRun: (alias) => request<RunDetail>(sitePath(alias)),

    createRun: async (input) => {
      const res = await request<QueryResponse>('/query', input);
      if (!res.run) throw new ApiError('실행을 시작하지 못했습니다.');
      return res.run;
    },

    streamRun: (alias, onEvent) =>
      subscribe(`${sitePath(alias)}/events`, (data) => onEvent(JSON.parse(data) as RunEvent)),

    submitAnalysis: async (alias, decision) => {
      await request(`${sitePath(alias)}/analysis`, decision);
    },

    submitDesign: async (alias, decision) => {
      await request(`${sitePath(alias)}/design`, decision);
    },

    submitAuth: async (alias, decision) => {
      await request(`${sitePath(alias)}/auth`, decision);
    },

    deleteSession: async (alias) => {
      await request(`${sitePath(alias)}/session/delete`, {});
    },

    stopRun: async (alias) => {
      await request(`${sitePath(alias)}/stop`, {});
    },

    ask: async (alias, question) => {
      const res = await request<QueryResponse>('/query', { alias, question });
      if (!res.answer) throw new ApiError('답변을 받지 못했습니다.');
      return res.answer;
    },
  };
}
