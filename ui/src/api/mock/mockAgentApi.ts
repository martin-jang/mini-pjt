// 가짜 에이전트. 타이머로 단계 진행과 SSE 로그를 흉내 내고, 승인 2곳에서 멈춘다

import type { AgentApi } from '../agentApi';
import { ApiError } from '../errors';
import type {
  AnalysisDecision,
  GuardrailEvent,
  LogLevel,
  LogSource,
  NewRunInput,
  QueryAnswer,
  RunDetail,
  RunEvent,
  RunMetrics,
  StageId,
} from '../types';
import {
  buildAnalysis,
  buildDesignScreens,
  buildResult,
  COMPONENT_USAGE,
  recommendedDecision,
  TOTAL_COLLECTED_SCREENS,
} from './fixtures';

type Step =
  | { kind: 'stage'; stage: StageId }
  | { kind: 'log'; source: LogSource; message: string; level?: LogLevel; llm?: number }
  | { kind: 'guard'; event: Omit<GuardrailEvent, 'at'>; message: string }
  | { kind: 'metrics'; patch: Partial<RunMetrics>; message: string }
  | { kind: 'note'; stage: StageId; note: string }
  | { kind: 'gate'; gate: 'analysis' | 'design' }
  | { kind: 'finish' };

interface MockRun {
  detail: RunDetail;
  queue: Step[];
  decision?: AnalysisDecision;
  stageStartedAt: Partial<Record<StageId, number>>;
  timer?: ReturnType<typeof setInterval>;
}

const STAGE_ORDER: StageId[] = [
  'explorer',
  'analyst',
  'analysisReview',
  'designer',
  'designReview',
  'builder',
  'verifier',
];

const LLM_LIMIT = 200;
const ALIAS_PATTERN = /^[a-z0-9][a-z0-9-]{1,31}$/;

function formatDuration(ms: number): string {
  const sec = Math.max(0, Math.round(ms / 1000));
  const m = Math.floor(sec / 60);
  return m > 0 ? `${m}분 ${sec % 60}초` : `${sec}초`;
}

function explorerSteps(url: string, kind: NewRunInput['kind']): Step[] {
  return [
    { kind: 'stage', stage: 'explorer' },
    { kind: 'log', source: 'system', message: `실행 시작: ${url}` },
    {
      kind: 'log',
      source: 'router',
      message: `의도 분류: ${kind === 'new' ? '신규 생성' : '확장'}`,
      llm: 1,
    },
    ...(kind === 'extend'
      ? [
          {
            kind: 'log',
            source: 'system',
            message: 'manifest 읽음: 이미 만든 화면은 건너뛰고 남은 화면만 대상',
          } as Step,
        ]
      : []),
    {
      kind: 'log',
      source: 'explorer',
      message: '로그인 화면에서 아이디·비밀번호 입력란 찾음',
      llm: 2,
    },
    {
      kind: 'guard',
      event: {
        rule: 'G3',
        detail: '로그인 값 입력 (계정 값은 로그·응답에서 가림)',
        outcome: 'masked',
      },
      message: '로그인 성공 (계정 값 ***)',
    },
    { kind: 'metrics', patch: { screensCollected: 4 }, message: '메뉴 탐색: 화면 4개 수집' },
    {
      kind: 'guard',
      event: { rule: 'G5', detail: '직원 목록 화면 이름·전화번호 23건', outcome: 'masked' },
      message: '개인정보 23건 마스킹 후 저장',
    },
    {
      kind: 'guard',
      event: { rule: 'G2', detail: '허용 origin 밖 링크 1건', outcome: 'blocked' },
      message: '허용 origin 밖 이동 차단: https://ext.example.net',
    },
    { kind: 'metrics', patch: { screensCollected: 12 }, message: '메뉴 탐색: 화면 12개 수집' },
    {
      kind: 'guard',
      event: { rule: 'G1', detail: "'삭제' 버튼 클릭 (승인 거절)", outcome: 'skipped' },
      message: "쓰기 동작 '삭제' 건너뜀",
    },
    {
      kind: 'metrics',
      patch: { screensCollected: TOTAL_COLLECTED_SCREENS },
      message: `수집 완료: 화면 ${TOTAL_COLLECTED_SCREENS}개`,
    },
    { kind: 'note', stage: 'explorer', note: `${TOTAL_COLLECTED_SCREENS}개 화면` },
    { kind: 'stage', stage: 'analyst' },
    { kind: 'log', source: 'analyst', message: '사이트 성격 추론: 사내 업무 포털', llm: 4 },
    {
      kind: 'log',
      source: 'analyst',
      message: `화면 목록 정리: ${TOTAL_COLLECTED_SCREENS}개`,
      llm: 2,
    },
    { kind: 'log', source: 'analyst', message: '변이 후보 3개 그룹 찾음', llm: 3 },
    {
      kind: 'log',
      source: 'analyst',
      message: 'Happy Path 후보 3개, 데이터 연결 방식 제안 작성',
      llm: 3,
    },
    { kind: 'gate', gate: 'analysis' },
  ];
}

