import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { agentApi } from '../api/agentApi';
import type {
  AuthRequest,
  GuardrailOutcome,
  LoginKind,
  LogLevel,
  RunDetail,
  StageInfo,
} from '../api/types';
import { Button } from '../components/Button';
import { Callout } from '../components/Callout';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { PageHeader } from '../components/PageHeader';
import { RunLoader } from '../components/RunLoader';
import { SiteMapCard } from '../components/SiteMapCard';
import { WalkCard } from '../components/WalkCard';
import { Badge, StatusBadge, type Tone } from '../components/StatusBadge';
import { useNow } from '../hooks/useNow';
import { formatClock, formatDuration, isActive, runDurations, STAGE_LABEL } from '../lib/format';

const OUTCOME: Record<GuardrailOutcome, { label: string; tone: Tone }> = {
  masked: { label: '마스킹됨', tone: 'success' },
  blocked: { label: '차단됨', tone: 'error' },
  skipped: { label: '건너뜀', tone: 'waiting' },
  approved: { label: '통과', tone: 'success' },
};

const LOG_LINE_CLASS: Record<LogLevel, string> = {
  info: 'border-l-transparent',
  warn: 'border-l-warning',
  block: 'border-l-error',
};

const STAGE_STATE_LABEL: Record<StageInfo['state'], string> = {
  pending: '대기',
  running: '진행 중',
  waiting: '승인 대기',
  done: '완료',
  stopped: '중단',
};

function StageIcon({ stage }: { stage: StageInfo }) {
  switch (stage.state) {
    case 'done':
      return <Icon name="check" className="text-success" />;
    case 'running':
      return <Icon name="progress_activity" className="animate-spin-slow text-running" />;
    case 'waiting':
      return <Icon name="pause_circle" className="text-warning" />;
    case 'stopped':
      return <Icon name="block" className="text-error" />;
    default:
      return <Icon name="radio_button_unchecked" className="text-pending" />;
  }
}

function Stepper({ run }: { run: RunDetail }) {
  return (
    <ol className="space-y-1" data-testid="stage-list">
      {run.stages.map((s) => (
        <li
          key={s.id}
          data-testid={`stage-${s.id}`}
          data-state={s.state}
          className={`flex items-center gap-3 rounded-md px-3 py-2.5 ${
            s.state === 'running'
              ? 'bg-running-soft'
              : s.state === 'waiting'
                ? 'bg-warning-soft'
                : ''
          }`}
        >
          <StageIcon stage={s} />
          <span className={`flex-1 text-sm ${s.state === 'pending' ? 'text-mute' : 'text-ink'}`}>
            {STAGE_LABEL[s.id]}
          </span>
          <span className="text-xs text-body">{s.note ?? STAGE_STATE_LABEL[s.state]}</span>
        </li>
      ))}
    </ol>
  );
}

function LogViewer({ run }: { run: RunDetail }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [run.logs.length]);
  return (
    <div
      ref={ref}
      data-testid="log-viewer"
      className="h-[420px] overflow-y-auto rounded-md bg-ink py-3 font-mono text-[13px] leading-6 text-log"
    >
      {run.logs.map((line, i) => (
        <div key={i} className={`flex gap-3 border-l-2 px-4 ${LOG_LINE_CLASS[line.level]}`}>
          <span className="shrink-0 text-mute">{formatClock(line.at)}</span>
          <span className="w-[96px] shrink-0 text-mute">[{line.source}]</span>
          <span className="min-w-0">{line.message}</span>
        </div>
      ))}
    </div>
  );
}

const NEXT_ACTION: Partial<
  Record<
    RunDetail['status'],
    { title: string; body?: string; to: string; label: string; testId: string }
  >
> = {
  awaiting_analysis: {
    title: '분석 리뷰 승인이 필요합니다',
    body: '사이트 성격, Happy Path, 데이터 연결 방식, 변이 통일 결과를 확인하세요.',
    to: 'analysis',
    label: '분석 리뷰 열기',
    testId: 'go-analysis-review',
  },
  awaiting_design: {
    title: '디자인 확인 승인이 필요합니다',
    body: '레이아웃이 크게 바뀐 화면은 따로 승인해야 합니다.',
    to: 'design',
    label: '디자인 확인 열기',
    testId: 'go-design-review',
  },
  done: { title: 'POC 생성이 끝났습니다', to: 'result', label: '결과 보기', testId: 'go-result' },
};

const LOGIN_KIND_LABEL: Record<LoginKind, string> = {
  none: '로그인 없음',
  id_pw: '아이디·비밀번호',
  certificate: '공동·공인인증서',
  simple_auth: '간편인증',
  unknown: '판단 어려움',
};

