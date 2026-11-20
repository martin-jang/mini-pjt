import type { RunDetail, RunStatus, StageId } from '../api/types';

export const STAGE_LABEL: Record<StageId, string> = {
  explorer: '① 화면 수집',
  analyst: '② 분석',
  analysisReview: '승인 1 · 분석 리뷰',
  designer: '③ 디자인',
  designReview: '승인 2 · 디자인 확인',
  builder: '④ 코드 생성',
  verifier: '⑤ 검증',
};

export const STATUS_LABEL: Record<RunStatus, string> = {
  running: '진행 중',
  awaiting_analysis: '승인 대기',
  awaiting_design: '승인 대기',
  done: '완료',
  stopped: '중단',
  failed: '실패',
};

export function formatClock(iso: string): string {
  const d = new Date(iso);
  return [d.getHours(), d.getMinutes(), d.getSeconds()]
    .map((n) => String(n).padStart(2, '0'))
    .join(':');
}

export function formatDuration(ms: number): string {
  const sec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}시간 ${m}분`;
  if (m > 0) return `${m}분 ${s}초`;
  return `${s}초`;
}

/** 엔드투엔드·승인 대기·에이전트 처리 시간 */
export function runDurations(run: RunDetail, now: number) {
  const end = run.timing.finishedAt ? Date.parse(run.timing.finishedAt) : now;
  const total = end - Date.parse(run.timing.startedAt);
  const currentWait = run.timing.waitingSince ? end - Date.parse(run.timing.waitingSince) : 0;
  const wait = run.timing.waitMs + currentWait;
  return { total, wait, agent: total - wait };
}

export function isActive(status: RunStatus): boolean {
  return status === 'running' || status === 'awaiting_analysis' || status === 'awaiting_design';
}

/** 사이트 상태에 맞는 기본 화면 경로 */
export function siteHome(alias: string, status: RunStatus): string {
  if (status === 'awaiting_analysis') return `/sites/${alias}/analysis`;
  if (status === 'awaiting_design') return `/sites/${alias}/design`;
  if (status === 'done') return `/sites/${alias}/result`;
  return `/sites/${alias}`;
}
