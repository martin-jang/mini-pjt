import { useState, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { agentApi } from '../api/agentApi';
import type { RunKind } from '../api/types';
import { Button } from '../components/Button';
import { Callout } from '../components/Callout';
import { Dot } from '../components/StatusBadge';
import { PageHeader } from '../components/PageHeader';

const KINDS: { kind: RunKind; title: string; description: string }[] = [
  {
    kind: 'new',
    title: '신규 생성',
    description: '사이트를 분석해 Happy Path 화면으로 새 POC를 만듭니다.',
  },
  {
    kind: 'extend',
    title: '기존 결과물 확장',
    description: '이미 만든 POC에 남은 화면을 이어 붙입니다.',
  },
];

const PROCESS = [
  { label: '화면 수집' },
  { label: '분석', approval: true },
  { label: '디자인', approval: true },
  { label: '코드 생성' },
  { label: '검증' },
];

const inputClass =
  'h-10 w-full rounded-md border border-hairline bg-canvas px-3 text-sm text-ink placeholder:text-mute focus:border-running focus:outline-none';

export function NewRequestPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const extendAlias = params.get('extend');
  const [url, setUrl] = useState(params.get('url') ?? '');
  const [alias, setAlias] = useState(extendAlias ?? '');
  const [kind, setKind] = useState<RunKind>(extendAlias ? 'extend' : 'new');
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(undefined);
    setSubmitting(true);
    try {
      const run = await agentApi.createRun({ url: url.trim(), alias: alias.trim(), kind });
      navigate(`/sites/${run.alias}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '요청을 보내지 못했습니다.');
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[720px]">
      <PageHeader
        title="새 요청"
        subtitle="레거시 시스템 URL을 입력하면 화면 수집부터 React POC 생성까지 진행합니다. 승인이 필요한 두 단계에서 멈춥니다."
      />
      <form
        onSubmit={onSubmit}
        className="rounded-md border border-hairline bg-canvas p-6"
        data-testid="new-request-form"
      >
        <div className="space-y-6">
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">레거시 URL</span>
            <input
              data-testid="input-url"
              className={`${inputClass} font-mono`}
              placeholder="https://legacy.example.com"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
            />
            <span className="mt-1.5 block text-xs text-body">
              이 주소의 origin 안에서만 화면을 수집합니다.
            </span>
          </label>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium">사이트 별칭</span>
            <input
              data-testid="input-alias"
              className={inputClass}
              placeholder="예: hr-portal"
              value={alias}
              onChange={(e) => setAlias(e.target.value)}
              required
            />
            <span className="mt-1.5 block text-xs text-body">
              결과물은{' '}
              <code className="rounded-md bg-canvas-soft-2 px-1 py-0.5 font-mono text-ink">
                next-pjt/{alias.trim() || '<별칭>'}/
              </code>
              에 생성됩니다.
            </span>
          </label>
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium">요청 유형</legend>
            <div className="grid grid-cols-2 gap-3">
              {KINDS.map((k) => (
                <label
                  key={k.kind}
                  className={`flex cursor-pointer items-start gap-3 rounded-md border p-4 ${
                    kind === k.kind ? 'border-ink' : 'border-hairline hover:bg-canvas-soft-2'
                  }`}
                >
                  <input
                    type="radio"
                    name="kind"
                    data-testid={`kind-${k.kind}`}
                    className="mt-1 accent-ink"
                    checked={kind === k.kind}
                    onChange={() => setKind(k.kind)}
                  />
                  <span>
                    <span className="block font-medium">{k.title}</span>
                    <span className="mt-0.5 block text-xs text-body">{k.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <Callout icon="key">
            로그인이 필요한 사이트는 <code className="font-mono text-ink">.env</code>에 계정을 먼저
            넣어 두세요. 계정 값은 화면·로그에 나오지 않습니다.
          </Callout>
          {error && (
            <Callout tone="error" icon="error" testId="form-error">
              {error}
            </Callout>
          )}
        </div>
        <div className="mt-6 flex justify-end gap-2 border-t border-hairline pt-5">
          <Button
            onClick={() => {
              setUrl('');
              setAlias('');
              setError(undefined);
            }}
          >
            지우기
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={submitting}
            data-testid="submit-request"
          >
            분석 시작
          </Button>
        </div>
      </form>

      <section className="mt-10">
        <h2 className="text-sm font-semibold">진행 순서</h2>
        <ol className="mt-4 grid grid-cols-5">
          {PROCESS.map((p, i) => (
            <li key={p.label} className="relative flex flex-col items-center text-center">
              {i > 0 && <span className="absolute top-3 right-1/2 h-px w-full bg-hairline" />}
              <span className="relative z-[1] flex size-6 items-center justify-center rounded-full border border-hairline bg-canvas text-xs text-body">
                {i + 1}
              </span>
              <span className="mt-2 text-sm">{p.label}</span>
              {p.approval && (
                <span className="mt-1 flex items-center gap-1 text-xs text-body">
                  <Dot tone="waiting" />
                  승인 필요
                </span>
              )}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
