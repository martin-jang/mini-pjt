// 콘솔 ↔ 에이전트 API 데이터 구조. T04에서 실제 FastAPI 응답도 이 형태를 따른다

export type RunKind = 'new' | 'extend';

/** 실행 전체 상태 */
export type RunStatus =
  | 'running'
  | 'awaiting_auth'
  | 'awaiting_analysis'
  | 'awaiting_design'
  | 'done'
  | 'stopped'
  | 'failed';

/** 로그인 화면 유형: 로그인 아님 / 아이디·비밀번호 / 공동·공인인증서 / 간편인증 / 판단 어려움 */
export type LoginKind = 'none' | 'id_pw' | 'certificate' | 'simple_auth' | 'unknown';

/** 사용자에게 넘긴 인증 (진행 화면 "인증 대기" 카드) */
export interface AuthRequest {
  loginKind: LoginKind;
  reason: string;
  /** 사용자가 인증할 화면 주소 (에이전트가 띄운 브라우저 창에 열려 있음) */
  url: string;
}

/** done: 브라우저에서 인증을 마침, cancel: 실행을 멈춤 */
export interface AuthDecision {
  action: 'done' | 'cancel';
}

export type StageId =
  'explorer' | 'analyst' | 'analysisReview' | 'designer' | 'designReview' | 'builder' | 'verifier';

export type StageState = 'pending' | 'running' | 'waiting' | 'done' | 'stopped';

export interface StageInfo {
  id: StageId;
  state: StageState;
  /** 단계 옆에 붙는 짧은 진행 정보 (예: "12개 화면 · 3분 12초") */
  note?: string;
}

export type LogSource =
  | 'system'
  | 'router'
  | 'explorer'
  | 'analyst'
  | 'designer'
  | 'builder'
  | 'verifier'
  | 'gate'
  | 'guard';

export type LogLevel = 'info' | 'warn' | 'block';

export interface LogLine {
  at: string;
  source: LogSource;
  level: LogLevel;
  message: string;
}

export type GuardrailId = 'G1' | 'G2' | 'G3' | 'G4' | 'G5' | 'G6' | 'G7' | 'G8' | 'G9';
export type GuardrailOutcome = 'masked' | 'blocked' | 'skipped' | 'approved';

export interface GuardrailEvent {
  at: string;
  rule: GuardrailId;
  detail: string;
  outcome: GuardrailOutcome;
}

export interface RunMetrics {
  screensCollected: number;
  llmCalls: number;
  llmLimit: number;
}

/** 시간 기록 (엔드투엔드 = 에이전트 처리 + 승인 대기) */
export interface RunTiming {
  startedAt: string;
  finishedAt?: string;
  waitMs: number;
  waitingSince?: string;
}

// ── 분석 리뷰 ─────────────────────────────

export interface SiteProfile {
  domain: string;
  users: string;
  coreTasks: string;
  confidence: number;
  summary: string;
  evidence: { screen: string; path: string }[];
}

export interface HappyPathCandidate {
  id: string;
  title: string;
  steps: string[];
  reason: string;
  recommended: boolean;
}

export type DataMode = 'mock' | 'legacy';

export interface DataModeOption {
  mode: DataMode;
  title: string;
  summary: string;
  reasons: string[];
  caveat?: string;
  recommended: boolean;
}

export type VariantDecision = 'unify' | 'prop' | 'hold';

export interface VariantGroup {
  id: string;
  name: string;
  selectors: string[];
  screenCount: number;
  decision: VariantDecision;
  reason: string;
}

export interface AnalysisReview {
  profile: SiteProfile;
  happyPaths: HappyPathCandidate[];
  dataModes: DataModeOption[];
  variants: VariantGroup[];
}

export type ReviewAction = 'approve' | 'revise' | 'reject';

export interface AnalysisDecision {
  action: ReviewAction;
  happyPathIds: string[];
  dataMode: DataMode;
  variantDecisions: Record<string, VariantDecision>;
  comment?: string;
}

// ── 디자인 확인 ─────────────────────────────

/** 레이아웃 비교용 간단한 구조 (스크린샷 대신 목업에서 그리는 도식) */
export interface LayoutSketch {
  nav: 'left' | 'top' | 'none';
  blocks: string[];
}

export type ScreenReviewState = 'pending' | 'approved' | 'revise';

/** 바뀐 점과 그렇게 바꾼 이유 */
export interface DesignChange {
  what: string;
  why: string;
}

export interface DesignScreen {
  id: string;
  name: string;
  path: string;
  majorChange: boolean;
  changes: DesignChange[];
  state: ScreenReviewState;
  /** 일반 변경 화면은 자동 승인된다 (대폭 변경 화면만 사용자 승인) */
  autoApproved?: boolean;
  asis: LayoutSketch;
  tobe: LayoutSketch;
}

export interface DesignReview {
  designSystem: string;
  screens: DesignScreen[];
}

export type DesignDecision =
  | { action: 'approveScreen'; screenId: string }
  | { action: 'revise'; screenId: string; comment: string }
  | { action: 'rejectAll'; comment?: string };

// ── 결과 ─────────────────────────────

