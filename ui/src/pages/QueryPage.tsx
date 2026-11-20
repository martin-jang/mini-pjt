import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { Link } from 'react-router';
import { agentApi } from '../api/agentApi';
import type { QueryAnswer } from '../api/types';
import { Icon } from '../components/Icon';
import { useSites } from '../hooks/useSites';

const SUGGESTIONS = [
  'Happy Path는 어떻게 정했어?',
  '공통 컴포넌트는 뭐가 있어?',
  '목업 데이터를 고른 이유는?',
];

interface Message {
  id: number;
  role: 'user' | 'agent';
  text?: string;
  answer?: QueryAnswer;
}

function AgentAvatar() {
  return (
    <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-ink font-mono text-[10px] font-semibold text-white">
      L2N
    </span>
  );
}

/** Router가 생성·확장 요청으로 분류한 경우: 새 요청 폼으로 넘어가는 링크 */
function startLink(start: Extract<QueryAnswer, { kind: 'start' }>['start']): string {
  const params = new URLSearchParams();
  if (start.url) params.set('url', start.url);
  if (start.kind === 'extend' && start.alias) params.set('extend', start.alias);
  else if (start.alias) params.set('alias', start.alias);
  return `/new?${params.toString()}`;
}

function AnswerView({ answer }: { answer: QueryAnswer }) {
  if (answer.kind === 'start') {
    return (
      <div className="min-w-0 flex-1" data-testid="answer-start">
        <p className="text-sm leading-6">{answer.text}</p>
        <Link
          to={startLink(answer.start)}
          data-testid="answer-start-link"
          className="mt-2 inline-flex h-8 items-center gap-1.5 rounded-md border border-hairline bg-canvas px-3 text-sm font-medium hover:bg-canvas-soft"
        >
          새 요청으로 시작
          <Icon name="arrow_forward" />
        </Link>
      </div>
    );
  }
  if (answer.kind === 'rejected') {
    return (
      <p
        className="border-l-2 border-hairline pl-3 text-sm text-body"
        data-testid="answer-rejected"
      >
        {answer.text}
      </p>
    );
  }
  return (
    <div className="min-w-0 flex-1" data-testid="answer">
      <p className="text-sm leading-6">{answer.text}</p>
      {answer.table && (
        <div className="mt-3 overflow-hidden rounded-md border border-hairline">
          <table className="w-full text-sm">
            <thead className="bg-canvas-soft-2 text-left text-xs text-body">
              <tr>
                {answer.table.columns.map((c) => (
                  <th key={c} className="px-4 py-2 font-normal">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {answer.table.rows.map((row, i) => (
                <tr key={i} className="border-t border-hairline">
                  {row.map((cell, j) => (
                    <td
                      key={j}
                      className={`px-4 py-2 ${j === 0 ? 'font-mono text-xs' : 'text-body'}`}
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {answer.sources.length > 0 && (
        <p className="mt-2 text-xs text-mute">근거: {answer.sources.join(' · ')}</p>
      )}
    </div>
  );
}

export function QueryPage() {
  const { sites } = useSites();
  const [alias, setAlias] = useState('');
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [pending, setPending] = useState(false);
  const nextId = useRef(1);
  const bottomRef = useRef<HTMLDivElement>(null);
  const target = alias || sites.find((s) => s.status === 'done')?.alias || sites[0]?.alias || '';

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' });
  }, [messages.length, pending]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || !target || pending) return;
    setInput('');
    setMessages((m) => [...m, { id: nextId.current++, role: 'user', text: q }]);
    setPending(true);
    try {
      const answer = await agentApi.ask(target, q);
      setMessages((m) => [...m, { id: nextId.current++, role: 'agent', answer }]);
    } catch (e) {
      const text = e instanceof Error ? e.message : '답변을 받지 못했습니다.';
      setMessages((m) => [
        ...m,
        { id: nextId.current++, role: 'agent', answer: { kind: 'rejected', text } },
      ]);
    } finally {
      setPending(false);
    }
  };

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void send(input);
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(input);
    }
  };

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-[760px] flex-col">
      <div className="flex items-center gap-3">
        <label className="flex h-9 items-center gap-2 rounded-md border border-hairline bg-canvas px-3 text-sm">
          <span className="text-body">대상 사이트</span>
          <select
            className="bg-transparent font-medium focus:outline-none"
            value={target}
            onChange={(e) => setAlias(e.target.value)}
            data-testid="query-site"
          >
            {sites.map((s) => (
              <option key={s.alias} value={s.alias}>
                {s.alias}
              </option>
            ))}
          </select>
        </label>
        <span className="text-xs text-body">분석·생성 결과를 기준으로 답합니다.</span>
      </div>
      <div className="mt-3 flex flex-wrap gap-2 border-b border-hairline pb-4">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => void send(s)}
            className="h-8 rounded-md border border-hairline bg-canvas px-3 text-sm text-ink hover:bg-canvas-soft-2"
          >
            {s}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-6 py-6" data-testid="chat-log">
        {messages.length === 0 && (
          <p className="pt-10 text-center text-sm text-mute">
            {target ? `${target}에 대해 궁금한 점을 물어보세요.` : '분석한 사이트가 없습니다.'}
          </p>
        )}
        {messages.map((m) =>
          m.role === 'user' ? (
            <div key={m.id} className="flex justify-end">
              <p className="max-w-[80%] rounded-md bg-canvas-soft-2 px-4 py-2.5 text-sm">
                {m.text}
              </p>
            </div>
          ) : (
            <div key={m.id} className="flex gap-3">
              <AgentAvatar />
              {m.answer && <AnswerView answer={m.answer} />}
            </div>
          ),
        )}
        {pending && (
          <div className="flex items-center gap-3 text-sm text-body">
            <AgentAvatar />
            답변을 찾는 중…
          </div>
        )}
        <div ref={bottomRef} className="scroll-mb-32" />
      </div>

      <form onSubmit={onSubmit} className="sticky bottom-0 bg-canvas-soft pt-2 pb-4">
        <div className="flex items-end gap-2 rounded-md border border-hairline bg-canvas p-2 focus-within:border-running">
          <textarea
            rows={1}
            className="max-h-32 min-h-9 flex-1 resize-none bg-transparent px-2 py-2 text-sm placeholder:text-mute focus:outline-none"
            placeholder={target ? `${target}에 대해 질문하세요` : '질문하세요'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            data-testid="query-input"
          />
          <button
            type="submit"
            aria-label="보내기"
            disabled={!input.trim() || pending}
            className="flex size-9 items-center justify-center rounded-md bg-ink text-white disabled:opacity-40"
            data-testid="query-send"
          >
            <Icon name="arrow_upward" />
          </button>
        </div>
        <p className="mt-1.5 text-center text-xs text-mute">Enter 전송 · Shift+Enter 줄바꿈</p>
      </form>
    </div>
  );
}
