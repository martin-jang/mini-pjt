import { useState } from 'react';
import { useNavigate } from 'react-router';
import { agentApi } from '../api/agentApi';
import type {
  AnalysisDecision,
  AnalysisReview,
  ReviewAction,
  RunDetail,
  VariantDecision,
} from '../api/types';
import { Button } from '../components/Button';
import { Callout } from '../components/Callout';
import { Card } from '../components/Card';
import { PageHeader } from '../components/PageHeader';
import { RunLoader } from '../components/RunLoader';
import { StatusBadge } from '../components/StatusBadge';

const VARIANT_OPTIONS: { value: VariantDecision; label: string }[] = [
  { value: 'unify', label: '공통 컴포넌트로 통일' },
  { value: 'prop', label: '공통 컴포넌트 + 변형 prop' },
  { value: 'hold', label: '따로 유지 (보류)' },
];

function initialDecision(
  run: RunDetail,
  analysis: AnalysisReview,
): Omit<AnalysisDecision, 'action'> {
  if (run.approvedAnalysis) return run.approvedAnalysis;
  return {
    happyPathIds: analysis.happyPaths.filter((p) => p.recommended).map((p) => p.id),
    dataMode: analysis.dataModes.find((m) => m.recommended)?.mode ?? 'mock',
    variantDecisions: Object.fromEntries(analysis.variants.map((v) => [v.id, v.decision])),
  };
}

/** 라디오·체크 카드: 선택은 1px ink 테두리, 미선택은 hairline */
const choiceClass = (selected: boolean, editable: boolean) =>
  `flex gap-3 rounded-md border p-4 ${selected ? 'border-ink shadow-select' : 'border-hairline'} ${
    editable ? 'cursor-pointer' : ''
  }`;

