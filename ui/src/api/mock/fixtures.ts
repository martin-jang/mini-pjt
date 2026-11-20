// 목업 데이터. 대상 사이트를 특정하지 않는 일반적인 "사내 업무 포털" 예시

import type {
  AnalysisDecision,
  AnalysisReview,
  DesignScreen,
  GeneratedScreen,
  LayoutSketch,
  RunResult,
} from '../types';

export const TOTAL_COLLECTED_SCREENS = 18;

export function buildAnalysis(): AnalysisReview {
  return {
    profile: {
      domain: '사내 업무 포털 (공지·근태·휴가)',
      users: '임직원, 부서 관리자',
      coreTasks: '공지 확인, 휴가 신청, 근태 조회',
      confidence: 0.92,
      summary:
        '로그인 후 첫 화면에 공지·근태 요약이 있고, 메뉴 18개 중 12개가 신청·조회 화면입니다. 화면 제목과 입력 항목으로 볼 때 임직원이 매일 쓰는 사내 업무 포털로 판단했습니다.',
      evidence: [
        { screen: '메인', path: '/main' },
        { screen: '공지 목록', path: '/notice/list' },
        { screen: '휴가 신청', path: '/leave/apply' },
      ],
    },
    happyPaths: [
      {
        id: 'hp1',
        title: '공지 확인',
        steps: ['로그인', '메인', '공지 목록', '공지 상세'],
        reason: '로그인 직후 가장 먼저 보이는 조회 흐름입니다. 쓰기 동작이 없어 시연이 안전합니다.',
        recommended: true,
      },
      {
        id: 'hp2',
        title: '휴가 신청',
        steps: ['로그인', '휴가 신청 목록', '휴가 신청'],
        reason: '입력 폼과 검증이 있는 대표 업무입니다. 바뀐 입력 경험을 보여주기 좋습니다.',
        recommended: true,
      },
      {
        id: 'hp3',
        title: '사용자 관리',
        steps: ['로그인', '사용자 목록', '사용자 상세'],
        reason: '관리자 메뉴라 수집 중 승인이 필요했고, 1차 시연 범위에서는 빼는 것을 권합니다.',
        recommended: false,
      },
    ],
    dataModes: [
      {
        mode: 'mock',
        title: '목업 데이터',
        summary: '수집한 화면 구조로 합성 데이터를 만들어 앱 안에서만 동작합니다.',
        reasons: [
          '휴가 신청은 쓰기 동작이라 시연 중 실제 데이터가 바뀔 수 있습니다',
          '레거시 응답이 서버에서 그린 HTML이라 API로 바로 쓰기 어렵습니다',
          '개인정보는 자리표시자 형식만 보고 합성 값으로 채웁니다',
        ],
        recommended: true,
      },
      {
        mode: 'legacy',
        title: '레거시 백엔드 호출',
        summary: '생성 앱이 레거시 서버에 직접 요청해 실제 데이터를 보여줍니다.',
        reasons: ['실제 데이터로 화면을 확인할 수 있습니다'],
        caveat: '레거시 세션·CORS 처리가 필요하고, 쓰기 동작은 실제 데이터를 바꿉니다.',
        recommended: false,
      },
    ],
    variants: [
      {
        id: 'v1',
        name: '목록 표',
        selectors: ['table.list', 'table.grid'],
        screenCount: 7,
        decision: 'unify',
        reason: '컬럼 구성과 페이지 이동 위치만 다릅니다. 하나의 표 컴포넌트로 묶습니다.',
      },
      {
        id: 'v2',
        name: '검색 조건 영역',
        selectors: ['.search_box', '.srch_area'],
        screenCount: 5,
        decision: 'prop',
        reason: '기간 선택이 있는 화면과 없는 화면이 나뉩니다. 기간 선택을 옵션으로 둡니다.',
      },
      {
        id: 'v3',
        name: '확인 팝업',
        selectors: ['window.open 팝업', '.layer_pop'],
        screenCount: 2,
        decision: 'hold',
        reason: '새 창 팝업과 레이어 팝업의 동작이 달라 확인이 필요합니다.',
      },
    ],
  };
}