/** 사용자 인증 넘김: 에이전트가 띄운 브라우저 창에서 사용자가 인증하고 완료를 알린다 */
function AuthCard({ run, auth }: { run: RunDetail; auth: AuthRequest }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const done = async () => {
    setBusy(true);
    setError(null);
    try {
      await agentApi.submitAuth(run.alias, { action: 'done' });
    } catch (e) {
      setError(e instanceof Error ? e.message : '요청을 보내지 못했습니다.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Callout
      tone="waiting"
      icon="key"
      title="브라우저에서 인증을 완료해 주세요"
      testId="auth-card"
      actions={
        <Button
          variant="primary"
          icon="check"
          disabled={busy}
          onClick={() => void done()}
          data-testid="auth-done"
        >
          인증 완료
        </Button>
      }
    >
      <p data-testid="auth-reason">
        {auth.reason} · {LOGIN_KIND_LABEL[auth.loginKind]}
      </p>
      <p className="mt-1">
        에이전트가 띄운 브라우저 창(<span className="font-mono text-xs">{auth.url}</span>)에서
        로그인이나 휴대폰 승인을 마친 뒤 인증 완료를 누르세요. 인증하는 동안 에이전트는 브라우저를
        조작하지 않습니다.
      </p>
      {error && (
        <p className="mt-1 text-error" role="alert">
          {error}
        </p>
      )}
    </Callout>
  );
}

function ProgressView({ run }: { run: RunDetail }) {
  const navigate = useNavigate();
  const active = isActive(run.status);
  const now = useNow(active);
  const { total, wait } = runDurations(run, now);
  const current = run.stages.find((s) => s.state === 'running' || s.state === 'waiting');
  const next = NEXT_ACTION[run.status];

  const metrics = [
    {
      label: '현재 단계',
      value: current ? STAGE_LABEL[current.id] : run.status === 'done' ? '완료' : '중단',
    },
    { label: '수집 화면', value: `${run.metrics.screensCollected}개` },
    {
      label: '경과 시간',
      value: formatDuration(total),
      sub: wait > 0 ? `승인 대기 ${formatDuration(wait)} 포함` : undefined,
    },
    { label: 'LLM 호출', value: `${run.metrics.llmCalls} / ${run.metrics.llmLimit}` },
  ];

  return (
    <>
      <PageHeader
        title={run.alias}
        badge={<StatusBadge status={run.status} testId="run-status" />}
        subtitle={<span className="font-mono text-xs">{run.url}</span>}
        actions={
          active && (
            <Button
              variant="danger"
              icon="stop_circle"
              onClick={() => void agentApi.stopRun(run.alias)}
              data-testid="stop-run"
            >
              실행 중단
            </Button>
          )
        }
      />

      {run.status === 'awaiting_auth' && run.auth && (
        <div className="mb-6">
          <AuthCard run={run} auth={run.auth} />
        </div>
      )}

      {next && (
        <div className="mb-6">
          <Callout
            tone={run.status === 'done' ? 'success' : 'waiting'}
            icon={run.status === 'done' ? 'task_alt' : 'pending_actions'}
            title={next.title}
            actions={
              <Button
                variant="primary"
                iconAfter="arrow_forward"
                data-testid={next.testId}
                onClick={() => navigate(`/sites/${run.alias}/${next.to}`)}
              >
                {next.label}
              </Button>
            }
          >
            {next.body}
          </Callout>
        </div>
      )}

      <div
        className="mb-8 grid grid-cols-4 divide-x divide-hairline rounded-lg border border-hairline bg-canvas"
        data-testid="run-metrics"
      >
        {metrics.map((m) => (
          <div key={m.label} className="px-5 py-4">
            <p className="text-xs text-body">{m.label}</p>
            <p className="mt-1 text-base font-semibold">{m.value}</p>
            {m.sub && <p className="mt-0.5 text-xs text-mute">{m.sub}</p>}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[320px_1fr] gap-6">
        <Card title="단계" bodyClassName="p-3">
          <Stepper run={run} />
        </Card>
        <Card
          title="실행 로그"
          actions={
            active && (
              <Badge tone="running" plain>
                실시간
              </Badge>
            )
          }
          bodyClassName="p-4"
        >
          <LogViewer run={run} />
        </Card>
      </div>

      {run.sitemap && <SiteMapCard sitemap={run.sitemap} />}
      {run.walk && <WalkCard walk={run.walk} />}

      <Card
        title="가드레일 이벤트"
        className="mt-6"
        bodyClassName="px-5 pb-2"
        testId="guardrail-events"
      >
        {run.guardrails.length === 0 ? (
          <p className="py-4 text-sm text-body">아직 이벤트가 없습니다.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-body">
                <th className="py-3 font-normal">시각</th>
                <th className="py-3 font-normal">규칙</th>
                <th className="py-3 font-normal">내용</th>
                <th className="py-3 text-right font-normal">처리</th>
              </tr>
            </thead>
            <tbody>
              {run.guardrails.map((g, i) => (
                <tr key={i} className="border-t border-hairline">
                  <td className="w-28 py-3 font-mono text-xs text-body">{formatClock(g.at)}</td>
                  <td className="w-20 py-3 font-mono text-xs">{g.rule}</td>
                  <td className="py-3">{g.detail}</td>
                  <td className="py-3 text-right">
                    <Badge tone={OUTCOME[g.outcome].tone} plain>
                      {OUTCOME[g.outcome].label}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}

export function ProgressPage() {
  return <RunLoader>{(run) => <ProgressView run={run} />}</RunLoader>;
}