function AnalysisView({ run, analysis }: { run: RunDetail; analysis: AnalysisReview }) {
  const navigate = useNavigate();
  const editable = run.status === 'awaiting_analysis';
  const [draft, setDraft] = useState(() => initialDecision(run, analysis));
  const [comment, setComment] = useState('');
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);
  const { profile } = analysis;

  const submit = async (action: ReviewAction) => {
    setError(undefined);
    setNotice(undefined);
    setBusy(true);
    try {
      await agentApi.submitAnalysis(run.alias, {
        action,
        ...draft,
        comment: comment.trim() || undefined,
      });
      if (action === 'revise') {
        setNotice('수정 요청을 보냈습니다. 반영된 분석을 다시 확인하세요.');
        setComment('');
        setBusy(false);
      } else {
        navigate(`/sites/${run.alias}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '요청을 보내지 못했습니다.');
      setBusy(false);
    }
  };

  const toggleHappyPath = (id: string) =>
    setDraft((d) => ({
      ...d,
      happyPathIds: d.happyPathIds.includes(id)
        ? d.happyPathIds.filter((x) => x !== id)
        : [...d.happyPathIds, id],
    }));

  return (
    <div className="mx-auto max-w-[832px]">
      <PageHeader title={`분석 리뷰 · ${run.alias}`} badge={<StatusBadge status={run.status} />} />

      <div className="space-y-8">
        <Callout tone={editable ? 'waiting' : 'pending'}>
          {editable
            ? '분석 결과를 확인해 주세요. 승인하면 디자인 단계로 넘어갑니다.'
            : '이미 처리된 분석입니다. 승인된 내용을 읽기 전용으로 보여줍니다.'}
        </Callout>

        <Card title="사이트 성격" bodyClassName="px-6 py-2" testId="site-profile">
          <dl className="divide-y divide-hairline">
            {[
              { label: '업무 도메인', value: profile.domain },
              { label: '주요 사용자', value: profile.users },
              { label: '핵심 업무', value: profile.coreTasks },
            ].map((item) => (
              <div key={item.label} className="grid grid-cols-[120px_1fr] py-3">
                <dt className="text-mute">{item.label}</dt>
                <dd>{item.value}</dd>
              </div>
            ))}
            <div className="py-3">
              <dt className="text-mute">근거</dt>
              <dd className="mt-1.5 text-body">{profile.summary}</dd>
              <dd className="mt-2 flex flex-wrap gap-1.5">
                {profile.evidence.map((e) => (
                  <span key={e.path} className="rounded-md bg-canvas-soft-2 px-2 py-0.5 text-xs">
                    {e.screen} <span className="font-mono text-mute">{e.path}</span>
                  </span>
                ))}
              </dd>
            </div>
          </dl>
        </Card>

        <Card
          title="Happy Path"
          description="POC로 먼저 만들 흐름을 고르세요. 나머지는 확장 요청으로 이어 붙일 수 있습니다."
          actions={
            <span className="text-xs text-mute">
              {draft.happyPathIds.length} / {analysis.happyPaths.length} 선택
            </span>
          }
          bodyClassName="space-y-3 p-6"
          testId="happy-paths"
        >
          {analysis.happyPaths.map((p) => {
            const checked = draft.happyPathIds.includes(p.id);
            return (
              <label key={p.id} className={choiceClass(checked, editable)}>
                <input
                  type="checkbox"
                  className="mt-1 accent-ink"
                  checked={checked}
                  disabled={!editable}
                  onChange={() => toggleHappyPath(p.id)}
                  data-testid={`happy-path-${p.id}`}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="font-medium">{p.title}</span>
                    {p.recommended && <span className="ml-auto text-xs text-mute">추천</span>}
                  </span>
                  <span className="mt-2 flex flex-wrap items-center gap-1.5">
                    {p.steps.map((step, i) => (
                      <span key={step} className="flex items-center gap-1.5">
                        {i > 0 && <span className="text-mute">→</span>}
                        <span className="rounded-md border border-hairline px-2 py-0.5 text-xs">
                          {step}
                        </span>
                      </span>
                    ))}
                  </span>
                  <span className={`mt-2 block text-[13px] ${checked ? 'text-body' : 'text-mute'}`}>
                    {p.reason}
                  </span>
                </span>
              </label>
            );
          })}
        </Card>

        <Card title="데이터 연결 방식" testId="data-modes">
          <div className="grid grid-cols-2 gap-4">
            {analysis.dataModes.map((m) => {
              const selected = draft.dataMode === m.mode;
              return (
                <label key={m.mode} className={choiceClass(selected, editable)}>
                  <input
                    type="radio"
                    name="dataMode"
                    className="mt-1 accent-ink"
                    checked={selected}
                    disabled={!editable}
                    onChange={() => setDraft((d) => ({ ...d, dataMode: m.mode }))}
                    data-testid={`data-mode-${m.mode}`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="font-medium">{m.title}</span>
                      {m.recommended && <span className="ml-auto text-xs text-mute">추천</span>}
                    </span>
                    <span
                      className={`mt-1 block text-[13px] ${selected ? 'text-body' : 'text-mute'}`}
                    >
                      {m.summary}
                    </span>
                    <ul
                      className={`mt-2 list-disc space-y-1 pl-4 text-[13px] ${selected ? 'text-body' : 'text-mute'}`}
                    >
                      {m.reasons.map((r) => (
                        <li key={r}>{r}</li>
                      ))}
                    </ul>
                    {m.caveat && (
                      <span className="mt-2 block text-[13px] text-error">{m.caveat}</span>
                    )}
                  </span>
                </label>
              );
            })}
          </div>
        </Card>

        <Card title="변이 통일" bodyClassName="px-6 py-2" testId="variants">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-mute">
              <tr>
                <th className="py-3 font-normal">후보</th>
                <th className="py-3 font-normal whitespace-nowrap">발견 화면</th>
                <th className="py-3 font-normal">판단</th>
                <th className="py-3 font-normal">근거</th>
              </tr>
            </thead>
            <tbody>
              {analysis.variants.map((v) => (
                <tr key={v.id} className="border-t border-hairline align-top">
                  <td className="py-3 pr-4">
                    <p>{v.name}</p>
                    <p className="mt-0.5 font-mono text-xs text-mute">{v.selectors.join(', ')}</p>
                  </td>
                  <td className="py-3 pr-4 whitespace-nowrap">{v.screenCount}개</td>
                  <td className="py-3 pr-4">
                    <select
                      className="h-8 rounded-md border border-hairline bg-canvas px-2 text-sm focus:border-ink focus:outline-none"
                      value={draft.variantDecisions[v.id] ?? v.decision}
                      disabled={!editable}
                      onChange={(e) =>
                        setDraft((d) => ({
                          ...d,
                          variantDecisions: {
                            ...d.variantDecisions,
                            [v.id]: e.target.value as VariantDecision,
                          },
                        }))
                      }
                      data-testid={`variant-${v.id}`}
                    >
                      {VARIANT_OPTIONS.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-3 text-body">{v.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        {editable && (
          <section className="space-y-3">
            {error && (
              <Callout tone="error" testId="analysis-error">
                {error}
              </Callout>
            )}
            {notice && (
              <Callout tone="success" testId="analysis-notice">
                {notice}
              </Callout>
            )}
            <div className="rounded-lg border border-hairline bg-canvas p-4">
              <textarea
                className="h-20 w-full resize-none rounded-md border border-hairline bg-canvas p-3 text-sm placeholder:text-mute focus:border-ink focus:outline-none"
                placeholder="수정 요청·반려 시 이유를 적어 주세요. 예: 휴가 신청 대신 근태 조회 흐름을 먼저 만들어 주세요"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                data-testid="analysis-comment"
              />
              <div className="mt-3 flex items-center gap-2">
                <p className="flex-1 text-xs text-mute">
                  승인 후 바꾸려면 처음부터 다시 실행해야 합니다.
                </p>
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() => void submit('reject')}
                  data-testid="analysis-reject"
                >
                  반려
                </Button>
                <Button
                  disabled={busy}
                  onClick={() => void submit('revise')}
                  data-testid="analysis-revise"
                >
                  수정 요청
                </Button>
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() => void submit('approve')}
                  data-testid="analysis-approve"
                >
                  승인하고 디자인 시작
                </Button>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}

export function AnalysisReviewPage() {
  return (
    <RunLoader>
      {(run) =>
        run.analysis ? (
          <AnalysisView run={run} analysis={run.analysis} />
        ) : (
          <Callout title="아직 분석 중입니다">
            분석이 끝나면 이 화면에서 결과를 확인할 수 있습니다.
          </Callout>
        )
      }
    </RunLoader>
  );
}