export function recommendedDecision(analysis: AnalysisReview): AnalysisDecision {
  return {
    action: 'approve',
    happyPathIds: analysis.happyPaths.filter((p) => p.recommended).map((p) => p.id),
    dataMode: analysis.dataModes.find((m) => m.recommended)?.mode ?? 'mock',
    variantDecisions: Object.fromEntries(analysis.variants.map((v) => [v.id, v.decision])),
  };
}

const legacyPage: LayoutSketch = { nav: 'left', blocks: ['상단 배너', '본문 표', '하단 버튼'] };

interface ScreenTemplate {
  path: string;
  majorChange: boolean;
  changes: string[];
  asis: LayoutSketch;
  tobe: LayoutSketch;
  preserved: number;
  total: number;
}

const screenCatalog: Record<string, ScreenTemplate> = {
  로그인: {
    path: '/login',
    majorChange: false,
    changes: ['입력란·버튼 위치 유지, 간격과 글자 크기만 정리'],
    asis: { nav: 'none', blocks: ['로고', '아이디·비밀번호', '로그인 버튼'] },
    tobe: { nav: 'none', blocks: ['로고', '아이디·비밀번호', '로그인 버튼'] },
    preserved: 4,
    total: 4,
  },
  메인: {
    path: '/main',
    majorChange: false,
    changes: ['요약 박스 3개를 카드로 바꿈, 배치는 유지'],
    asis: legacyPage,
    tobe: { nav: 'left', blocks: ['상단 헤더', '요약 카드', '최근 공지'] },
    preserved: 9,
    total: 9,
  },
  '공지 목록': {
    path: '/notice/list',
    majorChange: false,
    changes: ['검색 조건과 표 구성 유지, 공통 표 컴포넌트 적용'],
    asis: { nav: 'left', blocks: ['검색 조건', '공지 표', '페이지 이동'] },
    tobe: { nav: 'left', blocks: ['검색 조건', '공지 표', '페이지 이동'] },
    preserved: 7,
    total: 7,
  },
  '공지 상세': {
    path: '/notice/detail',
    majorChange: false,
    changes: ['본문·첨부 영역 유지'],
    asis: { nav: 'left', blocks: ['제목', '본문', '첨부', '목록 버튼'] },
    tobe: { nav: 'left', blocks: ['제목', '본문', '첨부', '목록 버튼'] },
    preserved: 6,
    total: 6,
  },
  '휴가 신청 목록': {
    path: '/leave/list',
    majorChange: false,
    changes: ['상태 열을 배지로 표시, 표 구성 유지'],
    asis: { nav: 'left', blocks: ['검색 조건', '신청 표', '신청 버튼'] },
    tobe: { nav: 'left', blocks: ['검색 조건', '신청 표', '신청 버튼'] },
    preserved: 8,
    total: 8,
  },
  '휴가 신청': {
    path: '/leave/apply',
    majorChange: true,
    changes: [
      '한 화면에 있던 입력 11개를 "기간 선택 → 사유·결재자" 2단계로 나눔',
      '왼쪽 아래에 있던 신청 버튼을 오른쪽 아래로 옮김',
      '새 창으로 뜨던 결재자 선택을 화면 안 대화상자로 바꿈',
    ],
    asis: { nav: 'left', blocks: ['입력 11개 (한 화면)', '결재자 새 창', '신청 버튼(왼쪽)'] },
    tobe: { nav: 'left', blocks: ['1단계: 기간 선택', '2단계: 사유·결재자', '신청 버튼(오른쪽)'] },
    preserved: 11,
    total: 11,
  },
  '사용자 목록': {
    path: '/admin/user/list',
    majorChange: false,
    changes: ['공통 표 컴포넌트 적용'],
    asis: { nav: 'left', blocks: ['검색 조건', '사용자 표'] },
    tobe: { nav: 'left', blocks: ['검색 조건', '사용자 표'] },
    preserved: 6,
    total: 6,
  },
  '사용자 상세': {
    path: '/admin/user/detail',
    majorChange: false,
    changes: ['입력 항목 그룹 유지'],
    asis: { nav: 'left', blocks: ['기본 정보', '권한'] },
    tobe: { nav: 'left', blocks: ['기본 정보', '권한'] },
    preserved: 8,
    total: 8,
  },
};

