import { createHttpAgentApi } from './httpAgentApi';
import { createMockAgentApi } from './mock/mockAgentApi';
import type {
  AnalysisDecision,
  AuthDecision,
  DesignDecision,
  NewRunInput,
  QueryAnswer,
  RunDetail,
  RunEvent,
  SiteSummary,
} from './types';

/** 콘솔이 에이전트와 주고받는 기능 전체. T04에서 같은 인터페이스로 실제 API 구현을 붙인다 */
export interface AgentApi {
  listSites(): Promise<SiteSummary[]>;
  /** 사이트 목록이 바뀔 때마다 알림. 해제 함수를 돌려준다 */
  watchSites(onChange: () => void): () => void;
  getRun(alias: string): Promise<RunDetail>;
  createRun(input: NewRunInput): Promise<RunDetail>;
  /** 실행 이벤트 스트림 (실제 API는 SSE). 해제 함수를 돌려준다 */
  streamRun(alias: string, onEvent: (event: RunEvent) => void): () => void;
  submitAnalysis(alias: string, decision: AnalysisDecision): Promise<void>;
  submitDesign(alias: string, decision: DesignDecision): Promise<void>;
  /** 사용자 인증 완료(또는 취소)를 알린다 */
  submitAuth(alias: string, decision: AuthDecision): Promise<void>;
  /** 저장된 로그인 세션 파일 삭제 (G10) */
  deleteSession(alias: string): Promise<void>;
  stopRun(alias: string): Promise<void>;
  ask(alias: string, question: string): Promise<QueryAnswer>;
}

export { ApiError } from './errors';

// 기본은 실제 에이전트 서버. VITE_USE_MOCK=1이면 목업(E2E 테스트·서버 없이 화면 확인용)
export const agentApi: AgentApi =
  import.meta.env.VITE_USE_MOCK === '1'
    ? createMockAgentApi({ tickMs: Number(import.meta.env.VITE_MOCK_TICK_MS ?? 600) })
    : createHttpAgentApi(import.meta.env.VITE_AGENT_API_URL ?? 'http://127.0.0.1:8000');
