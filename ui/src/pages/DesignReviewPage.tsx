import { useState } from 'react';
import { useNavigate } from 'react-router';
import { agentApi } from '../api/agentApi';
import type {
  DesignDecision,
  DesignReview,
  DesignScreen,
  LayoutSketch,
  RunDetail,
  ScreenReviewState,
} from '../api/types';
import { Button } from '../components/Button';
import { Callout } from '../components/Callout';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { PageHeader } from '../components/PageHeader';
import { RunLoader } from '../components/RunLoader';
import { Badge, StatusBadge, type Tone } from '../components/StatusBadge';

const SCREEN_STATE: Record<ScreenReviewState, { label: string; tone: Tone }> = {
  pending: { label: '승인 대기', tone: 'waiting' },
  approved: { label: '승인 완료', tone: 'success' },
  revise: { label: '수정 중', tone: 'running' },
};

/** 레이아웃 비교 도식: 메뉴 위치와 영역 배치만 보여준다 */
function Sketch({
  sketch,
  label,
  testId,
}: {
  sketch: LayoutSketch;
  label: string;
  testId: string;
}) {
  return (
    <figure className="flex-1" data-testid={testId}>
      <figcaption className="mb-2 text-xs font-medium text-body">{label}</figcaption>
      <div className="flex h-56 flex-col overflow-hidden rounded-md border border-hairline bg-canvas-soft-2">
        {sketch.nav === 'top' && (
          <div className="h-6 shrink-0 border-b border-hairline bg-canvas" />
        )}
        <div className="flex min-h-0 flex-1">
          {sketch.nav === 'left' && (
            <div className="w-14 shrink-0 border-r border-hairline bg-canvas" />
          )}
          <div className="flex flex-1 flex-col gap-2 p-3">
            {sketch.blocks.map((b) => (
              <div
                key={b}
                className="flex flex-1 items-center justify-center rounded-md border border-dashed border-pending bg-canvas px-2 text-center text-xs text-body"
              >
                {b}
              </div>
            ))}
          </div>
        </div>
      </div>
    </figure>
  );
}

function ScreenDetail({
  run,
  screen,
  editable,
  onDecide,
  busy,
}: {
  run: RunDetail;
  screen: DesignScreen;
  editable: boolean;
  onDecide: (d: DesignDecision) => Promise<boolean>;
  busy: boolean;
}) {
  const [comment, setComment] = useState('');
  const canAct = editable && screen.state === 'pending';
  return (
    <div className="space-y-4" data-testid="screen-detail">
      {screen.majorChange && (
        <Callout
          tone="waiting"
          icon="change_circle"
          title="레이아웃이 크게 바뀐 화면입니다"
          testId="major-change-notice"
        >
          일괄 승인에 포함되지 않습니다. 레거시와 TOBE 배치를 비교한 뒤 이 화면을 따로 승인하세요.
        </Callout>
      )}
      <Card
        title={
          <span className="flex items-center gap-2">
            {screen.name}
            <span className="font-mono text-xs font-normal text-body">{screen.path}</span>
          </span>
        }
        actions={
          <Badge tone={SCREEN_STATE[screen.state].tone}>{SCREEN_STATE[screen.state].label}</Badge>
        }
      >
        <div className="flex gap-4">
          <Sketch sketch={screen.asis} label="ASIS · 레거시 (마스킹본 기준)" testId="sketch-asis" />
          <Sketch sketch={screen.tobe} label={`TOBE · ${run.alias} 디자인`} testId="sketch-tobe" />
        </div>
        <h3 className="mt-6 text-sm font-semibold">바뀐 점과 이유</h3>
        <ol className="mt-2 divide-y divide-hairline" data-testid="screen-changes">
          {screen.changes.map((c, i) => (
            <li key={c.what} className="grid grid-cols-[20px_1fr] gap-x-2 py-3">
              <span className="text-xs leading-5 text-mute">{i + 1}</span>
              <p className="text-sm font-medium">{c.what}</p>
              {c.why && (
                <p className="col-start-2 mt-1 text-[13px] text-body" data-testid="change-why">
                  <span className="text-mute">이유 · </span>
                  {c.why}
                </p>
              )}
            </li>
          ))}
        </ol>
      </Card>
      {canAct && (
        <div className="flex items-center gap-2 rounded-md border border-hairline bg-canvas p-3">
          <input
            className="h-9 min-w-0 flex-1 rounded-md border border-hairline bg-canvas px-3 text-sm placeholder:text-mute focus:border-running focus:outline-none"
            placeholder="수정이 필요하면 의견을 적으세요 (예: 신청 버튼을 왼쪽에 유지)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            data-testid="screen-comment"
          />
          <Button
            icon="rate_review"
            disabled={busy}
            data-testid="screen-revise"
            onClick={() =>
              void onDecide({
                action: 'revise',
                screenId: screen.id,
                comment: comment.trim(),
              }).then((ok) => {
                if (ok) setComment('');
              })
            }
          >
            수정 요청
          </Button>
          <Button
            variant="primary"
            icon="check"
            disabled={busy}
            data-testid="screen-approve"
            onClick={() => void onDecide({ action: 'approveScreen', screenId: screen.id })}
          >
            이 화면 승인
          </Button>
        </div>
      )}
    </div>
  );
}