function selectedScreenNames(analysis: AnalysisReview, happyPathIds: string[]): string[] {
  const names = analysis.happyPaths
    .filter((p) => happyPathIds.includes(p.id))
    .flatMap((p) => p.steps);
  return [...new Set(names)];
}

export function buildDesignScreens(
  analysis: AnalysisReview,
  happyPathIds: string[],
): DesignScreen[] {
  return selectedScreenNames(analysis, happyPathIds).map((name, index) => {
    const t = screenCatalog[name];
    return {
      id: `s${index + 1}`,
      name,
      path: t?.path ?? '/',
      majorChange: t?.majorChange ?? false,
      changes: t?.changes ?? [],
      state: 'pending',
      asis: t?.asis ?? legacyPage,
      tobe: t?.tobe ?? legacyPage,
    };
  });
}

const dataModeLabel = { mock: '목업 데이터', legacy: '레거시 백엔드 호출' } as const;
const variantLabel = { unify: '통일', prop: '변형 prop', hold: '보류' } as const;

export function buildResult(
  alias: string,
  analysis: AnalysisReview,
  decision: AnalysisDecision,
  designScreens: DesignScreen[],
): RunResult {
  const screens: GeneratedScreen[] = designScreens.map((s) => {
    const hp = analysis.happyPaths.find(
      (p) => decision.happyPathIds.includes(p.id) && p.steps.includes(s.name),
    );
    const t = screenCatalog[s.name];
    return {
      name: s.name,
      path: s.path,
      happyPath: hp?.title,
      preserved: t?.preserved ?? 1,
      total: t?.total ?? 1,
    };
  });
  const variantSummary = analysis.variants
    .map((v) => `${v.name} ${variantLabel[decision.variantDecisions[v.id] ?? v.decision]}`)
    .join(', ');
  return {
    outputDir: `next-pjt/${alias}/`,
    previewUrl: 'http://localhost:5174/',
    totalScreens: TOTAL_COLLECTED_SCREENS,
    screens,
    components: [
      'AppLayout',
      'DataTable',
      'SearchForm',
      'FormField',
      'DateRangePicker',
      'StatusBadge',
      'ConfirmDialog',
      'StepIndicator',
      'Pagination',
    ],
    decisions: [
      {
        label: 'Happy Path',
        value: analysis.happyPaths
          .filter((p) => decision.happyPathIds.includes(p.id))
          .map((p) => p.title)
          .join(', '),
      },
      { label: '데이터 연결 방식', value: dataModeLabel[decision.dataMode] },
      { label: '변이 통일', value: variantSummary },
    ],
    verification: [
      { id: 'build', label: '빌드', detail: 'npm run build 성공, 타입 오류 0건', passed: true },
      {
        id: 'flow',
        label: 'Happy Path 흐름 테스트',
        detail: `Playwright ${decision.happyPathIds.length}개 흐름 통과`,
        passed: true,
      },
      {
        id: 'preserve',
        label: '기능 보존 대조',
        detail: '레거시 입력 필드·버튼·조회 항목 ↔ data-testid 대조',
        passed: true,
      },
      {
        id: 'secret',
        label: '계정 원문 검색',
        detail: '생성 결과물에서 계정 값 0건',
        passed: true,
      },
      {
        id: 'guard',
        label: '가드레일',
        detail: '의존성 템플릿과 일치(G7), 쓰기 경로 범위 안(G9)',
        passed: true,
      },
    ],
  };
}

export const COMPONENT_USAGE: Record<string, string> = {
  AppLayout: '전체 화면',
  DataTable: '공지 목록, 휴가 신청 목록',
  SearchForm: '공지 목록, 휴가 신청 목록',
  FormField: '로그인, 휴가 신청',
  DateRangePicker: '휴가 신청, 공지 목록',
  StatusBadge: '휴가 신청 목록',
  ConfirmDialog: '휴가 신청',
  StepIndicator: '휴가 신청',
  Pagination: '공지 목록, 휴가 신청 목록',
};