export interface GeneratedScreen {
  name: string;
  path: string;
  happyPath?: string;
  preserved: number;
  total: number;
}

export interface VerificationItem {
  id: string;
  label: string;
  detail: string;
  passed: boolean;
}

export interface RunResult {
  outputDir: string;
  previewUrl: string;
  totalScreens: number;
  screens: GeneratedScreen[];
  components: string[];
  decisions: { label: string; value: string }[];
  verification: VerificationItem[];
}

// ── 실행 ─────────────────────────────

export interface SiteSummary {
  alias: string;
  url: string;
  status: RunStatus;
}

// ── 사이트맵 (T07c Map) ─────────────────────────────

export interface SiteMapScreen {
  screenId: string;
  title: string;
  url: string;
  depth: number;
  tables: number;
  forms: number;
  buttons: number;
  /** 이 화면으로 들어오는 이동 수 */
  inbound: number;
  /** 화면 데이터 출처: observed(실제로 봄)·inferred(구조만 봄)·synthetic(합성 데이터) */
  dataSource?: DataSource;
}

export type DataSource = 'observed' | 'inferred' | 'synthetic';

export interface SiteMapMenuItem {
  label: string;
  /** 이 메뉴로 수집한 화면 (못 갔으면 null) */
  screenId?: string | null;
  children: SiteMapMenuItem[];
}

export type SiteMapLinkStatus = 'blocked' | 'skipped' | 'limit' | 'failed';

/** 따라가지 않은 링크와 이유 */
export interface SiteMapLink {
  label: string;
  url?: string | null;
  status: SiteMapLinkStatus;
  reason: string;
}

export interface SiteMapView {
  screens: SiteMapScreen[];
  menu: SiteMapMenuItem[];
  /** 이동 상태별 수: followed, duplicate, blocked, skipped, limit, failed */
  edgeCounts: Partial<Record<string, number>>;
  notFollowed: SiteMapLink[];
  /** 화면 수 상한에 닿아 멈췄는지 */
  truncated: boolean;
}

// ── 유스케이스·흐름 걷기 (T07d Hypothesize · Walk) ─────────────────────────────

export interface WalkStepView {
  index: number;
  action: string;
  target?: string | null;
  value?: string | null;
  toTitle: string;
  toUrl: string;
}

export type WalkStatus = 'completed' | 'partial' | 'failed' | 'untried';

export interface WalkCandidateView {
  id: string;
  name: string;
  /** view·search·input·other */
  kind: string;
  goal: string;
  /** 점수 합계 (20점 만점) */
  total: number;
  score: Record<string, number>;
  reason: string;
  status: WalkStatus;
  /** 완주 못 한 이유 종류: no_data·needs_auth·write_action·not_found·step_limit·other */
  failKind?: string | null;
  /** 완주했으면 도착 설명, 아니면 실패 이유 */
  result: string;
  steps: WalkStepView[];
  /** 재실행 스크립트로 LLM 없이 다시 걸었을 때 재현됐는지 */
  replayOk?: boolean | null;
  replayMessage: string;
  /** 빈 조회 결과 대응: found(조건 넓혀 찾음)·still_empty(합성 데이터로 보완) */
  dataRecovery?: 'found' | 'still_empty' | null;
  /** 합성 데이터 파일 (crawl 폴더 기준) */
  fixture?: string | null;
}

export interface WalkView {
  domain: string;
  users: string;
  coreTasks: string[];
  candidates: WalkCandidateView[];
}

export interface RunDetail extends SiteSummary {
  kind: RunKind;
  stages: StageInfo[];
  metrics: RunMetrics;
  timing: RunTiming;
  logs: LogLine[];
  guardrails: GuardrailEvent[];
  /** 사용자 인증 대기 중일 때만 있음 */
  auth?: AuthRequest | null;
  /** 저장된 로그인 세션 파일이 있는지 (G10: 실행이 끝나면 삭제를 권한다) */
  sessionSaved?: boolean;
  /** 화면 수집 사이트맵 (Explorer Map 이후) */
  sitemap?: SiteMapView | null;
  /** 유스케이스 후보와 흐름 걷기 결과 */
  walk?: WalkView | null;
  analysis?: AnalysisReview;
  /** 승인된 분석 결정 (승인 전에는 없음) */
  approvedAnalysis?: Omit<AnalysisDecision, 'action' | 'comment'>;
  design?: DesignReview;
  result?: RunResult;
}

export interface NewRunInput {
  url: string;
  alias: string;
  kind: RunKind;
}

/** SSE 이벤트. log는 줄 단위, 나머지는 스냅샷을 다시 받으라는 신호 */
export type RunEvent = { type: 'log'; line: LogLine } | { type: 'changed' };

// ── 질의 ─────────────────────────────

export type QueryAnswer =
  | {
      kind: 'answer';
      text: string;
      table?: { columns: string[]; rows: string[][] };
      sources: string[];
    }
  | { kind: 'rejected'; text: string }
  | {
      /** Router가 생성·확장 요청으로 분류: 새 요청 폼을 채울 값 */
      kind: 'start';
      text: string;
      start: { kind: RunKind; url?: string | null; alias?: string | null };
    };