function designerSteps(run: MockRun): Step[] {
  const screens = run.detail.design?.screens ?? [];
  return [
    { kind: 'stage', stage: 'designer' },
    { kind: 'log', source: 'designer', message: 'Stitch 디자인 시스템 생성', llm: 2 },
    ...screens.flatMap((s, i): Step[] => [
      {
        kind: 'log',
        source: 'designer',
        message: `화면 디자인 ${i + 1}/${screens.length}: ${s.path}`,
        llm: 2,
      },
      { kind: 'note', stage: 'designer', note: `화면 ${screens.length}개 중 ${i + 1}개` },
    ]),
    {
      kind: 'log',
      source: 'designer',
      message: '레거시·TOBE 레이아웃 비교: 대폭 변경 1개',
      llm: 1,
    },
    { kind: 'gate', gate: 'design' },
  ];
}

function builderSteps(run: MockRun): Step[] {
  const screens = run.detail.design?.screens ?? [];
  return [
    { kind: 'stage', stage: 'builder' },
    { kind: 'log', source: 'builder', message: '공통 컴포넌트 9개 생성', llm: 4 },
    ...screens.map((s): Step => ({
      kind: 'log',
      source: 'builder',
      message: `화면 생성: ${s.path}`,
      llm: 2,
    })),
    {
      kind: 'guard',
      event: { rule: 'G7', detail: 'package.json 의존성이 템플릿과 일치', outcome: 'approved' },
      message: '의존성 검사 통과',
    },
    { kind: 'note', stage: 'builder', note: `화면 ${screens.length}개` },
    { kind: 'stage', stage: 'verifier' },
    { kind: 'log', source: 'verifier', message: 'npm run build 성공' },
    { kind: 'log', source: 'verifier', message: 'Happy Path 흐름 테스트 통과' },
    { kind: 'log', source: 'verifier', message: '기능 보존 대조 통과' },
    { kind: 'log', source: 'verifier', message: '계정 원문 검색 0건' },
    { kind: 'finish' },
  ];
}