function DesignView({ run, design }: { run: RunDetail; design: DesignReview }) {
  const navigate = useNavigate();
  const editable = run.status === 'awaiting_design';
  const [selectedId, setSelectedId] = useState(
    () => (design.screens.find((s) => s.majorChange) ?? design.screens[0])?.id,
  );
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const approved = design.screens.filter((s) => s.state === 'approved').length;
  const pendingRegular = design.screens.filter(
    (s) => !s.majorChange && s.state === 'pending',
  ).length;
  const selected = design.screens.find((s) => s.id === selectedId) ?? design.screens[0];

  const decide = async (decision: DesignDecision): Promise<boolean> => {
    setError(undefined);
    setBusy(true);
    try {
      await agentApi.submitDesign(run.alias, decision);
      setBusy(false);
      const remaining = design.screens.filter(
        (s) =>
          s.state !== 'approved' &&
          !(decision.action === 'approveScreen' && s.id === decision.screenId) &&
          !(decision.action === 'approveRegular' && !s.majorChange && s.state === 'pending'),
      );
      if (decision.action === 'rejectAll' || remaining.length === 0)
        navigate(`/sites/${run.alias}`);
      else if (decision.action === 'approveScreen') {
        setSelectedId(remaining.find((s) => s.state === 'pending')?.id ?? selectedId);
      }
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : '요청을 보내지 못했습니다.');
      setBusy(false);
      return false;
    }
  };

  return (
    <>
      <PageHeader
        title={`디자인 확인 · ${run.alias}`}
        badge={<StatusBadge status={run.status} />}
        subtitle={
          <span data-testid="design-progress">
            승인 {approved} / {design.screens.length} 화면 · 디자인 시스템: {design.designSystem}
          </span>
        }
        actions={
          editable && (
            <>
              <Button
                variant="danger"
                icon="close"
                disabled={busy}
                onClick={() => void decide({ action: 'rejectAll' })}
                data-testid="design-reject-all"
              >
                전체 반려
              </Button>
              <Button
                variant="secondary"
                icon="done_all"
                disabled={busy || pendingRegular === 0}
                onClick={() => void decide({ action: 'approveRegular' })}
                data-testid="design-approve-regular"
              >
                일반 화면 일괄 승인 ({pendingRegular})
              </Button>
            </>
          )
        }
      />
      {error && (
        <div className="mb-6">
          <Callout tone="error" icon="error" testId="design-error">
            {error}
          </Callout>
        </div>
      )}
      <div className="grid grid-cols-[280px_1fr] items-start gap-6">
        <Card title="검토 대상 화면" bodyClassName="p-2">
          <ul className="space-y-1" data-testid="design-screen-list">
            {design.screens.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(s.id)}
                  data-testid={`design-screen-${s.id}`}
                  data-state={s.state}
                  className={`relative w-full rounded-md px-3 py-2.5 text-left ${
                    s.id === selected?.id ? 'bg-canvas-soft-2' : 'hover:bg-canvas-soft-2'
                  }`}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium">{s.name}</span>
                    <Badge tone={SCREEN_STATE[s.state].tone} plain>
                      {SCREEN_STATE[s.state].label}
                    </Badge>
                  </span>
                  <span className="mt-0.5 block font-mono text-xs text-body">{s.path}</span>
                  {s.majorChange && (
                    <span className="mt-1.5 flex items-center gap-1 text-xs text-body">
                      <Icon name="change_circle" className="text-[14px] text-warning" />
                      대폭 변경 · 개별 승인
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </Card>
        {selected && (
          <ScreenDetail
            key={selected.id}
            run={run}
            screen={selected}
            editable={editable}
            onDecide={decide}
            busy={busy}
          />
        )}
      </div>
    </>
  );
}

export function DesignReviewPage() {
  return (
    <RunLoader>
      {(run) =>
        run.design &&
        run.design.screens.length > 0 &&
        run.stages.some((s) => s.id === 'designReview' && s.state !== 'pending') ? (
          <DesignView run={run} design={run.design} />
        ) : (
          <Callout icon="hourglass_empty" title="아직 디자인을 만드는 중입니다">
            디자인이 끝나면 이 화면에서 레거시와 비교해 확인할 수 있습니다.
          </Callout>
        )
      }
    </RunLoader>
  );
}
