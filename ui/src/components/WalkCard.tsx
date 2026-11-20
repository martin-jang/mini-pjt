import { useState } from 'react';
import type { WalkCandidateView, WalkStatus, WalkView } from '../api/types';
import { Card } from './Card';
import { Badge, type Tone } from './StatusBadge';

const STATUS: Record<WalkStatus, { label: string; tone: Tone }> = {
  completed: { label: '완주', tone: 'success' },
  partial: { label: '부분 완주', tone: 'waiting' },
  failed: { label: '완주 못 함', tone: 'error' },
  untried: { label: '시도 안 함', tone: 'pending' },
};

const FAIL_KIND: Record<string, string> = {
  no_data: '데이터 없음',
  needs_auth: '인증 필요',
  write_action: '쓰기 동작 미승인',
  not_found: '요소·화면 없음',
  step_limit: '단계 상한',
  other: '기타',
};

const KIND: Record<string, string> = {
  view: '조회→상세',
  search: '검색→결과',
  input: '입력→완료',
  other: '기타',
};

const ACTION: Record<string, string> = {
  click: '클릭',
  type: '입력',
  select: '선택',
  press_enter: 'Enter',
  navigate: '이동',
};

function CandidateRow({ c }: { c: WalkCandidateView }) {
  const [open, setOpen] = useState(false);
  const status = STATUS[c.status];
  return (
    <li className="border-t border-hairline" data-testid={`walk-${c.id}`} data-status={c.status}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[1fr_90px_80px_110px] items-center gap-3 px-5 py-3 text-left hover:bg-canvas-soft-2"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{c.name}</span>
          <span className="block truncate text-xs text-body">{c.goal}</span>
        </span>
        <span className="text-xs text-body">{KIND[c.kind] ?? c.kind}</span>
        <span className="text-right text-sm">{c.total} / 20</span>
        <span className="text-right">
          <Badge tone={status.tone} plain>
            {status.label}
          </Badge>
        </span>
      </button>
      {open && (
        <div className="space-y-2 px-5 pb-4 text-sm" data-testid={`walk-detail-${c.id}`}>
          <p className="text-xs text-body">
            고른 이유 · {c.reason} (메뉴 {c.score.menu ?? 0} · 완결성 {c.score.completeness ?? 0}
            {' · '}도메인 {c.score.domain ?? 0} · 재사용 {c.score.reuse ?? 0})
          </p>
          {c.steps.length > 0 && (
            <ol className="space-y-1">
              {c.steps.map((s) => (
                <li key={s.index} className="flex gap-2 text-[13px]">
                  <span className="w-5 shrink-0 text-mute">{s.index}</span>
                  <span>
                    {ACTION[s.action] ?? s.action}
                    {s.target && <span className="font-medium"> “{s.target}”</span>}
                    {s.value && <span className="text-body"> 값 “{s.value}”</span>}
                    <span className="text-body"> → {s.toTitle}</span>
                  </span>
                </li>
              ))}
            </ol>
          )}
          {c.status !== 'untried' && (
            <p className="text-[13px]">
              {c.status !== 'completed' && c.failKind && (
                <span className="font-medium text-error">
                  {FAIL_KIND[c.failKind] ?? c.failKind} ·{' '}
                </span>
              )}
              <span className="text-body">{c.result}</span>
            </p>
          )}
          {c.dataRecovery && (
            <p className="text-xs text-body" data-testid={`walk-recovery-${c.id}`}>
              빈 조회 결과 대응 ·{' '}
              {c.dataRecovery === 'found'
                ? '조건을 넓혀 다시 조회해 데이터를 찾음'
                : `조건을 넓혀도 비어 합성 데이터로 보완 (${c.fixture ?? '합성 못 함'})`}
            </p>
          )}
          {c.replayOk != null && (
            <p
              className={`text-xs ${c.replayOk ? 'text-success' : 'text-error'}`}
              data-testid={`walk-replay-${c.id}`}
            >
              재실행 스크립트(LLM 없이): {c.replayOk ? '재현됨' : '실패'} · {c.replayMessage}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

/** Hypothesize · Walk 결과: 사이트 성격 1차 추론, 유스케이스 후보와 완주 여부 */
export function WalkCard({ walk }: { walk: WalkView }) {
  const completed = walk.candidates.filter((c) => c.status === 'completed').length;
  const partial = walk.candidates.filter((c) => c.status === 'partial').length;
  const tried = walk.candidates.filter((c) => c.status !== 'untried').length;
  return (
    <Card
      title="유스케이스 · 흐름 걷기"
      className="mt-6"
      testId="walk"
      actions={
        <span className="text-xs text-body" data-testid="walk-summary">
          완주 {completed} · 부분 {partial} · 시도 {tried} · 후보 {walk.candidates.length}
        </span>
      }
      bodyClassName="p-0"
    >
      <div className="px-5 py-3 text-sm" data-testid="walk-site">
        <span className="text-body">사이트 성격(1차) · </span>
        <span className="font-medium">{walk.domain}</span>
        <span className="text-body"> · 사용자 {walk.users}</span>
        {walk.coreTasks.length > 0 && (
          <span className="text-body"> · 핵심 업무 {walk.coreTasks.join(', ')}</span>
        )}
      </div>
      <ul>
        {walk.candidates.map((c) => (
          <CandidateRow key={c.id} c={c} />
        ))}
      </ul>
    </Card>
  );
}