export function createMockAgentApi(options: { tickMs: number }): AgentApi {
  const { tickMs } = options;
  const runs = new Map<string, MockRun>();
  const runListeners = new Map<string, Set<(event: RunEvent) => void>>();
  const siteListeners = new Set<() => void>();

  const emit = (alias: string, event: RunEvent) => {
    runListeners.get(alias)?.forEach((cb) => cb(event));
  };
  const emitChanged = (alias: string) => {
    emit(alias, { type: 'changed' });
    siteListeners.forEach((cb) => cb());
  };

  const getMockRun = (alias: string): MockRun => {
    const run = runs.get(alias);
    if (!run) throw new ApiError(`'${alias}' 실행을 찾을 수 없습니다.`);
    return run;
  };

  const setStage = (run: MockRun, id: StageId, state: RunDetail['stages'][number]['state']) => {
    const stage = run.detail.stages.find((s) => s.id === id);
    if (stage) stage.state = state;
  };

  const log = (
    run: MockRun,
    now: number,
    source: LogSource,
    message: string,
    level: LogLevel = 'info',
  ) => {
    const line = { at: new Date(now).toISOString(), source, level, message };
    run.detail.logs.push(line);
    emit(run.detail.alias, { type: 'log', line });
  };

  const finishStage = (run: MockRun, id: StageId, now: number) => {
    const stage = run.detail.stages.find((s) => s.id === id);
    if (!stage || stage.state !== 'running') return;
    stage.state = 'done';
    const started = run.stageStartedAt[id];
    if (started !== undefined) {
      const took = formatDuration(now - started);
      stage.note = stage.note ? `${stage.note} · ${took}` : took;
    }
  };

  const enterWait = (run: MockRun, now: number) => {
    run.detail.timing.waitingSince = new Date(now).toISOString();
  };
  const leaveWait = (run: MockRun, now: number) => {
    const since = run.detail.timing.waitingSince;
    if (since) run.detail.timing.waitMs += now - Date.parse(since);
    run.detail.timing.waitingSince = undefined;
  };

  /** 단계 하나를 적용한다. 멈춰야 하면(승인 대기·완료) false */
  const applyStep = (run: MockRun, step: Step, now: number): boolean => {
    const d = run.detail;
    switch (step.kind) {
      case 'stage': {
        d.stages.filter((s) => s.state === 'running').forEach((s) => finishStage(run, s.id, now));
        setStage(run, step.stage, 'running');
        run.stageStartedAt[step.stage] = now;
        return true;
      }
      case 'log':
        d.metrics.llmCalls += step.llm ?? 0;
        log(run, now, step.source, step.message, step.level);
        return true;
      case 'guard': {
        d.guardrails.unshift({ ...step.event, at: new Date(now).toISOString() });
        const level: LogLevel =
          step.event.outcome === 'blocked'
            ? 'block'
            : step.event.outcome === 'skipped'
              ? 'warn'
              : 'info';
        log(run, now, 'guard', `${step.event.rule} ${step.message}`, level);
        return true;
      }
      case 'metrics':
        Object.assign(d.metrics, step.patch);
        log(run, now, 'explorer', step.message);
        return true;
      case 'note': {
        const stage = d.stages.find((s) => s.id === step.stage);
        if (stage) stage.note = step.note;
        return true;
      }
      case 'gate': {
        d.stages.filter((s) => s.state === 'running').forEach((s) => finishStage(run, s.id, now));
        if (step.gate === 'analysis') {
          d.analysis = buildAnalysis();
          setStage(run, 'analysisReview', 'waiting');
          d.status = 'awaiting_analysis';
          log(run, now, 'gate', '승인 1 대기: 분석 리뷰');
        } else {
          setStage(run, 'designReview', 'waiting');
          d.status = 'awaiting_design';
          log(run, now, 'gate', '승인 2 대기: 디자인 확인');
        }
        enterWait(run, now);
        return false;
      }
      case 'finish': {
        finishStage(run, 'verifier', now);
        d.status = 'done';
        d.timing.finishedAt = new Date(now).toISOString();
        if (d.analysis && run.decision && d.design) {
          d.result = buildResult(d.alias, d.analysis, run.decision, d.design.screens);
        }
        log(run, now, 'system', `완료: next-pjt/${d.alias}/ 생성`);
        return false;
      }
    }
  };

  const stopTimer = (run: MockRun) => {
    if (run.timer) clearInterval(run.timer);
    run.timer = undefined;
  };

  const startTimer = (run: MockRun) => {
    stopTimer(run);
    run.timer = setInterval(() => {
      const step = run.queue.shift();
      if (!step) {
        stopTimer(run);
        return;
      }
      const keepGoing = applyStep(run, step, Date.now());
      if (!keepGoing) stopTimer(run);
      emitChanged(run.detail.alias);
    }, tickMs);
  };

  /** 대기열을 시간 간격을 두고 즉시 처리한다 (시드 데이터용) */
  const fastForward = (run: MockRun, clock: { now: number }, count = Infinity) => {
    let done = 0;
    while (done < count) {
      const step = run.queue.shift();
      if (!step) return;
      clock.now += 20_000;
      done += 1;
      if (!applyStep(run, step, clock.now)) return;
    }
  };

  const newRun = (input: NewRunInput, startedAt: number): MockRun => {
    const run: MockRun = {
      detail: {
        alias: input.alias,
        url: input.url,
        kind: input.kind,
        status: 'running',
        stages: STAGE_ORDER.map((id) => ({ id, state: 'pending' })),
        metrics: { screensCollected: 0, llmCalls: 0, llmLimit: LLM_LIMIT },
        timing: { startedAt: new Date(startedAt).toISOString(), waitMs: 0 },
        logs: [],
        guardrails: [],
      },
      queue: explorerSteps(input.url, input.kind),
      stageStartedAt: {},
    };
    runs.set(input.alias, run);
    return run;
  };

  // ── 승인 처리 ─────────────────────────────

  const approveAnalysis = (run: MockRun, decision: AnalysisDecision, now: number) => {
    const d = run.detail;
    if (!d.analysis) return;
    run.decision = decision;
    d.approvedAnalysis = {
      happyPathIds: decision.happyPathIds,
      dataMode: decision.dataMode,
      variantDecisions: decision.variantDecisions,
    };
    leaveWait(run, now);
    setStage(run, 'analysisReview', 'done');
    d.status = 'running';
    d.design = {
      designSystem: `${d.alias} 디자인 시스템`,
      screens: buildDesignScreens(d.analysis, decision.happyPathIds),
    };
    log(run, now, 'gate', '승인 1 완료: 분석 리뷰');
    run.queue = designerSteps(run);
  };

  const completeDesign = (run: MockRun, now: number) => {
    leaveWait(run, now);
    setStage(run, 'designReview', 'done');
    run.detail.status = 'running';
    log(run, now, 'gate', '승인 2 완료: 디자인 확인');
    run.queue = builderSteps(run);
  };

  const approveAllScreens = (run: MockRun, now: number) => {
    run.detail.design?.screens.forEach((s) => {
      s.state = 'approved';
    });
    completeDesign(run, now);
  };

  // ── 시드: 진행 상태가 다른 사이트 3개 ─────────────────────────────

  const seed = () => {
    const now = Date.now();

    const done = newRun(
      { alias: 'intranet', url: 'https://intranet.example.com', kind: 'new' },
      now - 5 * 3600_000,
    );
    const c1 = { now: now - 5 * 3600_000 };
    fastForward(done, c1);
    c1.now += 95 * 60_000;
    if (done.detail.analysis)
      approveAnalysis(done, recommendedDecision(done.detail.analysis), c1.now);
    fastForward(done, c1);
    c1.now += 110 * 60_000;
    approveAllScreens(done, c1.now);
    fastForward(done, c1);

    const waiting = newRun(
      { alias: 'groupware', url: 'https://gw.example.com', kind: 'new' },
      now - 30 * 60_000,
    );
    fastForward(waiting, { now: now - 30 * 60_000 });

    const running = newRun(
      { alias: 'hr-portal', url: 'https://hr.example.com', kind: 'new' },
      now - 20 * 60_000,
    );
    const c3 = { now: now - 20 * 60_000 };
    fastForward(running, c3);
    c3.now += 6 * 60_000;
    if (running.detail.analysis)
      approveAnalysis(running, recommendedDecision(running.detail.analysis), c3.now);
    fastForward(running, c3, 4);
    startTimer(running);
  };
  seed();

  // ── 질의 (목업 답변) ─────────────────────────────

  const answer = (run: MockRun, question: string): QueryAnswer => {
    const d = run.detail;
    const q = question.toLowerCase();
    const inScope = [
      '화면',
      '컴포넌트',
      'happy',
      '핵심',
      '데이터',
      '목업',
      '분석',
      '디자인',
      '승인',
      '결정',
      '사이트',
      '결과',
      '검증',
      '변이',
      '이유',
      d.alias,
    ].some((k) => q.includes(k));
    if (!inScope) {
      return {
        kind: 'rejected',
        text: '이 서비스는 분석한 사이트와 생성 결과에 대한 질문만 답할 수 있어요. 예: 화면 구성, 컴포넌트, 승인된 결정.',
      };
    }
    if (!d.analysis) {
      return {
        kind: 'answer',
        text: `${d.alias}는 아직 분석이 끝나지 않았어요. 분석 리뷰 이후에 다시 물어봐 주세요.`,
        sources: [],
      };
    }
    if (q.includes('컴포넌트') || q.includes('변이')) {
      const comps = d.result?.components ?? Object.keys(COMPONENT_USAGE);
      return {
        kind: 'answer',
        text: `${d.alias}에는 공통 컴포넌트 ${comps.length}개를 썼습니다.`,
        table: {
          columns: ['컴포넌트', '쓰인 화면'],
          rows: comps.map((c) => [c, COMPONENT_USAGE[c] ?? '—']),
        },
        sources: ['manifest.json', '분석 리뷰 결정 (변이 통일)'],
      };
    }
    if (q.includes('데이터') || q.includes('목업')) {
      const mode = d.analysis.dataModes.find((m) => m.mode === (run.decision?.dataMode ?? 'mock'));
      return {
        kind: 'answer',
        text: `데이터 연결 방식은 "${mode?.title ?? '목업 데이터'}"로 정했습니다. 근거: ${mode?.reasons.join(' / ') ?? ''}`,
        sources: ['분석 리뷰 결정 (데이터 연결 방식)'],
      };
    }
    if (q.includes('happy') || q.includes('핵심')) {
      const ids = run.decision?.happyPathIds ?? [];
      const paths = d.analysis.happyPaths.filter((p) => ids.length === 0 || ids.includes(p.id));
      return {
        kind: 'answer',
        text: `사이트 성격(${d.analysis.profile.domain})을 기준으로 아래 흐름을 골랐습니다.`,
        table: {
          columns: ['흐름', '화면', '이유'],
          rows: paths.map((p) => [p.title, p.steps.join(' → '), p.reason]),
        },
        sources: ['분석 리뷰 결정 (Happy Path)'],
      };
    }
    if (q.includes('화면') && d.result) {
      return {
        kind: 'answer',
        text: `생성한 화면은 ${d.result.screens.length}개입니다 (수집 ${d.result.totalScreens}개 중).`,
        table: {
          columns: ['화면', '경로', '기능 보존'],
          rows: d.result.screens.map((s) => [s.name, s.path, `${s.preserved}/${s.total}`]),
        },
        sources: ['manifest.json'],
      };
    }
    return {
      kind: 'answer',
      text: `${d.alias}는 ${d.analysis.profile.domain}로 추론했습니다. 주요 사용자는 ${d.analysis.profile.users}, 핵심 업무는 ${d.analysis.profile.coreTasks}입니다.`,
      sources: ['분석 리뷰 (사이트 성격 추론)'],
    };
  };

  const delay = <T>(value: () => T, ms = tickMs): Promise<T> =>
    new Promise((resolve, reject) =>
      setTimeout(
        () => {
          try {
            resolve(value());
          } catch (e) {
            reject(e);
          }
        },
        Math.min(ms, 300),
      ),
    );

  return {
    listSites: () =>
      delay(
        () =>
          [...runs.values()].map(({ detail: { alias, url, status } }) => ({ alias, url, status })),
        0,
      ),

    watchSites: (onChange) => {
      siteListeners.add(onChange);
      return () => siteListeners.delete(onChange);
    },

    getRun: (alias) => delay(() => structuredClone(getMockRun(alias).detail), 0),

    createRun: (input) =>
      delay(() => {
        if (!/^https?:\/\/[^\s/]+/.test(input.url))
          throw new ApiError('http:// 또는 https://로 시작하는 URL을 입력하세요.');
        if (!ALIAS_PATTERN.test(input.alias)) {
          throw new ApiError('별칭은 영문 소문자·숫자·하이픈으로 2~32자여야 합니다.');
        }
        const existing = runs.get(input.alias);
        if (input.kind === 'new' && existing)
          throw new ApiError(`'${input.alias}' 별칭이 이미 있습니다. 확장 요청을 쓰세요.`);
        if (input.kind === 'extend') {
          if (!existing)
            throw new ApiError(`'${input.alias}' 결과물이 없습니다. 신규 생성을 먼저 하세요.`);
          if (existing.detail.status !== 'done')
            throw new ApiError(`'${input.alias}' 실행이 아직 끝나지 않았습니다.`);
        }
        const run = newRun(input, Date.now());
        startTimer(run);
        siteListeners.forEach((cb) => cb());
        return structuredClone(run.detail);
      }),

    streamRun: (alias, onEvent) => {
      const set = runListeners.get(alias) ?? new Set();
      set.add(onEvent);
      runListeners.set(alias, set);
      return () => set.delete(onEvent);
    },

    submitAnalysis: (alias, decision) =>
      delay(() => {
        const run = getMockRun(alias);
        if (run.detail.status !== 'awaiting_analysis')
          throw new ApiError('분석 리뷰 승인 대기 상태가 아닙니다.');
        const now = Date.now();
        if (decision.action === 'reject') {
          leaveWait(run, now);
          setStage(run, 'analysisReview', 'stopped');
          run.detail.status = 'stopped';
          run.detail.timing.finishedAt = new Date(now).toISOString();
          log(
            run,
            now,
            'gate',
            `분석 리뷰 반려${decision.comment ? `: ${decision.comment}` : ''}`,
            'warn',
          );
        } else if (decision.action === 'revise') {
          if (!decision.comment?.trim()) throw new ApiError('수정 요청 내용을 입력하세요.');
          log(run, now, 'gate', `분석 수정 요청: ${decision.comment}`);
          log(run, now, 'analyst', '수정 요청을 반영해 분석 결과를 다시 정리했습니다');
        } else {
          if (decision.happyPathIds.length === 0)
            throw new ApiError('Happy Path를 하나 이상 고르세요.');
          approveAnalysis(run, decision, now);
          startTimer(run);
        }
        emitChanged(alias);
      }),

    submitDesign: (alias, decision) =>
      delay(() => {
        const run = getMockRun(alias);
        const design = run.detail.design;
        if (run.detail.status !== 'awaiting_design' || !design)
          throw new ApiError('디자인 확인 승인 대기 상태가 아닙니다.');
        const now = Date.now();
        switch (decision.action) {
          case 'approveScreen': {
            const screen = design.screens.find((s) => s.id === decision.screenId);
            if (!screen) throw new ApiError('화면을 찾을 수 없습니다.');
            screen.state = 'approved';
            log(run, now, 'gate', `화면 승인: ${screen.path}`);
            break;
          }
          case 'approveRegular': {
            const regular = design.screens.filter((s) => !s.majorChange && s.state === 'pending');
            regular.forEach((s) => {
              s.state = 'approved';
            });
            log(run, now, 'gate', `일반 화면 ${regular.length}개 일괄 승인`);
            break;
          }
          case 'revise': {
            const screen = design.screens.find((s) => s.id === decision.screenId);
            if (!screen) throw new ApiError('화면을 찾을 수 없습니다.');
            if (!decision.comment.trim()) throw new ApiError('수정 요청 내용을 입력하세요.');
            screen.state = 'revise';
            log(run, now, 'gate', `화면 수정 요청: ${screen.path} — ${decision.comment}`);
            setTimeout(() => {
              screen.state = 'pending';
              screen.changes = [
                ...screen.changes,
                { what: `수정 요청 반영: ${decision.comment}`, why: '사용자 수정 요청' },
              ];
              log(run, Date.now(), 'designer', `수정 요청 반영: ${screen.path}`);
              emitChanged(alias);
            }, tickMs * 4);
            break;
          }
          case 'rejectAll': {
            leaveWait(run, now);
            setStage(run, 'designReview', 'stopped');
            run.detail.status = 'stopped';
            run.detail.timing.finishedAt = new Date(now).toISOString();
            log(
              run,
              now,
              'gate',
              `디자인 전체 반려${decision.comment ? `: ${decision.comment}` : ''}`,
              'warn',
            );
            break;
          }
        }
        if (
          run.detail.status === 'awaiting_design' &&
          design.screens.every((s) => s.state === 'approved')
        ) {
          completeDesign(run, now);
          startTimer(run);
        }
        emitChanged(alias);
      }),

    // 목업 흐름은 로그인이 없는 사이트라 인증 대기에 들어가지 않는다 (인증 흐름은 실제 서버 E2E로 확인)
    submitAuth: (alias) =>
      delay(() => {
        const run = getMockRun(alias);
        if (run.detail.status !== 'awaiting_auth')
          throw new ApiError('사용자 인증 승인 대기 상태가 아닙니다.');
      }),

    deleteSession: (alias) =>
      delay(() => {
        const run = getMockRun(alias);
        run.detail.sessionSaved = false;
        emitChanged(alias);
      }),

    stopRun: (alias) =>
      delay(() => {
        const run = getMockRun(alias);
        if (run.detail.status === 'done' || run.detail.status === 'stopped') return;
        const now = Date.now();
        stopTimer(run);
        leaveWait(run, now);
        run.detail.stages.forEach((s) => {
          if (s.state === 'running' || s.state === 'waiting') s.state = 'stopped';
        });
        run.detail.status = 'stopped';
        run.detail.timing.finishedAt = new Date(now).toISOString();
        log(run, now, 'system', '사용자가 실행을 중단했습니다', 'warn');
        emitChanged(alias);
      }),

    ask: (alias, question) => delay(() => answer(getMockRun(alias), question), tickMs * 2),
  };
}
