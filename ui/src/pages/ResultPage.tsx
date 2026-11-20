import { useState } from 'react';
import { useNavigate } from 'react-router';
import { agentApi } from '../api/agentApi';
import type { RunDetail, RunResult } from '../api/types';
import { Button } from '../components/Button';
import { Callout } from '../components/Callout';
import { Card } from '../components/Card';
import { Icon } from '../components/Icon';
import { PageHeader } from '../components/PageHeader';
import { RunLoader } from '../components/RunLoader';
import { Badge, StatusBadge } from '../components/StatusBadge';
import { useNow } from '../hooks/useNow';
import { formatDuration, runDurations } from '../lib/format';

/** 저장된 로그인 세션은 비밀값처럼 다룬다. 더 수집하지 않으면 지우도록 권한다 (G10) */
function SessionNotice({ alias }: { alias: string }) {
  const [busy, setBusy] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await agentApi.deleteSession(alias);
      // 삭제 이벤트는 로그로만 오므로 스냅샷을 다시 받지 않는다. 성공하면 바로 숨긴다
      setDeleted(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : '세션을 지우지 못했습니다.');
      setBusy(false);
    }
  };

  if (deleted) return null;

  return (
    <div className="mb-6">
      <Callout
        tone="pending"
        icon="cookie"
        title="로그인 세션이 저장되어 있습니다"
        testId="session-notice"
        actions={
          <Button
            variant="danger"
            icon="delete"
            disabled={busy}
            onClick={() => void remove()}
            data-testid="delete-session"
          >
            세션 삭제
          </Button>
        }
      >
        확장 요청으로 화면을 더 수집하지 않을 거면 삭제하세요. 세션 파일은 생성 결과물과 분리된 git
        제외 폴더에 있습니다.
        {error && (
          <span className="mt-1 block text-error" role="alert">
            {error}
          </span>
        )}
      </Callout>
    </div>
  );
}

function ResultView({ run, result }: { run: RunDetail; result: RunResult }) {
  const navigate = useNavigate();
  const now = useNow(false);
  const { total, wait, agent } = runDurations(run, now);
  const passed = result.verification.filter((v) => v.passed).length;
  const preserved = result.screens.reduce((n, s) => n + s.preserved, 0);
  const fields = result.screens.reduce((n, s) => n + s.total, 0);
  const remaining = result.totalScreens - result.screens.length;

  const metrics = [
    {
      label: '생성 화면',
      value: `${result.screens.length} / ${result.totalScreens}개`,
      sub: '수집 화면 중',
    },
    { label: '공통 컴포넌트', value: `${result.components.length}개`, sub: '화면 간 재사용' },
    { label: '기능 보존', value: `${preserved} / ${fields}`, sub: '입력·버튼·조회 항목' },
    {
      label: '검증',
      value: `${passed} / ${result.verification.length} 통과`,
      sub: '빌드·흐름·보존·가드레일',
    },
  ];

  return (
    <>
      <PageHeader
        title={`결과 · ${run.alias}`}
        badge={<StatusBadge status={run.status} />}
        subtitle={
          <span className="flex items-center gap-1.5" data-testid="result-timing">
            <Icon name="schedule" className="text-[16px]" />
            엔드투엔드 {formatDuration(total)} (에이전트 {formatDuration(agent)} · 승인 대기{' '}
            {formatDuration(wait)})
          </span>
        }
        actions={
          <>
            <Button
              icon="add_circle"
              data-testid="request-extend"
              onClick={() =>
                navigate(`/new?extend=${run.alias}&url=${encodeURIComponent(run.url)}`)
              }
            >
              확장 요청
            </Button>
            <a href={result.previewUrl} target="_blank" rel="noreferrer" data-testid="open-poc">
              <Button variant="primary" iconAfter="open_in_new">
                POC 실행 열기
              </Button>
            </a>
          </>
        }
      />

      {run.sessionSaved && <SessionNotice alias={run.alias} />}

      <div className="mb-6 grid grid-cols-4 gap-4" data-testid="result-metrics">
        {metrics.map((m) => (
          <div key={m.label} className="rounded-md border border-hairline bg-canvas px-5 py-4">
            <p className="text-xs text-body">{m.label}</p>
            <p className="mt-1 text-xl font-semibold">{m.value}</p>
            <p className="mt-0.5 text-xs text-mute">{m.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-[1fr_340px] items-start gap-6">
        <Card
          title={`생성된 화면 (${result.screens.length})`}
          actions={<span className="font-mono text-xs text-body">src/pages/</span>}
          bodyClassName="p-0"
          testId="generated-screens"
        >
          <table className="w-full text-sm">
            <thead className="bg-canvas-soft-2 text-left text-xs text-body">
              <tr>
                <th className="px-5 py-2.5 font-normal">화면</th>
                <th className="px-5 py-2.5 font-normal">Happy Path</th>
                <th className="px-5 py-2.5 font-normal">기능 보존</th>
                <th className="px-5 py-2.5 text-right font-normal">상태</th>
              </tr>
            </thead>
            <tbody>
              {result.screens.map((s) => (
                <tr key={s.path} className="border-t border-hairline">
                  <td className="px-5 py-3">
                    <p className="font-medium">{s.name}</p>
                    <p className="font-mono text-xs text-body">{s.path}</p>
                  </td>
                  <td className="px-5 py-3 text-body">{s.happyPath ?? '—'}</td>
                  <td className="px-5 py-3 font-mono text-xs">
                    {s.preserved} / {s.total}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <Badge tone={s.preserved === s.total ? 'success' : 'waiting'} plain>
                      {s.preserved === s.total ? '생성됨' : '항목 확인 필요'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {remaining > 0 && (
            <div className="border-t border-hairline p-4">
              <Callout icon="info">
                남은 화면 {remaining}개는 확장 요청으로 이어서 만들 수 있습니다.
              </Callout>
            </div>
          )}
        </Card>

        <div className="space-y-6">
          <Card title="결과물 위치">
            <code
              className="block rounded-md border border-hairline bg-canvas-soft-2 px-3 py-2 font-mono text-sm"
              data-testid="output-dir"
            >
              {result.outputDir}
            </code>
            <p className="mt-2 text-xs text-body">
              실행:{' '}
              <code className="font-mono">
                npm run dev --prefix {result.outputDir.replace(/\/$/, '')}
              </code>
            </p>
          </Card>
          <Card
            title="공통 컴포넌트"
            actions={<span className="font-mono text-xs text-body">src/components/</span>}
          >
            <div className="flex flex-wrap gap-1.5">
              {result.components.map((c) => (
                <span
                  key={c}
                  className="rounded-md border border-hairline bg-canvas-soft-2 px-2 py-0.5 font-mono text-xs"
                >
                  {c}
                </span>
              ))}
            </div>
          </Card>
          <Card title="승인된 결정" bodyClassName="divide-y divide-hairline px-5">
            {result.decisions.map((d) => (
              <div key={d.label} className="py-3">
                <p className="text-xs text-body">{d.label}</p>
                <p className="mt-0.5 text-sm">{d.value}</p>
              </div>
            ))}
          </Card>
        </div>
      </div>

      <Card
        title="검증 결과"
        actions={
          <Badge
            tone={passed === result.verification.length ? 'success' : 'error'}
          >{`${passed} / ${result.verification.length} 통과`}</Badge>
        }
        className="mt-6"
        bodyClassName="divide-y divide-hairline px-5"
        testId="verification"
      >
        {result.verification.map((v) => (
          <div key={v.id} className="flex items-center gap-3 py-3">
            <Icon
              name={v.passed ? 'check_circle' : 'cancel'}
              className={v.passed ? 'text-success' : 'text-error'}
            />
            <div className="flex-1">
              <p className="text-sm font-medium">{v.label}</p>
              <p className="text-xs text-body">{v.detail}</p>
            </div>
            <Badge tone={v.passed ? 'success' : 'error'} plain>
              {v.passed ? '통과' : '실패'}
            </Badge>
          </div>
        ))}
      </Card>
    </>
  );
}

export function ResultPage() {
  return (
    <RunLoader>
      {(run) =>
        run.result ? (
          <ResultView run={run} result={run.result} />
        ) : (
          <Callout icon="hourglass_empty" title="아직 결과가 없습니다">
            코드 생성과 검증이 끝나면 이 화면에서 결과를 볼 수 있습니다.
          </Callout>
        )
      }
    </RunLoader>
  );
}
